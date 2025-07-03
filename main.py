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

os.chdir("c:\\Users\\jesus\\Desktop\\Cucei\\SERVICIO\\Servicio-Web-APP-2025")
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


def create_render():
    
    global plotter, skin_actor, slider, grid_dicom

    volume_bone = ((app.config['Image'] > 175) * 1).astype(np.int16)
    volume_skin = (((app.config['Image'] > -200) & (app.config['Image'] < 0)) * 1).astype(np.int16)
    unique_id = app.config["unique_id"]

    origin = app.config['dicom_series'][unique_id]["ImagePositionPatient"]
    spacing = (
        app.config['dicom_series'][unique_id]["SliceThickness"],
        app.config['dicom_series'][unique_id]["PixelSpacing"][0],
        app.config['dicom_series'][unique_id]["PixelSpacing"][1],
    )

    # --- HUESO GRID ---
    grid_bone = pv.ImageData()
    grid_bone.dimensions = np.array(volume_bone.shape) + 1
    grid_bone.origin = origin
    grid_bone.spacing = spacing
    grid_bone.cell_data["values"] = volume_bone.flatten(order="F")
    grid_bone = grid_bone.cell_data_to_point_data()
    surface_bone = grid_bone.contour([0.5])

    # --- PIEL GRID ---
    grid_skin = pv.ImageData()
    grid_skin.dimensions = np.array(volume_skin.shape) + 1
    grid_skin.origin = origin
    grid_skin.spacing = spacing
    grid_skin.cell_data["values"] = volume_skin.flatten(order="F")
    grid_skin = grid_skin.cell_data_to_point_data()
    surface_skin = grid_skin.contour([0.5])
    
    # Para usarse después y plotear segmentaciones
    grid_dicom = grid_skin
    
    # --- PLOTTING ---
    plotter = pv.Plotter(off_screen=True)
    plotter.set_background("black")
    plotter.add_mesh(surface_bone, color="white", smooth_shading=True, ambient=0.3, specular=0.4, specular_power=10)
    skin_actor = plotter.add_mesh(surface_skin, color="peachpuff", opacity=0.5, name="skin", smooth_shading=True)  # Piel transparente

    plotter.view_isometric()
    plotter.show_axes()

    panel_vtk = pn.pane.VTK(plotter.ren_win, width=400, height=500)

    # --- SLIDER + CALLBACK ---
    slider = pn.widgets.FloatSlider(name="Opacidad de la piel", start=0.0, end=1.0, step=0.05, value=0.5)

    def update_opacity(event):  # Actualizar la opacidad de la piel
        skin_actor.GetProperty().SetOpacity(event.new)
        panel_vtk.param.trigger('object')

    slider.param.watch(update_opacity, 'value')

    return pn.Column(panel_vtk, slider)


def add_RT_to_plotter():
    
    global plotter, panel_vtk, mask_actor

    if plotter is None:
        print("No hay plotter activo.")
        return

    app.config['RT'] = np.flip(app.config['RT'], axis=(0, 2)) # Voltear las posiciones 1 y 3 para que el 3D quede alineado
    RT_Image = app.config['RT']
    RT_Image = RT_Image.transpose(2, 0, 1) # Formato NRRD: (X, Y, Z), cambiar para coincidir con DICOM

    rt_grid = pv.ImageData()
    rt_grid.dimensions = np.array(RT_Image.shape) + 1
    
    # Asignar los mismos origin y spacing del grid de DICOM para estar en el mismo espacio físico
    rt_grid.origin = grid_dicom.origin
    rt_grid.spacing = grid_dicom.spacing
    
    # Asignar segmentación binaria
    rt_grid.cell_data["values"] = (RT_Image > 1).astype(np.uint8).flatten(order="F")

    # Convertir a point_data para que funcione contour() y Generar superficie con isovalor 0.5
    rt_grid = rt_grid.cell_data_to_point_data()
    surface = rt_grid.contour([0.5])

    # Agregar la malla segmentada al plotter
    plotter.add_mesh(surface, color="red", opacity=0.5, smooth_shading=True, specular=0.3)
    plotter.render() # Actualizar el plotter
    panel_vtk.object = plotter.ren_win # Actualizar el panel

    def update_opacity(event):  # Actualizar la opacidad de la piel
        skin_actor.GetProperty().SetOpacity(event.new)
        panel_vtk.param.trigger('object')

    slider.param.watch(update_opacity, 'value')
    
    return pn.Column(panel_vtk, slider)


