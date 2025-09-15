# --- 1. IMPORTACIONES DE LIBRERÍAS ---
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from flask import session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm, CSRFProtect
from flask_wtf.csrf import generate_csrf
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, EqualTo
import os, tempfile, zipfile
from collections import defaultdict
from uuid import uuid4
from io import BytesIO
import numpy as np
import numpy.ma as ma
import pydicom
import nrrd
import pyvista as pv
import panel as pn
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

# --- CONFIGURACIÓN INICIAL DE PYVISTA ---
pv.OFF_SCREEN = True
pv.global_theme.jupyter_backend = 'static'

# --- 2. CONFIGURACIÓN DE LA APLICACIÓN FLASK ---
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_SECRET_KEY'] = os.environ.get("WTF_CSRF_SECRET_KEY", app.secret_key)
csrf = CSRFProtect(app)

# --- 3. SISTEMA DE SESIÓN PARA MÚLTIPLES USUARIOS ---
SERVER_SIDE_SESSION_STORE = {}
def get_user_data():
    if 'user_session_id' not in session:
        user_id = str(uuid4())
        session['user_session_id'] = user_id
        SERVER_SIDE_SESSION_STORE[user_id] = {}
    user_id = session['user_session_id']
    return SERVER_SIDE_SESSION_STORE.setdefault(user_id, {})

# --- 4. CONFIGURACIÓN Y VARIABLES GLOBALES DE LA APP ---
@app.context_processor
def inject_user_and_csrf():
    return { 'user_logged_in': session.get('user_logged_in', False), 'user_initials': session.get('user_initials', ''), 'csrf_token': generate_csrf }

UPLOAD_FOLDER, UPLOAD_FOLDER_NRRD, ANONIMIZADO_FOLDER = 'uploads', 'upload_nrrd', os.path.join(os.getcwd(), 'anonimizado')
for folder in [UPLOAD_FOLDER, UPLOAD_FOLDER_NRRD, ANONIMIZADO_FOLDER]:
    if not os.path.exists(folder): os.makedirs(folder)

pn.extension('vtk')
bokeh_server_started = False
def start_bokeh_server(panel_layout):
    global bokeh_server_started
    if not bokeh_server_started:
        pn.serve({'/panel': panel_layout}, show=False, allow_websocket_origin=["*"], port=5010, threaded=True)
        bokeh_server_started = True

# --- 5. LÓGICA DE VISUALIZACIÓN Y PROCESAMIENTO DICOM ---
def create_render(user_data):
    """Crea el panel de visualización 3D con un slider de opacidad robusto."""
    panel_column = pn.Column()
    dicom_image = user_data.get('Image', np.array([]))
    if dicom_image.size == 0: return None

    # Segmentación y preparación de mallas (sin cambios)
    volume_bone = ((dicom_image > 175) * 1).astype(np.int16)
    volume_skin = (((dicom_image > -200) & (dicom_image < 0)) * 1).astype(np.int16)
    unique_id = user_data.get("unique_id")
    series_info = user_data.get('dicom_series', {}).get(unique_id, {})
    if not series_info: return None
    
    origin = series_info.get("ImagePositionPatient")
    spacing = (series_info.get("SliceThickness", 1), series_info.get("PixelSpacing", [1,1])[0], series_info.get("PixelSpacing", [1,1])[1])

    grid_bone = pv.ImageData(dimensions=np.array(volume_bone.shape) + 1, origin=origin, spacing=spacing)
    grid_bone.cell_data["values"] = volume_bone.flatten(order="F")
    grid_bone = grid_bone.cell_data_to_point_data()
    surface_bone = grid_bone.contour([0.5])

    grid_skin = pv.ImageData(dimensions=np.array(volume_skin.shape) + 1, origin=origin, spacing=spacing)
    grid_skin.cell_data["values"] = volume_skin.flatten(order="F")
    grid_skin = grid_skin.cell_data_to_point_data()
    surface_skin = grid_skin.contour([0.5]) # Esta es la geometría de la piel
    
    user_data['grid_dicom'] = grid_skin
    
    # Configuración del plotter (sin cambios)
    plotter = pv.Plotter(off_screen=True)
    plotter.set_background("black")
    plotter.add_mesh(surface_bone, color="white", smooth_shading=True)
    plotter.add_mesh(surface_skin, color="peachpuff", opacity=1.0, name="skin", smooth_shading=True)
    plotter.view_isometric()
    
    panel_vtk = pn.pane.VTK(plotter.ren_win, sizing_mode='stretch_both')

    # --- CAMBIO PRINCIPAL: Se restaura el slider con la lógica corregida ---
    
    # 1. Se crea el slider, con el valor por defecto al máximo (1.0)
    opacity_slider = pn.widgets.FloatSlider(
        name='Opacidad de la Piel', 
        start=0.0, end=1.0, step=0.05, value=1.0
    )
    
    # 2. La función de actualización utiliza el método robusto de "quitar y poner"
    def update_opacity_slider(event):
        new_opacity = event.new
        plotter.remove_actor('skin')
        plotter.add_mesh(surface_skin, color="peachpuff", opacity=new_opacity, name="skin", smooth_shading=True)
        panel_vtk.object = plotter.ren_win
        
    # 3. Se asocia la función de actualización al slider
    opacity_slider.param.watch(update_opacity_slider, 'value')

    # Se colocan el slider y el visor en la columna, con el slider arriba
    panel_column[:] = [opacity_slider, panel_vtk]
    
    user_data.update({'vtk_plotter': plotter, 'vtk_panel_column': panel_column, 'vtk_panel': panel_vtk})
    return panel_column

