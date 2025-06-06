#Python
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, Response
import tempfile
import zipfile
from collections import defaultdict
import numpy as np
import pyvista as pv
import panel as pn
import os
import pydicom
import nrrd

import dash
from dash import html, dcc, Input, Output, State
import dash_vtk
from dash_extensions.enrich import DashProxy, MultiplexerTransform

os.chdir("C:/Users/Alber/OneDrive/Escritorio/flask test/v2")

app = Flask(__name__)

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

pn.extension('vtk')  # Activar la extensión VTK de Panel


def create_render():
    global plotter
    global grid_dicom
    volume = ((app.config['Image'] < 200)*1).astype(np.int16) # Asegúrate de que 'Image' es un array NumPy 3D

    unique_id = app.config["unique_id"]
    # Crear el volumen a partir de los datos de la imagen
    grid = pv.ImageData()

    grid.dimensions = np.array(volume.shape) + 1

    grid.origin = app.config['dicom_series'][unique_id]["ImagePositionPatient"]  # The bottom left corner of the data set
    grid.spacing = (app.config['dicom_series'][unique_id]["SliceThickness"], app.config['dicom_series'][unique_id]["PixelSpacing"][0], app.config['dicom_series'][unique_id]["PixelSpacing"][1])  # These are the cell sizes along each axis
    #print(app.config['dicom_series'][unique_id]["PixelSpacing"])
    #print(app.config['dicom_series'][unique_id]["SliceThickness"])


    grid.cell_data["values"] = volume.flatten(order="F")
    # Crear la visualización
    plotter = pv.Plotter()
    plotter.add_volume(grid, cmap=['green', 'red', 'blue'] ,ambient = 0.5, shade=True, show_scalar_bar = True, opacity="sigmoid_2", )
    grid_dicom = grid
    # Usar Panel para mostrar el gráfico de PyVista
    panel_vtk = pn.pane.VTK(plotter.ren_win,  width=400, height=500)
    
    return panel_vtk


def add_RT_to_plotter():
    global plotter
    global grid
    RT_Image = app.config['RT']
    # Crear el volumen a partir de los datos de la imagen
    grid = pv.ImageData()
    print(RT_Image.shape)
    grid.dimensions = np.array(RT_Image.shape) + 1

    grid.cell_data["values"] = RT_Image.flatten(order="F")    
    plotter.add_volume(grid, cmap=['green', 'red', 'blue'] ,ambient = 0.5, shade=True, show_scalar_bar = True, opacity="sigmoid_2", )
    plotter.render()
    panel_vtk.object = plotter.ren_win 


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


@app.route('/')
def home():
    return render_template('home.html')

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
    # Crear un nuevo cubo si no existe
    if panel_vtk is None and app.config['Image'].any():
        panel_vtk = create_render()
        start_bokeh_server(panel_vtk)

    return render_template("render.html", success=(lambda: 0 if type(panel_vtk)==None else 1), render=render)  # Tamaño fijo o dinámico

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {"nrrd"} #Añadir aqui mas extensiones permitidas para RT Struct

@app.route("/upload_RT", methods=["POST"])
def upload_RT():
    if 'file' not in request.files:
        return "No se encontró el archivo", 400  # Respuesta de error

    file = request.files["file"]

    if file.filename == '':
        return "Nombre de archivo inválido", 400

    # Guardar el archivo en la carpeta de uploads
    filepath = os.path.join("uploaded_RT", file.filename)
    file.save(filepath)
    app.config['RT'], _ = nrrd.read(filepath)
    add_RT_to_plotter()
    # Leer el archivo NRRD
    #try:
    #    app.config['RT'] = nrrd.read(filepath)
    #    #return jsonify({"message": f"Archivo {file.filename} subido y leído correctamente!"}), 200
    #    return Response(status=200) 
    #except Exception as e:
    #    #return jsonify({"error": f"Error al leer el archivo NRRD: {str(e)}"}), 500
    #    return Response(status=500)
    return render_template("render.html", success=(lambda: 0 if type(panel_vtk)==None else 1), render=render) 
        

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



if __name__ == '__main__':
    app.run(debug=True, port=5001)