# Iniciar el servidor Bokeh una sola vez al iniciar la aplicación
def start_bokeh_server(panel_vtk):
    global bokeh_on
    
    if not bokeh_on:
        pn.serve({'/panel': panel_vtk}, show=False, allow_websocket_origin=["*"], port=5010, threaded=True)
        bokeh_on = True
    
def process_dicom_folder(directory):
    """Procesa un directorio de archivos DICOM y devuelve un diccionario con la información."""
    dicom_series = defaultdict(lambda: {
        "ruta_archivos": [],
        "paciente": None,
        "tipo": None,
        "dimensiones": None,
        "RescaleSlope": 1,
        "RescaleIntercept": 1,
        "ImagePositionPatient": 1,
        "ImageOrientationPatient": [],
        "PixelSpacing": 0,
        "SliceThickness": 0,
        "slices": [
        ],
        "Anonimize": {
            'PatientName': 'Nombre del paciente',
            'PatientID': 'ID del paciente',
            'PatientBirthDate': 'Fecha de nacimiento del paciente',
            'PatientSex': 'Sexo del paciente',
            'PatientAge': 'Edad del paciente',
            'StudyDate': 'Fecha del estudio',
            'StudyTime': 'Hora del estudio',
            'AccessionNumber': 'Número de acceso',
            'ReferringPhysicianName': 'Nombre del médico derivador',
            'MedicalRecordLocator': 'Número de historia clínica',
            'InstitutionName': 'Nombre de la institución',
            'InstitutionAddress': 'Dirección de la institución',
            'StudyDescription': 'Descripción del estudio',
            'SeriesDescription': 'Descripción de la serie',
            'OperatorName': 'Nombre del operador',
            'SeriesNumber': 'Número de la serie',
            'InstanceNumber': 'Número de la instancia',
        }
    })
    # Recorrer la carpeta de manera recursiva
    for file in directory:
        #file_path = os.path.join(root, file)
        try:
            # Intentar leer el archivo como DICOM
            dicom_data = pydicom.dcmread(file, stop_before_pixels=False,  force=True)
            # Identificar la serie única usando StudyInstanceUID y SeriesInstanceUID
            study_id = dicom_data.StudyInstanceUID
            series_id = dicom_data.SeriesInstanceUID
            unique_id = f"{study_id}-{series_id}"

            # Obtener el nombre del paciente
            paciente_nombre = dicom_data.PatientName if 'PatientName' in dicom_data else "Desconocido"
            
            # Agregar el archivo a la serie correspondiente en el diccionario
            dicom_series[unique_id]["ruta_archivos"].append(file)
            dicom_series[unique_id]["paciente"] = paciente_nombre
            dicom_series[unique_id]["dimensiones"] = (len(dicom_series[unique_id]["ruta_archivos"]), dicom_data.Rows, dicom_data.Columns)
            dicom_series[unique_id]["RescaleSlope"] = dicom_data.RescaleSlope
            dicom_series[unique_id]["RescaleIntercept"] = dicom_data.RescaleIntercept
            dicom_series[unique_id]["ImagePositionPatient"] = dicom_data.ImagePositionPatient
            dicom_series[unique_id]["PixelSpacing"] = dicom_data.PixelSpacing  
            dicom_series[unique_id]["SliceThickness"] = dicom_data.get("SliceThickness", 1)

            ##Anonimize
            dicom_series[unique_id]['Anonimize']['PatientName'] = dicom_data.PatientName
            dicom_series[unique_id]['Anonimize']['PatientID'] = dicom_data.PatientID 
            dicom_series[unique_id]['Anonimize']['PatientBirthDate'] = dicom_data.PatientBirthDate 
            dicom_series[unique_id]['Anonimize']['PatientSex'] = dicom_data.PatientSex 
            dicom_series[unique_id]['Anonimize']['PatientAge'] = dicom_data.PatientAge 
            dicom_series[unique_id]['Anonimize']['StudyDate'] = dicom_data.StudyDate 
            dicom_series[unique_id]['Anonimize']['StudyTime'] = dicom_data.StudyTime 
            dicom_series[unique_id]['Anonimize']['AccessionNumber'] = dicom_data.AccessionNumber 
            dicom_series[unique_id]['Anonimize']['ReferringPhysicianName'] = dicom_data.ReferringPhysicianName 
            dicom_series[unique_id]['Anonimize']['MedicalRecordLocator'] = dicom_data.MedicalRecordLocator 
            dicom_series[unique_id]['Anonimize']['InstitutionName'] = dicom_data.InstitutionName 
            dicom_series[unique_id]['Anonimize']['InstitutionAddress'] = dicom_data.InstitutionAddress 
            dicom_series[unique_id]['Anonimize']['StudyDescription'] = dicom_data.StudyDescription 
            dicom_series[unique_id]['Anonimize']['SeriesDescription'] = dicom_data.SeriesDescription 
            dicom_series[unique_id]['Anonimize']['OperatorName'] = dicom_data.OperatorName 
            dicom_series[unique_id]['Anonimize']['SeriesNumber'] = dicom_data.SeriesNumber 
            dicom_series[unique_id]['Anonimize']['InstanceNumber'] = dicom_data.InstanceNumber 



            if len(dicom_series[unique_id]["ruta_archivos"]) > 1:
                dicom_series[unique_id]["tipo"] = "3D"
            else:
                dicom_series[unique_id]["tipo"] = "2D"
            #dicom_series[unique_id]["slices"].append([dicom_data.get("InstanceNumber", "None"),dicom_data.pixel_array])
            
        
        except Exception as e:
            # Si el archivo no es DICOM, lo ignoramos
            continue

    app.config['dicom_series']  = dicom_series.copy()
    return dicom_series

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