def add_RT_to_plotter(user_data):
    """Añade una malla de segmentación (RT Struct) al plotter 3D existente."""
    # Obtiene los objetos necesarios de la sesión del usuario
    plotter = user_data.get('vtk_plotter')
    panel_vtk = user_data.get('vtk_panel')
    grid_dicom = user_data.get('grid_dicom')

    # Valida que todos los objetos necesarios existan
    if not all([plotter, panel_vtk, grid_dicom]):
        return None

    # Procesa y alinea la imagen RT
    RT_Image = np.flip(user_data['RT'], axis=(0, 2)).transpose(2, 0, 1)
    user_data['RT_aligned'] = np.flip(user_data['RT'], axis=(0, 2))

    # Crea la malla 3D para la segmentación
    rt_grid = pv.ImageData(dimensions=np.array(RT_Image.shape) + 1, origin=grid_dicom.origin, spacing=grid_dicom.spacing)
    rt_grid.cell_data["values"] = (RT_Image > 1).astype(np.uint8).flatten(order="F")
    rt_grid = rt_grid.cell_data_to_point_data()
    surface = rt_grid.contour([0.5])
    user_data['rt_surface'] = surface # Guarda la geometría para poder mostrarla/ocultarla después

    # Añade la malla inicial al plotter con un nombre
    plotter.add_mesh(surface, color="red", opacity=0.5, smooth_shading=True, name="mask_actor")

    # --- LÓGICA DEL BOTÓN INTERNO ELIMINADA ---
    # Ya no se crea ni se añade el pn.widgets.Toggle a la columna del panel.

    # Actualiza la vista para que la máscara aparezca inmediatamente
    plotter.render()
    panel_vtk.object = plotter.ren_win
    
    return user_data.get('vtk_panel_column')

@app.route('/toggle_rt_visibility', methods=['POST'])
def toggle_rt_visibility():
    """Maneja la visibilidad de la máscara RT Struct desde el botón del plugin en la sidebar."""
    user_data = get_user_data()
    plotter = user_data.get('vtk_plotter')
    panel_vtk = user_data.get('vtk_panel')
    surface = user_data.get('rt_surface') 
    if not all([plotter, panel_vtk]):
        return jsonify({"error": "El visor no está inicializado"}), 400
    is_visible = request.json.get('visible', False)
    plotter.remove_actor("mask_actor")
    if is_visible and surface is not None:
        plotter.add_mesh(surface, color="red", opacity=0.5, smooth_shading=True, name="mask_actor")
    panel_vtk.object = plotter.ren_win
    return jsonify({"status": "ok", "visible": is_visible})

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
    if v == "axial" and 0 <= index < Z: img = vol[index, :, :]; w, h = X, int(round(Y * user_data["scale_axial"]))
    elif v == "coronal" and 0 <= index < Y: img = vol[:, index, :]; w, h = X, int(round(Z * user_data["scale_coronal"]))
    elif v == "sagittal" and 0 <= index < X: img = vol[:, :, index]; w, h = Y, int(round(Z * user_data["scale_sagittal"]))
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
    """Procesa la serie DICOM seleccionada por el usuario y prepara los datos para el visor."""
    user_data = get_user_data()
    unique_id = request.json.get('unique_id')
    user_data["unique_id"] = unique_id
    if not unique_id or not user_data.get('dicom_series'): return jsonify({"error": "Datos inválidos"}), 400
    
    # Ordena los cortes y crea un volumen 3D
    files = user_data['dicom_series'][unique_id]["ruta_archivos"]
    slices = sorted([(int(pydicom.dcmread(f).InstanceNumber), pydicom.dcmread(f).pixel_array) for f in files])
    volume_raw = np.array([s[1] for s in slices])
    user_data['dicom_series'][unique_id]["slices"] = volume_raw
    if volume_raw.size == 0: return jsonify({"error": "Serie sin slices"}), 400
    
    # Extrae y guarda todos los parámetros necesarios para la visualización
    slope = float(user_data['dicom_series'][unique_id].get("RescaleSlope", 1.0))
    intercept = float(user_data['dicom_series'][unique_id].get("RescaleIntercept", 0.0))
    dx, dy, dz = _extract_spacing_for_series(unique_id, user_data)
    s_ax, s_co, s_sa = _compute_view_scales(dx, dy, dz)
    
    user_data.update({
        "volume_raw": volume_raw.astype(np.int16), 
        "dims": volume_raw.shape, 
        "slope": slope, "intercept": intercept,
        "Image": (volume_raw * slope + intercept).astype(np.int16), 
        "scale_axial": s_ax, "scale_coronal": s_co, "scale_sagittal": s_sa
    })
    user_data.pop('vtk_panel_column', None) # Limpia el panel 3D para la nueva selección
    return jsonify({"mensaje": "Ok"})

