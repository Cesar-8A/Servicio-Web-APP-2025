from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, Response
from flask import session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, EqualTo

import tempfile
import zipfile
from collections import defaultdict
import numpy as np
import numpy.ma as ma
import pyvista as pv
pv.OFF_SCREEN = True
import panel as pn
import os
import pydicom
import nrrd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
from scipy.ndimage import label, binary_erosion

import dash
from dash import html, dcc, Input, Output, State
import dash_vtk
from dash_extensions.enrich import DashProxy, MultiplexerTransform

from process_dicom_folder import process_dicom_folder


os.chdir("C:/Users/Usuario/OneDrive/flask")

#os.chdir("c:\\Users\\jesus\\Desktop\\Cucei\\SERVICIO\\Servicio-Web-APP-2025")
#os.chdir("C:/Users/lozan/Downloads/Servicio-Web-APP-2025-branchChuy")

app = Flask(__name__)
app.secret_key = "clave_secreta_no_tan_secreta_jeje"

# Inyección global de estado de sesión a todas las plantillas
@app.context_processor
def inject_user():
    return {
        'user_logged_in': session.get('user_logged_in', False),
        'user_initials': session.get('user_initials', '')
    }

#Variables globales
panel_vtk = None
plotter = None #instancia del panel
bokeh_on = False
selected_dicom_metadata = None
selected_dicom_slices = None
UPLOAD_FOLDER = 'uploads'
UPLOAD_FOLDER_NRRD = 'upload_nrrd'
ANONIMIZADO_FOLDER = os.path.join(os.getcwd(), 'anonimizado')
grid_dicom = None
grid_RT = None

app.config['dicom_series'] = None
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['Image'] = np.array([])
app.config['RT'] = np.array([])
app.config["unique_id"] = 0

# Crear la carpeta de subidas si no existe
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if not os.path.exists(UPLOAD_FOLDER_NRRD):
    os.makedirs(UPLOAD_FOLDER_NRRD)    

pn.extension('vtk')  # Activar la extensión VTK de Panel


# Iniciar el servidor Bokeh una sola vez al iniciar la aplicación
def start_bokeh_server(panel_vtk):
    global bokeh_on
    
    if not bokeh_on:
        pn.serve({'/panel': panel_vtk}, show=False, allow_websocket_origin=["*"], port=5010, threaded=True)
        bokeh_on = True
    

@app.route('/process_selected_dicom', methods=['POST'])
def process_selected_dicom():
    data = request.json  # Recibir JSON del frontend
    unique_id = data.get('unique_id')  # Obtener el ID seleccionado
    app.config["unique_id"] = unique_id

    if not unique_id:
        return jsonify({"error": "No se recibió un ID válido"}), 400

    print(f"Procesando DICOM con ID: {unique_id}")

    image = app.config['dicom_series'][unique_id]["slices"][:,:] #Obtener unicamente la imagen sin el instance number
    #print(np.array(image).shape)
        # Obtener los datos crudos de la imagen DICOM
    #image = app.config['dicom_series'][unique_id]["slices"][:, :, 50]  # Tomar un corte medio

    # Ajuste de unidades Hounsfield (HU)
    rescale_slope = app.config['dicom_series'][unique_id]['RescaleSlope']
    rescale_intercept = app.config['dicom_series'][unique_id]['RescaleIntercept']
    image_processed = image * rescale_slope + rescale_intercept
    app.config["Image"] = image_processed.astype(np.int16) #Reducir el espacio ocupado con un dato de menor tamaño
    global panel_vtk 
    panel_vtk = None
    return jsonify({"mensaje": "Ok"})  # Respuesta JSON al frontend

################################################################################################################

@app.route('/anonimize')
def anonimize():
    if type(app.config['dicom_series'])!=type(None):
        success = 1
        unique_id = app.config['unique_id']
        dicom_series = app.config['dicom_series'][unique_id]['Anonimize']
    else:
        success = 0
        dicom_series = None
    return render_template('anonimize.html', dicom_series=dicom_series, success = success)

@app.route('/guardar_cambios', methods=['POST'])
def guardar_cambios():
    data = request.json  # Obtener los cambios enviados por el frontend
    cambios = data.get('cambios', {})  # Obtener el diccionario de cambios

    unique_id = app.config['unique_id']  # Obtener el ID único de la serie DICOM seleccionada

    if not unique_id or not cambios:
        return jsonify({"error": "Datos inválidos"}), 400

    # Actualizar el diccionario de anonimización con los nuevos valores
    for campo, valor in cambios.items():
        if campo in app.config['dicom_series'][unique_id]['Anonimize']:
            app.config['dicom_series'][unique_id]['Anonimize'][campo] = valor

    return jsonify({"mensaje": "Cambios guardados correctamente"})

################################################################
from dicom_export import export_dicom_series

@app.route('/exportar_dicom', methods=['POST'])
def exportar_dicom():
    unique_id = app.config.get('unique_id')
    if not unique_id:
        return jsonify({"error": "Datos inválidos"}), 400

    try:
        zip_path = export_dicom_series(unique_id, ANONIMIZADO_FOLDER)
        return send_file(zip_path, as_attachment=True, download_name='archivos_anonimizados.zip')
    except Exception as e:
        return jsonify({"error": str(e)}), 500
