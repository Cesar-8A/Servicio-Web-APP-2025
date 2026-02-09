# --- 1. IMPORTACIONES DE LIBRERÍAS ---
# Flask y extensiones para la aplicación web y formularios
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from flask import session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm, CSRFProtect
from flask_wtf.csrf import generate_csrf
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, EqualTo

# Utilidades del sistema y manejo de archivos
import os
import tempfile
import zipfile
from collections import defaultdict
from uuid import uuid4
from io import BytesIO

# Librerías para procesamiento científico y de imágenes
import numpy as np
import numpy.ma as ma
import pydicom  # Para leer archivos DICOM
import nrrd     # Para leer archivos NRRD (RT Struct)

# Librerías de visualización
import pyvista as pv
import panel as pn
import matplotlib
matplotlib.use('Agg') # Modo no interactivo para servidores
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

# --- CONFIGURACIÓN INICIAL DE PYVISTA ---
pv.OFF_SCREEN = True # Asegura que PyVista no intente crear ventanas visibles
pv.global_theme.jupyter_backend = 'static' # Usa un motor gráfico que no depende de la pantalla

# --- 2. CONFIGURACIÓN DE LA APLICACIÓN FLASK ---
app = Flask(__name__)

# Claves secretas para seguridad de la sesión y formularios
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_SECRET_KEY'] = os.environ.get("WTF_CSRF_SECRET_KEY", app.secret_key)
csrf = CSRFProtect(app)

# --- 3. SISTEMA DE SESIÓN PARA MÚLTIPLES USUARIOS ---

# Diccionario global que funciona como un almacén en memoria para los datos de cada sesión
SERVER_SIDE_SESSION_STORE = {}

def get_user_data():
    """
    Gestiona y recupera el diccionario de datos para el usuario actual.
    Si el usuario es nuevo, le asigna un ID único y crea un espacio para sus datos.
    """
    if 'user_session_id' not in session:
        user_id = str(uuid4())
        session['user_session_id'] = user_id
        SERVER_SIDE_SESSION_STORE[user_id] = {}
    user_id = session['user_session_id']
    # setdefault asegura que si el user_id se perdió por alguna razón, se cree un dict vacío
    return SERVER_SIDE_SESSION_STORE.setdefault(user_id, {})

# --- 4. CONFIGURACIÓN Y VARIABLES GLOBALES DE LA APP ---

# Inyecta variables globales en todas las plantillas HTML para saber si el usuario está logueado
@app.context_processor
def inject_user_and_csrf():
    return {
        'user_logged_in': session.get('user_logged_in', False),
        'user_initials': session.get('user_initials', ''),
        'csrf_token': generate_csrf
    }

