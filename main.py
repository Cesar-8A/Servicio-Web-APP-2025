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
from matplotlib.colors import LinearSegmentedColormap

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
    """
    Actualiza el 3D. (Lógica Ivan + Mejoras Visuales Luis)
    """
    plotter = user_data.get('vtk_plotter')
    panel_vtk = user_data.get('vtk_panel')
    grid = user_data.get('grid_full') 
    
    if not plotter or not panel_vtk or grid is None: return

    # Recuperamos el colormap actual (o 'bone' por defecto)
    current_cmap = user_data.get('current_cmap', 'bone')

    plotter.clear()

    if mode == 'isosurface':
        try:
            surface_bone = grid.contour([175]) 
            surface_skin = grid.contour([-200]) 
            plotter.add_mesh(surface_bone, color="white", smooth_shading=True, name="bone")
            plotter.add_mesh(surface_skin, color="peachpuff", opacity=0.5, smooth_shading=True, name="skin")
        except:
            plotter.add_volume(grid, cmap=current_cmap, opacity="linear", blending="composite")

    elif mode == 'mip':
        plotter.add_volume(grid, cmap=current_cmap, opacity="linear", blending="maximum")

    elif mode == 'mip_inverted':
        # Forzamos el mapa de color invertido si no lo está ya
        cmap_inv = f"{current_cmap}_r" if not current_cmap.endswith('_r') else current_cmap
        plotter.add_volume(grid, cmap=cmap_inv, opacity="linear", blending="maximum")
    # ------------------------------------

    else: # Volume
        plotter.add_volume(grid, cmap=current_cmap, opacity="linear", blending="composite")

    # Re-dibujar RT Struct si existe (Lógica de Ivan intacta)
    if 'RT' in user_data and 'RT_aligned' in user_data:
        add_RT_to_plotter(user_data)

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
    user_data['last_polygon_operation'] = None  # For 1-level undo

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
    """
    Histograma Estilo ITK-SNAP:
    - Rango fijo: -1024 a 1000.
    - Resolución: 300 bins (rectángulos).
    """
    user_data = get_user_data()
    image = user_data.get('Image')
    if image is None: return jsonify({"error": "No hay imagen"}), 404
    try:
        pixel_data = image.flatten()
        
        # 1. Configuración Estricta solicitada
        min_hu, max_hu = -1024, 1000
        num_bins = 300 # Cantidad de rectángulos

        # 2. Filtrar datos dentro del rango solicitado
        # Los valores fuera de este rango se ignoran para el gráfico (como en ITK-SNAP)
        valid_pixels = pixel_data[(pixel_data >= min_hu) & (pixel_data <= max_hu)]

        # 3. Calcular histograma con 300 bins exactos
        counts, bin_edges = np.histogram(valid_pixels, bins=num_bins, range=[min_hu, max_hu])
        
        # Segmentos anatómicos (Se mantienen igual para la info extra)
        segments = {
            "Aire": int(np.sum(valid_pixels < -300)),
            "Grasa": int(np.sum((valid_pixels >= -120) & (valid_pixels < -30))),
            "Tejido": int(np.sum((valid_pixels >= 30) & (valid_pixels < 60))),
            "Hueso": int(np.sum(valid_pixels > 300))
        }

        return jsonify({
            "mode": "tissue", # Usamos tissue para activar el modo de dibujo normal
            "counts": counts.tolist(),
            "bin_edges": bin_edges.tolist(),
            "segments": segments,
            "range": [min_hu, max_hu] # Enviamos el rango explícito
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_dicom_metadata')
def get_dicom_metadata():
    """
    Devuelve metadatos técnicos COMPLETOS para la ficha técnica.
    """
    user_data = get_user_data()
    uid = user_data.get('unique_id')
    if not uid: return jsonify({"error": "No data"}), 400
    try:
        files = user_data['dicom_series'][uid]["ruta_archivos"]
        ds = pydicom.dcmread(files[0], stop_before_pixels=True)
        
        # Recuperar geometría (Necesaria para Inspector, pero oculta en tabla)
        grid = user_data.get('grid_full')
        if grid:
            spacing = list(grid.spacing) 
            origin = list(grid.origin)
        else:
            spacing = [1.0, 1.0, 1.0]
            origin = [0.0, 0.0, 0.0]
        
        # --- DICCIONARIO COMPLETO (En Español) ---
        metadata = {
            "Paciente": str(ds.get("PatientName", "Anónimo")), 
            "ID Paciente": str(ds.get("PatientID", "-")),
            "Modalidad": str(ds.get("Modality", "N/A")), 
            "Fecha Estudio": str(ds.get("StudyDate", "N/A")),
            "Institución": str(ds.get("InstitutionName", "-")),
            "Fabricante": str(ds.get("Manufacturer", "-")),
            "Modelo": str(ds.get("ManufacturerModelName", "-")),
            "KVp (Voltaje)": str(ds.get("KVP", "-")),
            "mA (Corriente)": str(ds.get("XRayTubeCurrent", "-")),
            "Tiempo Exp.": str(ds.get("ExposureTime", "-")),
            "Espesor Corte": f"{ds.get('SliceThickness', 0)} mm",
            "Ubicación": f"{ds.get('SliceLocation', '-')}",
            "Matriz": f"{ds.get('Rows', 0)} x {ds.get('Columns', 0)}",
            
            # Datos técnicos internos (El JS los filtra para no mostrarlos en la tabla)
            "Spacing": spacing, 
            "Origin": origin
        }
        return jsonify(metadata)
    except Exception as e:
        print(f"Error metadata: {e}") 
        return jsonify({"error": "Error"}), 500

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
    user_data = get_user_data()
    data = request.json
    
    # Guardamos los nuevos valores
    new_mode = data.get('mode')
    new_cmap = data.get('cmap') 
    
    user_data['render_mode'] = new_mode
    if new_cmap: user_data['current_cmap'] = new_cmap 

    if 'vtk_plotter' in user_data:
        update_3d_render(user_data, mode=new_mode)
    
    return jsonify({"status": "success"})


@app.route('/image/<view>/<int:layer>')
def get_image(view, layer):
    user_data = get_user_data()
    ww = request.args.get('ww', 400, type=float)
    wc = request.args.get('wc', 40, type=float)
    cmap = request.args.get('cmap', 'gray') # NUEVO PARÁMETRO

    img2d, w_px, h_px = _slice_2d_and_target_size(view, layer, user_data)
    if img2d is None: return "Error", 400

    slope = user_data.get("slope", 1.0); intercept = user_data.get("intercept", 0.0)
    hu2d = (img2d.astype(np.float32) * slope) + intercept

    # Aplicar ventana (Normalizar 0 a 1 para Matplotlib)
    lower, upper = wc - ww/2, wc + ww/2
    img_norm = (np.clip(hu2d, lower, upper) - lower) / (upper - lower) if upper > lower else np.zeros_like(hu2d)
    
    # Calcular Aspect Ratio
    dx, dy, dz = _extract_spacing_for_series(user_data.get("unique_id"), user_data)
    v_lower = view.lower()
    if v_lower == "axial": display_w, display_h = w_px, h_px
    else: display_w, display_h = w_px, int(h_px * (dz/dx))

    fig, ax = plt.subplots(figsize=(display_w/100, display_h/100), dpi=100)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    
    # 1. DIBUJAR BASE CON COLORMAP (Lógica Luis)
    ax.imshow(img_norm, cmap=cmap, vmin=0, vmax=1, interpolation="lanczos", aspect='auto')
    ax.axis("off")

    # 2. OVERLAY RT STRUCT (Lógica Ivan - SE MANTIENE)
    if 'RT_aligned' in user_data:
        try:
            rt = user_data['RT_aligned']
            if v_lower == 'axial': seg = rt[layer, :, :]
            elif v_lower in ['sagital', 'sagittal']: seg = rt[:, :, layer]
            elif v_lower == 'coronal': seg = rt[:, layer, :]
            ax.imshow(ma.masked_where(seg==0, seg), cmap='Reds', alpha=0.8, aspect='auto', interpolation="nearest")
        except: pass
        
    # 3. OVERLAY SEGMENTACIÓN MANUAL (Lógica Ivan - SE MANTIENE)
    if user_data.get('segmentation_mask') is not None:
        try:
            mask = user_data['segmentation_mask']
            if v_lower == 'axial': seg = mask[layer, :, :]
            elif v_lower in ['sagital', 'sagittal']: seg = mask[:, :, layer]
            elif v_lower == 'coronal': seg = mask[:, layer, :]
            # Create custom cyan colormap (exact match with frontend #00FFFF)
            cyan_cmap = LinearSegmentedColormap.from_list('cyan', ['#000000', '#00FFFF'])
            ax.imshow(ma.masked_where(seg==0, seg), cmap=cyan_cmap, vmin=0, vmax=512, alpha=0.6, aspect='auto', interpolation='nearest')
        except: pass

    buf = BytesIO()
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
    if view == "axial": z, yy, xx = index, int(round(y / max(1e-8, s_ax))), int(round(x))
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

    # --- STORE OPERATION FOR UNDO (before modifying mask) ---
    # Store a snapshot of the mask before this operation
    user_data['last_polygon_operation'] = {
        'view': view,
        'layer': layer,
        'vertices': vertices,
        'mode': mode,
        'mask_before': seg_mask.copy()  # Full snapshot for 1-level undo
    }

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

@app.route("/undo_last_polygon", methods=["POST"])
def undo_last_polygon():
    """Undoes the last polygon operation by restoring the mask snapshot."""
    user_data = get_user_data()
    last_op = user_data.get('last_polygon_operation')

    if last_op is None:
        return jsonify({"status": "error", "message": "No operation to undo"}), 400

    seg_mask = user_data.get('segmentation_mask')
    if seg_mask is None:
        return jsonify({"status": "error", "message": "No segmentation mask found"}), 400

    try:
        # Restore mask to state before last polygon
        mask_before = last_op.get('mask_before')
        if mask_before is not None:
            # Copy the snapshot back to the active mask
            np.copyto(seg_mask, mask_before)

            # Clear the last operation (can only undo once)
            user_data['last_polygon_operation'] = None

            return jsonify({"status": "success", "message": "Last polygon undone"})
        else:
            return jsonify({"status": "error", "message": "Snapshot not found"}), 500

    except Exception as e:
        return jsonify({"status": "error", "message": f"Undo failed: {str(e)}"}), 500

@app.route("/clear_segmentation", methods=["POST"])
def clear_segmentation():
    """Clears the segmentation mask by filling it with zeros."""
    user_data = get_user_data()
    seg_mask = user_data.get('segmentation_mask')

    if seg_mask is not None:
        seg_mask.fill(0)
        # Clear undo history when clearing all
        user_data['last_polygon_operation'] = None
        return jsonify({"status": "success", "message": "Segmentation cleared"})

    return jsonify({"status": "error", "message": "No segmentation mask found"}), 400

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