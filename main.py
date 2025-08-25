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

#os.chdir("c:\\Users\\jesus\\Desktop\\Cucei\\SERVICIO\\Servicio-Web-APP-2025")
os.chdir("C:\\Users\\lozan\\OneDrive\\Escritorio\\Servicio-Web-APP-2025")

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
    """
    Genera la escena 3D (piel + hueso) con PyVista y retorna
    un Panel (pn.Column) responsivo que contiene el canvas VTK + slider de opacidad.
    """

    global plotter, skin_actor, slider, grid_dicom, panel_vtk

    # Validaciones mínimas
    if app.config.get('Image') is None or not app.config['Image'].size:
        raise RuntimeError("No hay volumen cargado en app.config['Image'].")

    if app.config.get('dicom_series') is None:
        raise RuntimeError("No hay metadatos DICOM en app.config['dicom_series'].")

    unique_id = app.config.get("unique_id")
    if unique_id is None or unique_id not in app.config['dicom_series']:
        raise RuntimeError("unique_id inválido o no establecido en app.config['unique_id'].")

    # ========================
    # 1) Preparación de volúmenes binarios (hueso/piel)
    # ========================
    # Volumen en HU (ya lo guardas entero en Image tras process_selected_dicom)
    vol = app.config['Image'].astype(np.int16, copy=False)

    # Umbrales sencillos (ajústalos a tu dataset)
    volume_bone = (vol > 175).astype(np.int16)        # hueso
    volume_skin = ((vol > -200) & (vol < 0)).astype(np.int16)  # piel

    # ========================
    # 2) Espacio físico (origen y spacing) desde la serie DICOM seleccionada
    # ========================
    ds_meta = app.config['dicom_series'][unique_id]
    origin = ds_meta["ImagePositionPatient"]  # [x, y, z] de la primera slice
    # Nota: Tu orden es (Z, Y, X) para vol, así que spacing debe seguir ese orden:
    spacing = (
        float(ds_meta.get("SliceThickness", 1.0)),     # eje Z (índice 0)
        float(ds_meta["PixelSpacing"][0]),             # eje Y (índice 1)
        float(ds_meta["PixelSpacing"][1])              # eje X (índice 2)
    )

    # ========================
    # 3) Construcción de grids y superficies (isosuperficies)
    # ========================
    def make_surface(binary_volume):
        grid = pv.ImageData()
        # IMPORTANTE: PyVista/VTK esperan dimensiones +1
        grid.dimensions = np.array(binary_volume.shape) + 1  # (nz, ny, nx) + 1
        grid.origin = origin
        grid.spacing = spacing
        # Los valores van como celdas; usar orden Fortran para mantener ejes
        grid.cell_data["values"] = binary_volume.flatten(order="F")
        grid = grid.cell_data_to_point_data()
        surf = grid.contour([0.5])  # isosuperficie de la binaria
        return grid, surf

    grid_bone, surface_bone = make_surface(volume_bone)
    grid_skin, surface_skin = make_surface(volume_skin)

    # Guardar grid_skin como referencia para segmentaciones (RT) posteriores
    grid_dicom = grid_skin

    # ========================
    # 4) Render con PyVista
    # ========================
    plotter = pv.Plotter(off_screen=True)
    plotter.set_background("black")

    # Hueso (blanco brillante)
    plotter.add_mesh(
        surface_bone,
        color="white",
        smooth_shading=True,
        ambient=0.3,
        specular=0.4,
        specular_power=10,
    )
    # Piel (semi-transparente)
    skin_actor = plotter.add_mesh(
        surface_skin,
        color="peachpuff",
        opacity=0.5,
        name="skin",
        smooth_shading=True,
    )

    plotter.view_isometric()
    plotter.show_axes()

    # ========================
    # 5) Panel VTK responsivo + slider
    # ========================
    # ✅ Pane VTK sin medidas fijas: se estira con el contenedor (iframe)
    panel_vtk = pn.pane.VTK(plotter.ren_win, sizing_mode="stretch_both")

    slider = pn.widgets.FloatSlider(
        name="Opacidad de la piel",
        start=0.0, end=1.0, step=0.05, value=0.5
    )

    def update_opacity(event):
        try:
            skin_actor.GetProperty().SetOpacity(float(event.new))
            # Forzar actualización del pane
            panel_vtk.param.trigger('object')
        except Exception:
            pass

    slider.param.watch(update_opacity, 'value')

    # ✅ Contenedor responsivo
    return pn.Column(panel_vtk, slider, sizing_mode="stretch_both")


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