# Definición de carpetas para almacenar archivos subidos
UPLOAD_FOLDER = 'uploads'
UPLOAD_FOLDER_NRRD = 'upload_nrrd'
ANONIMIZADO_FOLDER = os.path.join(os.getcwd(), 'anonimizado')
# Crea las carpetas si no existen al iniciar la aplicación
for folder in [UPLOAD_FOLDER, UPLOAD_FOLDER_NRRD, ANONIMIZADO_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Inicialización de Panel y Bokeh para la vista 3D
pn.extension('vtk')
bokeh_server_started = False
def start_bokeh_server(panel_layout):
    """Inicia el servidor de Bokeh en un hilo separado si aún no se ha iniciado."""
    global bokeh_server_started
    if not bokeh_server_started:
        pn.serve({'/panel': panel_layout}, show=False, allow_websocket_origin=["*"], port=5010, threaded=True)
        bokeh_server_started = True

# --- 5. LÓGICA DE VISUALIZACIÓN Y PROCESAMIENTO DICOM ---

def create_or_get_plotter(user_data):
    """
    Inicializa el plotter, procesa el volumen 3D y configura el panel.
    """
    if 'vtk_panel_column' in user_data:
        return user_data['vtk_panel_column']

    # --- 1. CREAR EL GRID (VOLUMEN 3D) ---
    # Recuperamos la imagen procesada (HU)
    dicom_image = user_data.get('Image', np.array([]))
    if dicom_image.size == 0: return None

    # Recuperamos metadatos espaciales para que no se vea aplastado
    unique_id = user_data.get("unique_id")
    series_info = user_data.get('dicom_series', {}).get(unique_id, {})
    
    # Valores por defecto seguros
    origin = series_info.get("ImagePositionPatient", [0,0,0])
    spacing_xy = series_info.get("PixelSpacing", [1, 1])
    spacing_z = series_info.get("SliceThickness", 1)
    spacing = (spacing_z, spacing_xy[0], spacing_xy[1])

    # Creamos el objeto PyVista (ImageData) con el volumen completo
    grid_full = pv.ImageData(dimensions=np.array(dicom_image.shape) + 1, origin=origin, spacing=spacing)
    grid_full.cell_data["values"] = dicom_image.flatten(order="F")
    grid_full = grid_full.cell_data_to_point_data() # Necesario para contornos y volumen
    
    # GUARDAMOS EL GRID EN LA SESIÓN
    user_data['grid_full'] = grid_full
    # -------------------------------------

    # Configuración inicial del plotter
    plotter = pv.Plotter(off_screen=True)
    plotter.set_background("black")
    
    panel_vtk = pn.pane.VTK(plotter.ren_win, width=400, height=500, name='vtk_pane')
    panel_column = pn.Column(panel_vtk)
    
    # Guardamos los componentes en la sesión
    user_data.update({
        'vtk_plotter': plotter,
        'vtk_panel': panel_vtk,
        'vtk_panel_column': panel_column
    })
    
    # Aplicamos el renderizado inicial
    initial_mode = user_data.get('render_mode', 'isosurface')
    update_3d_render(user_data, mode=initial_mode)
    
    return panel_column

def update_3d_render(user_data, mode):
    """Actualiza el renderizado 3D usando el volumen completo guardado."""
    plotter = user_data.get('vtk_plotter')
    panel_vtk = user_data.get('vtk_panel')
    
    # Recuperamos el grid completo que creamos arriba
    grid = user_data.get('grid_full') 
    
    if not plotter or not panel_vtk or grid is None:
        print("Error: No se encontró el volumen 3D (grid_full) para renderizar.")
        return

    # Limpiar la escena anterior
    plotter.clear()

    # Dibujar según el modo
    if mode == 'isosurface':
        try:
            # Umbrales aproximados: Hueso > 175, Piel entre -200 y 0
            surface_bone = grid.contour([175]) 
            surface_skin = grid.contour([-200]) 
            
            plotter.add_mesh(surface_bone, color="white", smooth_shading=True, name="bone")
            plotter.add_mesh(surface_skin, color="peachpuff", opacity=0.5, smooth_shading=True, name="skin")
        except Exception as e:
            print(f"Error en isosurface: {e}")
            # Fallback si falla el contorno
            plotter.add_volume(grid, cmap="bone", opacity="linear", blending="composite")

    elif mode == 'mip':
        # Maximum Intensity Projection (Esqueleto brillante)
        plotter.add_volume(grid, cmap="bone", opacity="linear", blending="maximum")

    else: # 'Volume Rendering'
        # Renderizado volumétrico estándar (Transparente)
        plotter.add_volume(grid, cmap="bone", opacity="linear", blending="composite")

    # Ajustar cámara y actualizar
    plotter.view_isometric()
    panel_vtk.param.trigger('object')


def add_RT_to_plotter(user_data):
    """
    Intenta añadir la máscara RT aplicando las transformaciones de ejes originales.
    """
    plotter = user_data.get('vtk_plotter')
    panel_vtk = user_data.get('vtk_panel')
    grid_full = user_data.get('grid_full') 
    
    if not all([plotter, panel_vtk, 'RT' in user_data, grid_full]): 
        return False, "Faltan datos base."

    try:
        # 1. Obtener datos crudos
        rt_data = user_data['RT'] 
        
    
        # -----------------------------------------------------

        # 2. Crear la malla a la medida de los datos YA TRANSFORMADOS
        rt_dims = np.array(rt_data.shape) + 1
        
        rt_grid = pv.ImageData(
            dimensions=rt_dims, 
            spacing=grid_full.spacing, 
            origin=grid_full.origin
        )
        
        # 3. Inyección de datos
        # Usamos flatten order="F" (Fortran-style) que es estándar para VTK/PyVista
        rt_grid.cell_data["values"] = rt_data.flatten(order="F")
        
        # Convertir a puntos para el contorno (corrección anterior)
        rt_grid = rt_grid.cell_data_to_point_data()

        # 4. Guardamos para 2D (Overlay)
        # Para el 2D, usamos la misma transformación para que coincida
        user_data['RT_aligned'] = rt_data

        # 5. Crear contorno y añadir
        surface = rt_grid.contour([0.5]) 
        
        plotter.remove_actor("rt_struct") 
        plotter.add_mesh(surface, color="red", opacity=0.5, name="rt_struct", smooth_shading=True)
        
        panel_vtk.param.trigger('object')
        
        msg = "Segmentación cargada (Ejes transformados)."
        return True, msg

    except Exception as e:
        error_msg = f"Error crítico RT: {str(e)}"
        print(error_msg)
        return False, error_msg

def _extract_spacing_for_series(unique_id, user_data):
    """Calcula el espaciado entre píxeles (dx, dy, dz) de forma robusta."""
    files = user_data['dicom_series'][unique_id]["ruta_archivos"]
    dx, dy, dz = 1.0, 1.0, 1.0
    try:
        ds0 = pydicom.dcmread(files[0], stop_before_pixels=True, force=True)
        ps = getattr(ds0, "PixelSpacing", [1.0, 1.0]); dy, dx = float(ps[0]), float(ps[1])
    except Exception: pass
    zs = [float(pydicom.dcmread(p, stop_before_pixels=True, force=True).ImagePositionPatient[2]) for p in files if hasattr(pydicom.dcmread(p, stop_before_pixels=True, force=True), 'ImagePositionPatient')]
    if len(zs) >= 2:
        diffs = np.diff(sorted(zs)); dz = float(np.median(diffs)) if diffs.size > 0 else 1.0
    else:
        try: dz = float(user_data['dicom_series'][unique_id].get("SliceThickness", 1.0))
        except: dz = 1.0
    dx, dy, dz = [val if np.isfinite(val) and val > 0 else 1.0 for val in (dx, dy, dz)]
    return dx, dy, dz

def _compute_view_scales(dx, dy, dz):
    """Calcula factores de escala para que las imágenes no se vean distorsionadas."""
    eps = 1e-8; return max(eps, dy / dx), max(eps, dz / dx), max(eps, dz / dy)

def _slice_2d_and_target_size(view, index, user_data):
    """Extrae un corte 2D de un volumen 3D para una vista y capa específicas."""
    vol = user_data.get("volume_raw"); dims = user_data.get("dims")
    if vol is None or dims is None: return None, None, None
    Z, Y, X = dims
    v = "sagittal" if view.lower() == "sagital" else view.lower()
    # Return actual voxel dimensions - CSS will handle aspect ratio scaling
    if v == "axial" and 0 <= index < Z: img = vol[index, :, :]; w, h = X, Y
    elif v == "coronal" and 0 <= index < Y: img = vol[:, index, :]; w, h = X, Z
    elif v == "sagittal" and 0 <= index < X: img = vol[:, :, index]; w, h = Y, Z
    else: return None, None, None
    return img, max(1, int(w)), max(1, int(h))

def _push_segmentation_state(user_data):
    """Saves current segmentation state to history stack before modifications."""
    seg_mask = user_data.get('segmentation_mask')
    if seg_mask is None:
        return

    # Copy current state
    current_state = np.copy(seg_mask)

    # Get history data
    stack = user_data.get('segmentation_history_stack', [])
    index = user_data.get('segmentation_history_index', -1)
    max_size = user_data.get('segmentation_history_max_size', 20)

    # If user made changes after undoing, truncate forward history
    if index < len(stack) - 1:
        stack = stack[:index + 1]

    # Append current state
    stack.append(current_state)

    # Remove oldest if exceeding max size
    if len(stack) > max_size:
        stack.pop(0)
    else:
        index += 1

    # Update user data
    user_data['segmentation_history_stack'] = stack
    user_data['segmentation_history_index'] = index

def process_dicom_folder(directory, user_data):
    """Lee una carpeta de archivos, los agrupa por series y extrae metadatos clave."""
    dicom_series = defaultdict(lambda: {
        "ruta_archivos": [], "slices": [], "Anonimize": {
            'PatientName': '', 'PatientID': '', 'PatientBirthDate': '', 'PatientSex': '', 'PatientAge': '',
            'StudyDate': '', 'StudyTime': '', 'AccessionNumber': '', 'ReferringPhysicianName': '',
            'MedicalRecordLocator': '', 'InstitutionName': '', 'InstitutionAddress': '',
            'StudyDescription': '', 'SeriesDescription': '', 'OperatorName': '', 'SeriesNumber': '', 'InstanceNumber': ''
        }})
    
    loaded_series = set()
    for file_path in directory:
        try:
            dicom_data = pydicom.dcmread(file_path, force=True)
            unique_id = f"{dicom_data.StudyInstanceUID}-{dicom_data.SeriesInstanceUID}"
            series = dicom_series[unique_id]
            series["ruta_archivos"].append(file_path)

            if unique_id not in loaded_series: # Solo llenar metadatos una vez por serie
                loaded_series.add(unique_id)
                series["paciente"] = str(dicom_data.PatientName)
                series["RescaleSlope"] = dicom_data.RescaleSlope
                series["RescaleIntercept"] = dicom_data.RescaleIntercept
                series["ImagePositionPatient"] = dicom_data.ImagePositionPatient
                series["PixelSpacing"] = dicom_data.PixelSpacing
                series["SliceThickness"] = dicom_data.get("SliceThickness", 1)
                for tag in series["Anonimize"]:
                    if hasattr(dicom_data, tag):
                        value = getattr(dicom_data, tag)
                        series["Anonimize"][tag] = str(value) if value is not None else ''
        except Exception:
            continue

    for uid, series in dicom_series.items():
        if series["ruta_archivos"]:
            dcm = pydicom.dcmread(series["ruta_archivos"][0])
            series["dimensiones"] = (len(series["ruta_archivos"]), dcm.Rows, dcm.Columns)
            series["tipo"] = "3D" if len(series["ruta_archivos"]) > 1 else "2D"

    user_data['dicom_series'] = dict(dicom_series)
    return user_data['dicom_series']
    
# --- 6. RUTAS DE LA APLICACIÓN WEB ---

@app.route("/")
def home():
    """Ruta principal, muestra la página de inicio."""
    return render_template('index.html')

@app.route('/loadDicom', methods=['GET', 'POST'])
def loadDicom():
    """Maneja la subida de la carpeta de archivos DICOM."""
    user_data = get_user_data()
    if request.method == 'POST':
        folder = request.files.getlist('folder')
        if not folder: return redirect(request.url)
        saved_files = []
        for file in folder:
            file_path = os.path.join(UPLOAD_FOLDER, os.path.basename(file.filename))
            file.save(file_path)
            saved_files.append(file_path)
        dicom_series = process_dicom_folder(saved_files, user_data)
        return render_template('resultsTableDicom.html', dicom_series=dicom_series)
    return render_template('loadDicom.html')
    
@app.route('/loadDicomMetadata/<unique_id>')
def load_dicom_metadata(unique_id):
    """Carga los metadatos de la serie seleccionada (llamado por AJAX desde la tabla de resultados)."""
    user_data = get_user_data()
    dicom_series = user_data.get('dicom_series', {})
    if unique_id not in dicom_series: return jsonify({"error": "ID de serie no encontrado"}), 404
    first_file_data = pydicom.dcmread(dicom_series[unique_id]["ruta_archivos"][0], force=True)
    return jsonify({"metadata": str(first_file_data.PatientName)})

@app.route('/process_selected_dicom', methods=['POST'])
def process_selected_dicom():
    """
    Procesa la serie DICOM seleccionada.
    CORRECCIÓN: Actualiza el volumen 3D existente en lugar de borrarlo, 
    para que el servidor no pierda la conexión.
    """
    user_data = get_user_data()
    unique_id = request.json.get('unique_id')
    user_data["unique_id"] = unique_id
    
    if not unique_id or not user_data.get('dicom_series'): 
        return jsonify({"error": "Datos inválidos"}), 400
    
    # 1. Cargar los nuevos datos 2D
    files = user_data['dicom_series'][unique_id]["ruta_archivos"]
    slices = sorted([(int(pydicom.dcmread(f).InstanceNumber), pydicom.dcmread(f).pixel_array) for f in files])
    volume_raw = np.array([s[1] for s in slices])
    user_data['dicom_series'][unique_id]["slices"] = volume_raw
    
    if volume_raw.size == 0: return jsonify({"error": "Serie sin slices"}), 400
    
    # Metadatos básicos
    slope = float(user_data['dicom_series'][unique_id].get("RescaleSlope", 1.0))
    intercept = float(user_data['dicom_series'][unique_id].get("RescaleIntercept", 0.0))
    dx, dy, dz = _extract_spacing_for_series(unique_id, user_data)
    s_ax, s_co, s_sa = _compute_view_scales(dx, dy, dz)
    
    # Actualizar sesión
    user_data.update({
        "volume_raw": volume_raw.astype(np.int16),
        "dims": volume_raw.shape,
        "slope": slope, "intercept": intercept,
        "Image": (volume_raw * slope + intercept).astype(np.int16),
        "scale_axial": s_ax, "scale_coronal": s_co, "scale_sagittal": s_sa
    })

    # Initialize segmentation mask
    dims = volume_raw.shape
    user_data['segmentation_mask'] = np.zeros(dims, dtype=np.uint8)
    user_data['segmentation_active'] = False
    user_data['brush_size'] = 1
    user_data['paint_mode'] = 'paint'

    # Initialize undo/redo history system
    user_data['segmentation_history_stack'] = []
    user_data['segmentation_history_index'] = -1
    user_data['segmentation_history_max_size'] = 20

    # --- CORRECCIÓN CLAVE: REGENERAR EL GRID 3D AQUÍ ---
    # En lugar de borrar 'vtk_panel_column', actualizamos 'grid_full'
    
    series_info = user_data['dicom_series'][unique_id]
    origin = series_info.get("ImagePositionPatient", [0,0,0])
    spacing = (dz, dy, dx) # Z, Y, X (Ajustado a tu lógica de spacing)

    # Crear nuevo grid con el NUEVO paciente
    grid_full = pv.ImageData(dimensions=np.array(volume_raw.shape) + 1, origin=origin, spacing=spacing)
    image_hu = user_data['Image']
    grid_full.cell_data["values"] = image_hu.flatten(order="F")
    grid_full = grid_full.cell_data_to_point_data()
    
    # Guardar el nuevo grid en la sesión
    user_data['grid_full'] = grid_full
    
    # Si el visor 3D ya existía, forzamos su actualización visual AHORA MISMO
    if 'vtk_plotter' in user_data:
        # Limpiamos cualquier RT Struct viejo que hubiera
        user_data.pop('RT', None)
        user_data.pop('RT_aligned', None)
        
        # Redibujamos la escena con el nuevo paciente
        current_mode = user_data.get('render_mode', 'isosurface')
        update_3d_render(user_data, mode=current_mode)
        
    return jsonify({"mensaje": "Ok"})

@app.route('/get_histogram')
def get_histogram():
    """Calcula y devuelve los datos del histograma para la imagen cargada."""
    user_data = get_user_data()
    image = user_data.get('Image') # Usamos la imagen en HU
    if image is None:
        return jsonify({"error": "No hay imagen cargada"}), 404

    try:
        # Usamos la imagen completa para el histograma
        pixel_data = image.flatten()
        
        # Limita el rango para enfocarse en valores clínicamente relevantes y mejorar el rendimiento
        # Puedes ajustar estos valores si trabajas con rangos de HU muy específicos
        min_hu, max_hu = -1024, 3071
        pixel_data = pixel_data[(pixel_data >= min_hu) & (pixel_data <= max_hu)]

        # Calcula el histograma con NumPy
        counts, bin_edges = np.histogram(pixel_data, bins=256, range=[min_hu, max_hu])

        # Devuelve los datos listos para ser usados en el frontend
        return jsonify({
            "counts": counts.tolist(),
            "bin_edges": bin_edges.tolist()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_dicom_metadata')
def get_dicom_metadata():
    """Devuelve los metadatos técnicos del DICOM cargado."""
    user_data = get_user_data()
    unique_id = user_data.get('unique_id')
    dicom_series = user_data.get('dicom_series', {})
    
    if not unique_id or unique_id not in dicom_series:
        return jsonify({"error": "No hay serie cargada"}), 400

    try:
        # Leemos solo el primer archivo para sacar los datos comunes
        first_file_path = dicom_series[unique_id]["ruta_archivos"][0]
        ds = pydicom.dcmread(first_file_path, stop_before_pixels=True, force=True)
        
        # Extraemos los tags con valores por defecto si no existen
        metadata = {
            "Fabricante": str(ds.get("Manufacturer", "N/A")),
            "Modalidad": str(ds.get("Modality", "N/A")),
            "Fecha Estudio": str(ds.get("StudyDate", "N/A")),
            "KVp": str(ds.get("KVP", "-")),
            "mA (Corriente)": str(ds.get("XRayTubeCurrent", "-")),
            "Espesor Corte": f"{ds.get('SliceThickness', 0)} mm",
            "Tamaño Matriz": f"{ds.get('Rows', 0)} x {ds.get('Columns', 0)}"
        }
        return jsonify(metadata)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/render/<render>")
def render(render): 
    """Muestra la página principal del visor con los 4 cuadrantes."""
    user_data = get_user_data()
    image = user_data.get('Image')
    if image is None or image.size == 0:
        return render_template("render.html", success=0)
    
    # Obtiene o crea el plotter y el layout de panel
    panel_layout = create_or_get_plotter(user_data)
    
    # Inicia el servidor de Bokeh si es la primera vez
    if panel_layout:
        start_bokeh_server(panel_layout)
        
    dims = user_data.get("dims", (1, 1, 1))
    # Pasamos la variable 'render' a la plantilla
    current_mode = user_data.get('render_mode', 'isosurface')

    # El cambio clave está aquí: 'render=render_type' se convierte en 'render=render'
    return render_template("render.html", success=1, render=render,
                           max_value_axial=dims[0] - 1,
                           max_value_coronal=dims[1] - 1,
                           max_value_sagital=dims[2] - 1,
                           current_render_mode=current_mode)

@app.route('/update_render_mode', methods=['POST'])
def update_render_mode():
    """
    Recibe una solicitud para cambiar el modo de renderizado 3D y lo aplica.
    """
    user_data = get_user_data()
    new_mode = request.json.get('mode')
    
    if not new_mode or 'vtk_plotter' not in user_data:
        return jsonify({"status": "error", "message": "Datos inválidos o plotter no inicializado."}), 400

    # Llama a la función de actualización
    update_3d_render(user_data, mode=new_mode)
    
    # Guarda la elección del usuario para la próxima vez que cargue la página
    user_data['render_mode'] = new_mode
    
    return jsonify({"status": "success", "message": f"Renderizado cambiado a {new_mode}"})


@app.route('/image/<view>/<int:layer>')
def get_image(view, layer):
    """Genera y devuelve una imagen PNG de un corte 2D específico."""
    user_data = get_user_data()
    # Recibe los parámetros de Window Leveling (brillo/contraste)
    ww = request.args.get('ww', default=400, type=float)
    wc = request.args.get('wc', default=40, type=float)

    img2d, w_px, h_px = _slice_2d_and_target_size(view, layer, user_data)
    if img2d is None: return "Vista o índice no válido", 400
    
    print(f"DEBUG get_image: view={view}, img2d.shape={img2d.shape}, w_px={w_px}, h_px={h_px}, dims={user_data.get('dims')}")
    # Aplica la conversión a Unidades Hounsfield
    slope = user_data.get("slope", 1.0); intercept = user_data.get("intercept", 0.0)
    hu2d = (img2d.astype(np.float32) * slope) + intercept

    # Aplica la fórmula de Window Leveling
    lower_bound = wc - (ww / 2); upper_bound = wc + (ww / 2)
    image_scaled = np.clip(hu2d, lower_bound, upper_bound)
    # Evitar división por cero si ww es 0
    if (upper_bound - lower_bound) > 0:
        image_scaled = (image_scaled - lower_bound) / (upper_bound - lower_bound) * 255.0
    else:
        image_scaled = np.zeros_like(image_scaled)
    image_8bit = image_scaled.astype(np.uint8)

    # Dibuja la imagen con Matplotlib
    dpi = 100.0
    # Calculate display size based on physical scaling
    dx, dy, dz = _extract_spacing_for_series(user_data.get("unique_id"), user_data)

    # Determine aspect ratio based on view
    v_lower = view.lower()
    if v_lower == "axial":
        display_w, display_h = w_px, h_px  # Already square in physical space
    elif v_lower in ["coronal", "sagital", "sagittal"]:
        # Scale height by slice thickness ratio (dz/dx)
        aspect_ratio = dz / dx
        display_w = w_px
        display_h = int(h_px * aspect_ratio)
    else:
        display_w, display_h = w_px, h_px

    print(f"DEBUG matplotlib: dx={dx}, dy={dy}, dz={dz}, aspect_ratio={dz/dx if v_lower in ['coronal','sagital','sagittal'] else 1.0}, display_w={display_w}, display_h={display_h}")

    fig, ax = plt.subplots(figsize=(display_w / dpi, display_h / dpi), dpi=dpi)

    # Remove all margins and padding so axes fill the entire figure
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    # Use 'auto' aspect to let matplotlib stretch to fill the figure
    ax.imshow(image_8bit, cmap="gray", vmin=0, vmax=255, interpolation="lanczos", aspect='auto')
    ax.axis("off")

    # Superpone la máscara de RT Struct si existe
    rt = user_data.get('RT_aligned')
    if rt is not None:
        try:
            v_lower = view.lower()
            seg_slice = None

            # Extract RT slice using SAME indexing as DICOM volume
            # RT_aligned has shape (Z, Y, X) matching volume_raw
            if v_lower == 'axial':
                seg_slice = rt[layer, :, :]      # Shape: (Y, X) - matches DICOM
            elif v_lower in ['sagital', 'sagittal']:
                seg_slice = rt[:, :, layer]      # Shape: (Z, Y) - matches DICOM
            elif v_lower == 'coronal':
                seg_slice = rt[:, layer, :]      # Shape: (Z, X) - matches DICOM

            if seg_slice is not None:
                # Mask out zero values and overlay
                masked_seg = ma.masked_where(seg_slice == 0, seg_slice)
                ax.imshow(masked_seg, cmap='Reds', alpha=0.8, interpolation="nearest", aspect='auto')
        except Exception as e:
            print(f"RT overlay error: {e}")
            pass

    # Overlay segmentation mask if it exists
    seg_mask = user_data.get('segmentation_mask')
    if seg_mask is not None:
        try:
            v_lower = view.lower()
            seg_slice = None

            # Extract segmentation slice using SAME indexing as DICOM volume
            # segmentation_mask has shape (Z, Y, X) matching volume_raw
            if v_lower == 'axial':
                seg_slice = seg_mask[layer, :, :]      # Shape: (Y, X) - matches DICOM
            elif v_lower in ['sagital', 'sagittal']:
                seg_slice = seg_mask[:, :, layer]      # Shape: (Z, Y) - matches DICOM
            elif v_lower == 'coronal':
                seg_slice = seg_mask[:, layer, :]      # Shape: (Z, X) - matches DICOM

            if seg_slice is not None:
                # Mask out zero values and overlay
                masked_seg = ma.masked_where(seg_slice == 0, seg_slice)
                ax.imshow(masked_seg, cmap='Greens', alpha=0.6, interpolation='nearest', aspect='auto')
        except Exception as e:
            print(f"Segmentation overlay error: {e}")
            pass

    # Guarda la imagen en un buffer en memoria y la envía al navegador
    buf = BytesIO()
    # REMOVED bbox_inches='tight' - it was ignoring our figsize!
    fig.savefig(buf, format='png', transparent=True, pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route("/upload_RT", methods=["POST"])
def upload_RT():
    """Maneja la subida de un archivo RT Struct y guarda sus metadatos."""
    user_data = get_user_data()
    
    file = request.files.get("file")
    if not file or file.filename == '':
        return jsonify({"status": "error", "message": "No se seleccionó ningún archivo."}), 400
    
    if not file.filename.lower().endswith('.nrrd'):
        return jsonify({"status": "error", "message": "Formato inválido. Solo se aceptan archivos .nrrd"}), 400

    try:
        filepath = os.path.join(UPLOAD_FOLDER_NRRD, file.filename)
        file.save(filepath)
        
        # --- CAMBIO IMPORTANTE: Leemos y GUARDAMOS el header ---
        rt_data, rt_header = nrrd.read(filepath)
        
        user_data['RT'] = rt_data 
        user_data['RT_header'] = rt_header # <--- Aquí está la clave de la posición
        # -------------------------------------------------------
        
        success, message = add_RT_to_plotter(user_data)
        
        if success:
            return jsonify({"status": "success", "message": message})
        else:
            return jsonify({"status": "error", "message": message}), 500

    except Exception as e:
        return jsonify({"status": "error", "message": f"Error interno: {str(e)}"}), 500

@app.route("/hu_value")
def hu_value():
    """Devuelve el valor HU en una coordenada específica."""
    user_data = get_user_data()
    vol = user_data.get("volume_raw"); dims = user_data.get("dims")
    if vol is None or dims is None: return jsonify({"error": "No hay volumen cargado"}), 500
    try:
        view, x, y, index = request.args.get("view", "").lower(), int(request.args.get("x", "-1")), int(request.args.get("y", "-1")), int(request.args.get("index", "-1"))
    except ValueError: return jsonify({"error": "Parámetros inválidos"}), 400
    Z, Y, X = dims
    if view == "sagital": view = "sagittal" # Compatibilidad
    s_ax, s_co, s_sa = user_data["scale_axial"], user_data["scale_coronal"], user_data["scale_sagittal"]
    if view == "axial": z, yy, xx = index, int(round(y / max(1e-8, s_ax))), x
    elif view == "coronal": z, yy, xx = int(round(y / max(1e-8, s_co))), index, x
    elif view == "sagittal": z, yy, xx = int(round(y / max(1e-8, s_sa))), x, index
    else: return jsonify({"error": "Vista inválida"}), 400
    if not (0 <= z < Z and 0 <= yy < Y and 0 <= xx < X): return jsonify({"error": "Coordenadas fuera de rango"}), 400
    pv = int(vol[z, yy, xx]); hu = int(pv * user_data.get("slope", 1.0) + user_data.get("intercept", 0.0))
    return jsonify({
        "voxel": {"z": z, "y": yy, "x": xx},
        "hu": hu,
        "scales": {"axial": s_ax, "coronal": s_co, "sagittal": s_sa}
    })

@app.route("/paint_voxel", methods=["POST"])
def paint_voxel():
    """Paints or erases voxels in the segmentation mask."""
    user_data = get_user_data()

    # Extract parameters from JSON request
    data = request.json
    view = data.get('view', '').lower()
    xPix = data.get('xPix', -1)
    yPix = data.get('yPix', -1)
    layer = data.get('layer', -1)
    brush_size = data.get('brush_size', 1)
    mode = data.get('mode', 'paint')

    # Validate segmentation mask exists
    seg_mask = user_data.get('segmentation_mask')
    if seg_mask is None:
        return jsonify({"status": "error", "message": "Segmentation mask not initialized"}), 500

    # Get volume dimensions
    dims = user_data.get('dims')
    if dims is None:
        return jsonify({"status": "error", "message": "Volume dimensions not found"}), 500

    Z, Y, X = dims

    # Get scaling factors
    s_ax = user_data.get('scale_axial', 1.0)
    s_co = user_data.get('scale_coronal', 1.0)
    s_sa = user_data.get('scale_sagittal', 1.0)

    # Normalize view name
    if view == "sagital":
        view = "sagittal"

    # Convert pixel coordinates to voxel coordinates (EXACT same logic as /hu_value)
    if view == "axial":
        z = layer
        yy = int(round(yPix / max(1e-8, s_ax)))
        xx = xPix
    elif view == "coronal":
        z = int(round(yPix / max(1e-8, s_co)))
        yy = layer
        xx = xPix
    elif view == "sagittal":
        z = int(round(yPix / max(1e-8, s_sa)))
        yy = xPix
        xx = layer
    else:
        return jsonify({"status": "error", "message": "Invalid view"}), 400

    # Validate voxel coordinates are within bounds
    if not (0 <= z < Z and 0 <= yy < Y and 0 <= xx < X):
        return jsonify({"status": "error", "message": "Coordinates out of range"}), 400

    # Push current state to history before modification
    _push_segmentation_state(user_data)

    # Determine paint value
    if mode == 'paint':
        paint_value = 255
    elif mode == 'erase':
        paint_value = 0
    else:
        return jsonify({"status": "error", "message": "Invalid mode"}), 400

    # Paint a 2D kernel on the current slice only
    radius = brush_size
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            ny = yy + dy
            nx = xx + dx
            if 0 <= ny < Y and 0 <= nx < X:
                seg_mask[z, ny, nx] = paint_value

    return jsonify({"status": "success"})

@app.route("/fill_polygon", methods=["POST"])
def fill_polygon():
    """Fills a polygon region in the segmentation mask."""
    try:
        from skimage.draw import polygon
    except ImportError:
        return jsonify({"status": "error", "message": "scikit-image not installed"}), 500

    user_data = get_user_data()

    # Extract parameters from JSON request
    data = request.json
    view = data.get('view', '').lower()
    layer = data.get('layer', -1)
    vertices = data.get('vertices', [])  # List of {xPix, yPix}
    mode = data.get('mode', 'paint')

    # Validate inputs
    if not vertices or len(vertices) < 3:
        return jsonify({"status": "error", "message": "At least 3 vertices required"}), 400

    seg_mask = user_data.get('segmentation_mask')
    if seg_mask is None:
        return jsonify({"status": "error", "message": "Segmentation mask not initialized"}), 500

    dims = user_data.get('dims')
    if dims is None:
        return jsonify({"status": "error", "message": "Volume dimensions not found"}), 500

    Z, Y, X = dims

    # Get scaling factors
    s_ax = user_data.get('scale_axial', 1.0)
    s_co = user_data.get('scale_coronal', 1.0)
    s_sa = user_data.get('scale_sagittal', 1.0)

    # Normalize view name
    if view == "sagital":
        view = "sagittal"

    # Extract pixel coordinates from vertices
    pixel_x = [v['xPix'] for v in vertices]
    pixel_y = [v['yPix'] for v in vertices]

    # Determine paint value
    if mode == 'paint':
        paint_value = 255
    elif mode == 'erase':
        paint_value = 0
    else:
        return jsonify({"status": "error", "message": "Invalid mode"}), 400

    # Push current state to history before modification
    _push_segmentation_state(user_data)

    # Convert to voxel coordinates and fill based on view
    try:
        if view == "axial":
            # Polygon in X-Y plane at Z = layer
            voxel_x = pixel_x  # Direct mapping
            voxel_y = [int(round(py / max(1e-8, s_ax))) for py in pixel_y]

            # Validate layer
            if not (0 <= layer < Z):
                return jsonify({"status": "error", "message": "Layer out of range"}), 400

            # Get polygon interior points
            rr, cc = polygon(voxel_y, voxel_x, shape=(Y, X))

            # Fill at current Z layer
            seg_mask[layer, rr, cc] = paint_value

        elif view == "coronal":
            # Polygon in X-Z plane at Y = layer
            voxel_x = pixel_x  # Direct mapping
            voxel_z = [int(round(py / max(1e-8, s_co))) for py in pixel_y]

            # Validate layer
            if not (0 <= layer < Y):
                return jsonify({"status": "error", "message": "Layer out of range"}), 400

            # Get polygon interior points (rows=Z, cols=X)
            zz, xx = polygon(voxel_z, voxel_x, shape=(Z, X))

            # Fill at current Y layer
            seg_mask[zz, layer, xx] = paint_value

        elif view == "sagittal":
            # Polygon in Y-Z plane at X = layer
            voxel_y = pixel_x  # xPix maps to Y in sagittal
            voxel_z = [int(round(py / max(1e-8, s_sa))) for py in pixel_y]

            # Validate layer
            if not (0 <= layer < X):
                return jsonify({"status": "error", "message": "Layer out of range"}), 400

            # Get polygon interior points (rows=Z, cols=Y)
            zz, yy = polygon(voxel_z, voxel_y, shape=(Z, Y))

            # Fill at current X layer
            seg_mask[zz, yy, layer] = paint_value

        else:
            return jsonify({"status": "error", "message": "Invalid view"}), 400

        return jsonify({"status": "success"})

    except Exception as e:
        return jsonify({"status": "error", "message": f"Fill failed: {str(e)}"}), 500

@app.route("/clear_segmentation", methods=["POST"])
def clear_segmentation():
    """Clears the segmentation mask by filling it with zeros."""
    user_data = get_user_data()
    seg_mask = user_data.get('segmentation_mask')

    if seg_mask is not None:
        # Push current state to history before clearing
        _push_segmentation_state(user_data)
        seg_mask.fill(0)
        return jsonify({"status": "success", "message": "Segmentation cleared"})

    return jsonify({"status": "error", "message": "No segmentation mask found"}), 400

@app.route("/undo_segmentation", methods=["POST"])
def undo_segmentation():
    """Undoes the last segmentation action by restoring previous state."""
    user_data = get_user_data()

    stack = user_data.get('segmentation_history_stack', [])
    index = user_data.get('segmentation_history_index', -1)
    seg_mask = user_data.get('segmentation_mask')

    # Check if can undo
    if not stack or index <= 0:
        return jsonify({"status": "error", "message": "No hay cambios para deshacer"}), 400

    # Decrement index
    index -= 1
    user_data['segmentation_history_index'] = index

    # Restore state
    if seg_mask is not None and index < len(stack):
        np.copyto(seg_mask, stack[index])

    return jsonify({
        "status": "success",
        "history_index": index,
        "history_length": len(stack)
    })

@app.route("/redo_segmentation", methods=["POST"])
def redo_segmentation():
    """Redoes a previously undone segmentation action."""
    user_data = get_user_data()

    stack = user_data.get('segmentation_history_stack', [])
    index = user_data.get('segmentation_history_index', -1)
    seg_mask = user_data.get('segmentation_mask')

    # Check if can redo
    if not stack or index >= len(stack) - 1:
        return jsonify({"status": "error", "message": "No hay cambios para rehacer"}), 400

    # Increment index
    index += 1
    user_data['segmentation_history_index'] = index

    # Restore state
    if seg_mask is not None and index < len(stack):
        np.copyto(seg_mask, stack[index])

    return jsonify({
        "status": "success",
        "history_index": index,
        "history_length": len(stack)
    })

@app.route("/get_history_state")
def get_history_state():
    """Returns the current state of undo/redo availability."""
    user_data = get_user_data()

    stack = user_data.get('segmentation_history_stack', [])
    index = user_data.get('segmentation_history_index', -1)

    if not stack:
        return jsonify({
            "can_undo": False,
            "can_redo": False,
            "history_length": 0
        })

    can_undo = index > 0
    can_redo = index < len(stack) - 1

    return jsonify({
        "can_undo": can_undo,
        "can_redo": can_redo,
        "history_length": len(stack)
    })

@app.route("/export_segmentation", methods=["POST"])
def export_segmentation():
    """Exports the segmentation mask as an NRRD file."""
    user_data = get_user_data()
    seg_mask = user_data.get('segmentation_mask')

    if seg_mask is None or seg_mask.sum() == 0:
        return jsonify({"status": "error", "message": "No segmentation to export"}), 400

    try:
        # Get spacing information
        unique_id = user_data.get('unique_id')
        dx, dy, dz = _extract_spacing_for_series(unique_id, user_data)

        # Get origin information
        grid_full = user_data.get('grid_full')
        if grid_full is not None:
            origin = grid_full.origin
        else:
            origin = [0, 0, 0]

        # Create NRRD header
        header = {
            'space': 'left-posterior-superior',
            'kinds': ['domain', 'domain', 'domain'],
            'space directions': [[dz, 0, 0], [0, dy, 0], [0, 0, dx]],
            'space origin': origin
        }

        # Create temporary file path
        filepath = os.path.join(ANONIMIZADO_FOLDER, 'segmentation.nrrd')

        # Write NRRD file
        nrrd.write(filepath, seg_mask, header)

        # Return file for download
        return send_file(filepath, as_attachment=True, download_name='segmentation.nrrd')

    except Exception as e:
        return jsonify({"status": "error", "message": f"Export failed: {str(e)}"}), 500

@app.route('/anonimize')
def anonimize():
    """Muestra la página para anonimizar los datos DICOM."""
    user_data = get_user_data()
    dicom_series, unique_id = user_data.get('dicom_series'), user_data.get('unique_id')
    if dicom_series and unique_id:
        return render_template('anonimize.html', dicom_series=dicom_series[unique_id]['Anonimize'], success=1, unique_id=unique_id)
    return render_template('anonimize.html', success=0)

@app.route('/guardar_cambios', methods=['POST'])
def guardar_cambios():
    """Guarda los cambios de anonimización hechos por el usuario."""
    user_data = get_user_data()
    cambios = request.json.get('cambios', {})
    unique_id = user_data.get('unique_id')
    if unique_id and cambios:
        for campo, valor in cambios.items():
            if campo in user_data['dicom_series'][unique_id]['Anonimize']:
                user_data['dicom_series'][unique_id]['Anonimize'][campo] = valor
    return jsonify({"mensaje": "Cambios guardados"})

@app.route('/exportar_dicom', methods=['POST'])
def exportar_dicom():
    """Exporta la serie DICOM actual con los datos de anonimización aplicados."""
    user_data = get_user_data()
    unique_id = user_data.get('unique_id')
    if not unique_id: return jsonify({"error": "Datos inválidos"}), 400
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = os.path.join(tmpdir, "anon"); os.makedirs(out_dir, exist_ok=True)
        for archivo in user_data['dicom_series'][unique_id]["ruta_archivos"]:
            try:
                dicom_data = pydicom.dcmread(archivo)
                for campo, valor in user_data['dicom_series'][unique_id]['Anonimize'].items():
                    if hasattr(dicom_data, campo):
                        data_element = dicom_data.data_element(campo)
                        if data_element:
                            data_element.value = valor
                dicom_data.save_as(os.path.join(out_dir, f"anonimo_{os.path.basename(archivo)}"))
            except Exception: continue
        zip_path = os.path.join(tmpdir, 'archivos_anonimizados.zip')
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for f in os.listdir(out_dir): zipf.write(os.path.join(out_dir, f), f)
        return send_file(zip_path, as_attachment=True, download_name='archivos_anonimizados.zip')

# --- 7. RUTAS DE LOGIN Y REGISTRO ---
class LoginForm(FlaskForm):
    username = StringField('Usuario', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField('Contraseña', validators=[InputRequired(), Length(min=4, max=20)])
    submit = SubmitField('Iniciar sesión')

class RegisterForm(FlaskForm):
    username = StringField('Usuario', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField('Contraseña', validators=[InputRequired(), Length(min=4, max=20)])
    confirm_password = PasswordField('Confirmar contraseña', validators=[InputRequired(), EqualTo('password')])
    submit = SubmitField('Registrarse')

usuarios = {}

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user, password = form.username.data, form.password.data
        if user in usuarios and check_password_hash(usuarios[user], password):
            session['user_logged_in'] = True; session['user_initials'] = user[:2].upper()
            flash('Inicio de sesión exitoso', 'success'); return redirect(url_for('home'))
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user, password = form.username.data, form.password.data
        if user in usuarios: flash('El usuario ya existe', 'danger')
        else:
            usuarios[user] = generate_password_hash(password)
            flash('Registro exitoso. Ahora puedes iniciar sesión.', 'success'); return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
def logout():
    """Limpia la sesión del usuario, incluyendo los datos del visor."""
    user_id = session.get('user_session_id')
    if user_id and user_id in SERVER_SIDE_SESSION_STORE:
        del SERVER_SIDE_SESSION_STORE[user_id]
    session.clear()
    flash('Has cerrado sesión', 'info')
    return redirect(url_for('home'))

# --- 8. INICIO DE LA APLICACIÓN ---
if __name__ == '__main__':
    # Se ejecuta solo cuando el script es el punto de entrada principal
    app.run(debug=True, port=5001)