@app.route('/exportar_dicom', methods=['POST'])
def exportar_dicom():
    unique_id = app.config['unique_id']  # Obtener el ID único de la serie DICOM seleccionada

    if not unique_id:
        return jsonify({"error": "Datos inválidos"}), 400

    # Obtener la lista de archivos DICOM de la serie seleccionada
    archivosDicom = app.config['dicom_series'][unique_id]["ruta_archivos"]

    # Procesar cada archivo DICOM
    for archivo in archivosDicom:
        try:
            # Leer el archivo DICOM
            dicom_data = pydicom.dcmread(archivo)

            # Aplicar los cambios de anonimización
            for campo, valor in app.config['dicom_series'][unique_id]['Anonimize'].items():
                if campo in dicom_data:
                    # Asignar el valor como texto (sin formato específico)
                    try:
                        dicom_data[campo].value = str(valor)
                    except:
                        dicom_data[campo].value = 0

            # Crear el nuevo nombre del archivo anonimizado
            nombreArchivo = os.path.basename(archivo)
            nombreAnonimizado = f"anonimo_{nombreArchivo}"  # Concatenar "anonimo_" al nombre
            rutaDestino = os.path.join(ANONIMIZADO_FOLDER, nombreAnonimizado)

            # Guardar el archivo anonimizado en la carpeta "anonimizado"
            dicom_data.save_as(rutaDestino)

        except Exception as e:
            print(f"Error al procesar el archivo {archivo}: {e}")
            continue

    # Crear un archivo ZIP con los archivos anonimizados
    zip_path = os.path.join(ANONIMIZADO_FOLDER, 'archivos_anonimizados.zip')
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, _, files in os.walk(ANONIMIZADO_FOLDER):
            for file in files:
                if file.endswith('.dcm'):  # Solo incluir archivos DICOM
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.basename(file_path))

    # Enviar el archivo ZIP al cliente
    return send_file(zip_path, as_attachment=True, download_name='archivos_anonimizados.zip')