################################################################################################################
# Rutas principales de la aplicación
@app.route("/render/<render>")
def render(render):
    import numpy as np
    global panel_vtk

    vol = app.config.get('Image')

    # Si no hay volumen o está vacío → muestra mensaje y no calcule sliders
    if vol is None or not getattr(vol, "size", 0):
        # Intenta recuperar desde dicom_series si ya cargaste metadatos/slices
        uid = app.config.get("unique_id")
        ds = app.config.get("dicom_series")
        if uid and ds and isinstance(ds.get(uid, {}).get("slices", None), np.ndarray):
            vol = ds[uid]["slices"]
            # Aplica HU solo si NO lo habías hecho ya
            slope = float(ds[uid].get("RescaleSlope", 1.0))
            intercept = float(ds[uid].get("RescaleIntercept", 0.0))
            vol = vol.astype(np.float32) * slope + intercept
            app.config["Image"] = vol.astype(np.int16)

    # Si sigue sin haber volumen, renderiza la plantilla en modo "sin imagen"
    if vol is None or not getattr(vol, "size", 0):
        return render_template("render.html", success=0)

    # Asegura que sea un arreglo numpy
    vol = np.asarray(app.config["Image"])
    # Si es 2D (un solo corte), conviértelo en 3D con Z=1
    if vol.ndim == 2:
        vol = vol[np.newaxis, ...]           # (1, rows, cols)
        app.config["Image"] = vol            # guarda la versión 3D
    elif vol.ndim != 3:
        # Cualquier otra cosa no soportada → muestra modo sin imagen
        return render_template("render.html", success=0)

    nz, ny, nx = vol.shape

    # Levanta Panel/VTK si hace falta y hay datos
    if panel_vtk is None and nz > 0 and ny > 0 and nx > 0:
        panel_vtk = create_render()
        start_bokeh_server(panel_vtk)

    return render_template(
        "render.html",
        success=1,
        render=render,
        max_value_axial=max(nz - 1, 0),
        max_value_sagital=max(ny - 1, 0),
        max_value_coronal=max(nx - 1, 0),
    )

"""
@app.route('/image/<view>/<int:layer>')
def get_image(view, layer):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import io

    vol = app.config.get('Image')
    if vol is None or not getattr(vol, "size", 0):
        return "No hay volumen cargado", 400

    unique_id = app.config.get("unique_id")
    meta = app.config['dicom_series'][unique_id]

    # Espaciados físicos
    slice_thickness = float(meta.get("SliceThickness", 1.0))
    ps = meta.get("PixelSpacing", [1.0, 1.0])
    row_spacing = float(ps[0])  # Y
    col_spacing = float(ps[1])  # X

    vol = np.asarray(vol)
    if vol.ndim == 2:
        vol = vol[np.newaxis, ...]  # (Z=1, Y, X)

    nz, ny, nx = vol.shape  # (Z, Y, X)

    # Selección de corte y extents físicos (xmin, xmax, ymin, ymax)
    if view == 'axial':
        layer = 0 if nz == 1 else max(0, min(layer, nz - 1))
        img = vol[layer, :, :]
        extent = [0, nx * col_spacing, 0, ny * row_spacing]  # X·dx, Y·dy
    elif view == 'sagital':
        layer = max(0, min(layer, ny - 1))
        img = vol[:, layer, :]  # (Z, X)
        extent = [0, nx * col_spacing, 0, nz * slice_thickness]  # X·dx, Z·dz
    elif view == 'coronal':
        layer = max(0, min(layer, nx - 1))
        img = vol[:, :, layer]  # (Z, Y)
        extent = [0, ny * row_spacing, 0, nz * slice_thickness]  # Y·dy, Z·dz
    else:
        return "Vista no válida", 400

    img = img.astype(np.float32)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(img, cmap='gray', origin='lower', extent=extent)  # <- extents físicos
    ax.set_aspect('equal')                                      # <- pixels cuadrados en espacio físico
    ax.axis('off')
    fig.subplots_adjust(0, 0, 1, 1)                             # <- sin márgenes

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100)  # <- sin bbox_inches='tight'
    plt.close(fig)
    buf.seek(0)
    return send_file(buf, mimetype='image/png')"""
    
@app.route('/image/<view>/<int:layer>')
def get_image(view, layer):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import io

    vol = app.config.get('Image')
    if vol is None or not getattr(vol, "size", 0):
        return "No hay volumen cargado", 400

    vol = np.asarray(vol)
    if vol.ndim == 2:
        vol = vol[np.newaxis, ...]  # (1, Y, X)

    nz, ny, nx = vol.shape  # (Z, Y, X)

    # Selección del corte
    if view == 'axial':
        layer = max(0, min(layer, nz - 1))
        img = vol[layer, :, :]
    elif view == 'sagital':
        layer = max(0, min(layer, ny - 1))
        img = vol[:, layer, :]
    elif view == 'coronal':
        layer = max(0, min(layer, nx - 1))
        img = vol[:, :, layer]
    else:
        return "Vista no válida", 400

    img = img.astype(np.float32)

    # Render: usamos imshow directo, sin extent y sin márgenes
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(img, cmap='gray', origin='lower', aspect='auto')
    ax.axis('off')
    fig.subplots_adjust(0, 0, 1, 1)  # ocupa todo el canvas

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight', pad_inches=0)
    plt.close(fig)
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