################################################################

from render import create_render

@app.route("/render/<render>")
def render(render):
    global panel_vtk
    image = app.config.get('Image', None)

    if image is None or image.size == 0:
        return "❌ No hay imagen cargada o está vacía", 400

    if image.ndim != 3:
        return f"❌ Se esperaba una imagen 3D, pero se obtuvo una imagen con shape {image.shape}", 400

    if panel_vtk is None:
        render_state = create_render()
        app.config["render_state"] = render_state
        panel_vtk = render_state["panel_column"]
        start_bokeh_server(panel_vtk)

    return render_template(
        "render.html",
        success=(0 if panel_vtk is None else 1),
        render=render,
        max_value_axial=image.shape[0] - 1,
        max_value_sagital=image.shape[1] - 1,
        max_value_coronal=image.shape[2] - 1
    )

################################################################
from get_image import generate_slice_image

@app.route('/image/<view>/<int:layer>')
def get_image(view, layer):
    buf, error_message, status_code = generate_slice_image(view, layer)
    if status_code != 200:
        return error_message, status_code
    return send_file(buf, mimetype='image/png')
################################################################

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {"nrrd"} #Añadir aqui mas extensiones permitidas para RT Struct

from rt import add_RT_to_plotter

@app.route("/upload_RT", methods=["POST"])
def upload_RT():
    global panel_vtk, plotter

    if 'file' not in request.files:
        return "No se encontró el archivo", 400  # Respuesta de error

    file = request.files["file"]

    if file.filename == '':
        return "Nombre de archivo inválido", 400

    # Guardar el archivo dentro de la ruta segura
    filepath = os.path.join(UPLOAD_FOLDER_NRRD, file.filename)
    file.save(filepath)

    # Leer el archivo NRRD
    app.config['RT'], _ = nrrd.read(filepath)
    
    # Llamar a la función y actualizar el panel
    render_state = app.config.get("render_state")
    panel_vtk = add_RT_to_plotter(render_state)

    return render_template("render.html", max_value_axial=app.config['Image'].shape[0]-1 , max_value_sagital=app.config['Image'].shape[1]-1 , max_value_coronal=app.config['Image'].shape[2]-1)  # Tamaño fijo o dinámico 
        
################################################################
from dicom_metadata import load_metadata_and_slices

@app.route('/loadDicomMetadata/<unique_id>')
def load_dicom_metadata(unique_id):
    try:
        metadata = load_metadata_and_slices(unique_id)
        return jsonify(metadata)

    except Exception as e:
        return jsonify({"error": str(e)}), 400
################################################################


@app.route('/loadDicom', methods=['GET', 'POST'])
def loadDicom():
    try:
        if request.method == 'POST':
            # Verificar si se ha subido un archivo
            if 'folder' not in request.files:
                return redirect(request.url)
            
            folder = request.files.getlist('folder')
            if not folder:
                return redirect(request.url)
            
            # Guardar los archivos en la carpeta de subidas
            saved_files = []
            for file in folder:
                #print(file.filename)
                file_name = file.filename.split('/')
                
                if len(file_name) > 1:
                    file_name = file_name[-1]
                file_path = app.config['UPLOAD_FOLDER']+'/'+file_name
                file.save(file_path)
                saved_files.append(file_path)
                #saved_files.append(file)
            
            # Procesar los archivos DICOM
            #dicom_series = process_dicom_folder(app.config['UPLOAD_FOLDER'])
            dicom_series = process_dicom_folder(saved_files)
            
            # Redirigir a la página de resultados
            return render_template('resultsTableDicom.html', dicom_series=dicom_series)
    except:
        pass
    return render_template('loadDicom.html')

# CODIGO - INICIO DE SESION
# Formulario de inicio de sesión
class LoginForm(FlaskForm):
    username = StringField('Usuario', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField('Contraseña', validators=[InputRequired(), Length(min=4, max=20)])
    submit = SubmitField('Iniciar sesión')

# Formulario de registro
class RegisterForm(FlaskForm):
    username = StringField('Usuario', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField('Contraseña', validators=[InputRequired(), Length(min=4, max=20)])
    confirm_password = PasswordField('Confirmar contraseña', validators=[InputRequired(), EqualTo('password')])
    submit = SubmitField('Registrarse')

# Base de datos de ejemplo (diccionario en memoria)
usuarios = {}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = form.username.data
        password = form.password.data

        if user in usuarios and usuarios[user] == password:
            session['user_logged_in'] = True
            session['user_initials'] = user[:2].upper()
            flash('Inicio de sesión exitoso', 'success')
            return redirect(url_for('home'))
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = form.username.data
        password = form.password.data

        if user in usuarios:
            flash('El usuario ya existe', 'danger')
        else:
            usuarios[user] = password
            flash('Registro exitoso. Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión', 'info')
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)