@app.route("/render/<render>")
def render(render):
    global panel_vtk
    image = app.config.get('Image', None)

    if image is None or image.size == 0:
        return "❌ No hay imagen cargada o está vacía", 400

    if image.ndim != 3:
        return f"❌ Se esperaba una imagen 3D, pero se obtuvo una imagen con shape {image.shape}", 400

    if panel_vtk is None:
        panel_vtk = create_render()
        start_bokeh_server(panel_vtk)

    return render_template(
        "render.html",
        success=(0 if panel_vtk is None else 1),
        render=render,
        max_value_axial=image.shape[0] - 1,
        max_value_sagital=image.shape[1] - 1,
        max_value_coronal=image.shape[2] - 1
    )


@app.route('/image/<view>/<int:layer>')
def get_image(view, layer):
    image = app.config['Image']
    unique_id = app.config["unique_id"]

    # Aplicar Rescale Slope e Intercept
    slope = app.config['dicom_series'][unique_id]["RescaleSlope"]
    intercept = app.config['dicom_series'][unique_id]["RescaleIntercept"]
    image = image * slope + intercept

    # Obtener el espaciado
    slice_thickness = app.config['dicom_series'][unique_id]["SliceThickness"]
    pixel_spacing = app.config['dicom_series'][unique_id]["PixelSpacing"]

    if view == 'axial':
        slice_img = image[layer, :, :]
    elif view == 'sagital':
        slice_img = image[:, layer, :]
    elif view == 'coronal':
        slice_img = image[:, :, layer]
    else:
        return "Vista no válida", 400

    # Ajuste del espaciado a proporciones reales
    if view == 'axial':
        aspect_ratio = pixel_spacing[1] / pixel_spacing[0]
    elif view == 'sagital':
        aspect_ratio = slice_thickness / pixel_spacing[0]
    elif view == 'coronal':
        aspect_ratio = slice_thickness / pixel_spacing[1]

    # Ajustar y mostrar la imagen
    plt.figure(figsize=(6, 6))
    plt.imshow(slice_img, cmap='gray', aspect=aspect_ratio)
    plt.axis('off')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
    plt.close()
    buf.seek(0)
    return send_file(buf, mimetype='image/png')




def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {"nrrd"} #Añadir aqui mas extensiones permitidas para RT Struct

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
    panel_vtk = add_RT_to_plotter()

    return render_template("render.html", max_value_axial=app.config['Image'].shape[0]-1 , max_value_sagital=app.config['Image'].shape[1]-1 , max_value_coronal=app.config['Image'].shape[2]-1)  # Tamaño fijo o dinámico 
        

@app.route('/loadDicomMetadata/<unique_id>')
def load_dicom_metadata(unique_id):
    global selected_dicom_metadata, selected_dicom_slices
    dicom_series = app.config['dicom_series'] 

    # Obtener la lista de archivos DICOM asociados a la serie seleccionada
    dicom_files = dicom_series[unique_id]["ruta_archivos"]
    # Leer los metadatos del primer archivo (puedes ajustar esto según tus necesidades)
    dicom_data = pydicom.dcmread(dicom_files[0], stop_before_pixels=False, force = True)
    
    selected_dicom_metadata = {
        "PatientName": dicom_data.get("PatientName", "Desconocido"),
        "StudyDate": dicom_data.get("StudyDate", "Desconocido"),
        "Modality": dicom_data.get("Modality", "Desconocido"),
        # Agrega más metadatos según sea necesario
    }
    # Leer y ordenar los slices según el InstanceNumber
    slices = []
    for file in dicom_files:
        dicom_data = pydicom.dcmread(file, stop_before_pixels=False)
        instance_number = int(dicom_data.get("InstanceNumber", 0))
        pixel_array = dicom_data.pixel_array  # Obtener el array de píxeles
        slices.append((instance_number, pixel_array))

    # Ordenar los slices por InstanceNumber
    slices.sort(key=lambda x: x[0])
    selected_dicom_slices = np.array([slice[1] for slice in slices]) # Convertir a numpy array
    app.config['dicom_series'][unique_id]["slices"] = selected_dicom_slices

    # Devolver los metadatos y slices como JSON
    return jsonify({
        "metadata": str(selected_dicom_metadata["PatientName"]),
        #"slices": selected_dicom_slices,  # Convertir a lista para JSON
    })


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