@app.route("/render/<render>")
def render(render):
    """Muestra la página principal del visor con los 4 cuadrantes."""
    user_data = get_user_data()
    image = user_data.get('Image')
    if image is None or image.size == 0:
        return render_template("render.html", success=0)
    
    panel_layout = user_data.get('vtk_panel_column')
    if panel_layout is None:
        panel_layout = create_render(user_data)
        if panel_layout: start_bokeh_server(panel_layout)
        
    dims = user_data.get("dims", (1, 1, 1))
    return render_template("render.html", success=1, render=render,
                           max_value_axial=dims[0] - 1,
                           max_value_coronal=dims[1] - 1,
                           max_value_sagital=dims[2] - 1)

@app.route('/image/<view>/<int:layer>')
def get_image(view, layer):
    """Genera y devuelve una imagen PNG de un corte 2D específico."""
    user_data = get_user_data()
    # Recibe los parámetros de Window Leveling (brillo/contraste)
    ww = request.args.get('ww', default=400, type=float)
    wc = request.args.get('wc', default=40, type=float)

    img2d, w_px, h_px = _slice_2d_and_target_size(view, layer, user_data)
    if img2d is None: return "Vista o índice no válido", 400

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
    fig, ax = plt.subplots(figsize=(w_px / dpi, h_px / dpi), dpi=dpi)
    ax.imshow(image_8bit, cmap="gray", vmin=0, vmax=255, interpolation="nearest", aspect='auto')
    ax.axis("off")
    
    # Superpone la máscara de RT Struct si existe
    rt = user_data.get('RT_aligned')
    if rt is not None:
        try:
            v_lower = view.lower(); seg_slice = None
            if v_lower == 'axial': seg_slice = np.flip(rt[:, :, layer], axis=0)
            elif v_lower == 'sagital': seg_slice = rt[:, layer, :]
            elif v_lower == 'coronal': seg_slice = np.flip(rt[layer, :, :], axis=0)
            if seg_slice is not None: ax.imshow(ma.masked_where(seg_slice.T == 0, seg_slice.T), cmap='Reds', alpha=0.8, interpolation="nearest", aspect='auto')
        except Exception: pass

    # Guarda la imagen en un buffer en memoria y la envía al navegador
    buf = BytesIO()
    fig.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route("/upload_RT", methods=["POST"])
def upload_RT():
    """Maneja la subida de un archivo RT Struct en formato NRRD."""
    user_data = get_user_data()
    file = request.files.get("file")
    if not file or file.filename == '': return "Archivo inválido", 400
    filepath = os.path.join(UPLOAD_FOLDER_NRRD, file.filename); file.save(filepath)
    user_data['RT'], _ = nrrd.read(filepath)
    add_RT_to_plotter(user_data)
    dims = user_data.get("dims", (1, 1, 1))
    return render_template("render.html", success=1, max_value_axial=dims[0] - 1, max_value_coronal=dims[1] - 1, max_value_sagital=dims[2] - 1)

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
    return jsonify({"voxel": {"z": z, "y": yy, "x": xx}, "hu": hu})
    
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
                        # Asignar el valor. Necesita el tipo correcto, no siempre string.
                        data_element = dicom_data.data_element(campo)
                        if data_element:
                            data_element.value = valor
                dicom_data.save_as(os.path.join(out_dir, f"anonimo_{os.path.basename(archivo)}"))
            except Exception: continue
        zip_path = os.path.join(tmpdir, 'archivos_anonimizados.zip')
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for f in os.listdir(out_dir): zipf.write(os.path.join(out_dir, f), f)
        return send_file(zip_path, as_attachment=True, download_name='archivos_anonimizados.zip')

# --- 7. RUTAS DE LOGIN Y REGISTRO  ---
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