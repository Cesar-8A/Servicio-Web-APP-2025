# Medical Image Processing Web Application - Architecture Documentation

**Repository:** Servicio-Web-APP-2025-2
**Purpose:** Medical imaging web application for DICOM visualization, anonymization, and 3D rendering
**Target Users:** Medical professionals, radiologists, students (Universidad de Guadalajara context)
**Last Updated:** 2025-11-30

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture & Technology Stack](#architecture--technology-stack)
3. [Data Models & Storage](#data-models--storage)
4. [Complete Data Flow](#complete-data-flow)
5. [API Endpoints & Routes](#api-endpoints--routes)
6. [Frontend Architecture](#frontend-architecture)
7. [Security Model](#security-model)
8. [External Dependencies](#external-dependencies)
9. [Session Management](#session-management)
10. [File Structure](#file-structure)
11. [Recent Architecture Changes & Fixes (2025-11-30)](#11-recent-architecture-changes--fixes)

---

## 1. System Overview

### What the Application Does
This is a **medical imaging viewer and processing platform** that allows healthcare professionals to:
- Upload and visualize DICOM medical images (CT scans, MRI, etc.)
- View 3D volumetric renderings with multiple modes (isosurface, MIP, volume rendering)
- Load and overlay RT Structure segmentation masks (NRRD format)
- Manipulate window/level settings for optimal image contrast
- Anonymize patient data within DICOM files
- Export processed/anonymized DICOM series

### Key Capabilities
- **Multi-plane visualization**: Axial, Sagittal, Coronal views
- **3D rendering**: Real-time interactive 3D visualization using PyVista/VTK
- **Advanced image processing**: Histogram editing, HU (Hounsfield Unit) measurements, zoom/pan
- **Multi-user support**: Session-based data isolation
- **RT Structure overlay**: Segmentation mask visualization in 2D and 3D

---

## 2. Architecture & Technology Stack

### High-Level Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                      CLIENT BROWSER                         │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  HTML/CSS   │  │  JavaScript  │  │  Bootstrap UI    │  │
│  │  Templates  │  │  (viewer.js) │  │  + Icons         │  │
│  └─────────────┘  └──────────────┘  └──────────────────┘  │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP/WebSocket
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    FLASK WEB SERVER                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           main.py (Flask Application)                │   │
│  │  • Routes & Request Handlers                         │   │
│  │  • Session Management                                │   │
│  │  • DICOM Processing Logic                            │   │
│  │  • Image Generation Pipeline                         │   │
│  └─────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
│  PyDICOM     │   │  PyVista/VTK │   │  Bokeh/Panel     │
│  (DICOM I/O) │   │  (3D Engine) │   │  (3D Embedding)  │
└──────────────┘   └──────────────┘   └──────────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
                ┌───────────────────────┐
                │   File System         │
                │  • uploads/           │
                │  • upload_nrrd/       │
                │  • anonimizado/       │
                └───────────────────────┘
```

### Technology Stack

**Backend:**
- **Flask 3.0.3**: Web framework (routes, templates, session management)
- **PyDICOM 2.4.4**: DICOM file reading and metadata extraction
- **NumPy 1.24.4**: Array processing for volumetric data
- **PyVista 0.44.2**: 3D visualization using VTK (off-screen rendering)
- **Panel 1.2.3 + Bokeh 3.1.1**: Embedding interactive 3D views in web pages
- **Matplotlib 3.3.2**: 2D slice image generation
- **NRRD (pynrrd 1.1.3)**: RT Structure segmentation file I/O

**Frontend:**
- **Bootstrap 5.3.3**: UI framework and responsive design
- **Bootstrap Icons 1.11.3**: Icon library
- **Vanilla JavaScript (ES6)**: Client-side interactivity (viewer.js)
- **HTML5 Canvas**: 2D image rendering and overlays

**Security:**
- **Flask-WTF 1.2.1**: CSRF protection
- **Werkzeug 3.0.6**: Password hashing (SHA-256)
- **Flask Sessions**: Server-side session storage

---

## 3. Data Models & Storage

### Storage Architecture
**NO DATABASE** - This application uses **in-memory and file-based storage**:

1. **In-Memory Session Store** (`SERVER_SIDE_SESSION_STORE`)
   - Python dictionary: `{user_session_id: user_data_dict}`
   - Persists only while server is running
   - Each user gets isolated data space

2. **File System**
   - `uploads/`: Uploaded DICOM files
   - `upload_nrrd/`: RT Structure segmentation files (.nrrd)
   - `anonimizado/`: Exported anonymized DICOM series (temporary)

### User Session Data Structure
```python
user_data = {
    # --- Identity ---
    'user_session_id': str(uuid4()),  # Unique user identifier

    # --- DICOM Series Metadata ---
    'dicom_series': {
        'StudyUID-SeriesUID': {
            'ruta_archivos': [file_paths],      # List of DICOM file paths
            'slices': np.array,                 # 3D volume (Z, Y, X)
            'paciente': str,                    # Patient name
            'RescaleSlope': float,              # HU conversion factor
            'RescaleIntercept': float,          # HU conversion offset
            'ImagePositionPatient': [x, y, z],  # 3D spatial origin
            'PixelSpacing': [dx, dy],           # In-plane resolution
            'SliceThickness': float,            # Z-axis spacing
            'dimensiones': (slices, rows, cols),
            'tipo': '3D' | '2D',
            'Anonimize': {                      # Fields to anonymize
                'PatientName': str,
                'PatientID': str,
                # ... (17 DICOM tags)
            }
        }
    },

    # --- Active Volume Data ---
    'unique_id': str,                    # Currently selected series ID
    'volume_raw': np.ndarray,            # Raw pixel values (Z, Y, X)
    'dims': (Z, Y, X),                   # Volume dimensions
    'Image': np.ndarray,                 # HU-converted volume
    'slope': float,                      # Active RescaleSlope
    'intercept': float,                  # Active RescaleIntercept

    # --- Scaling Factors (for 2D display) ---
    'scale_axial': float,                # dy/dx
    'scale_coronal': float,              # dz/dx
    'scale_sagittal': float,             # dz/dy

    # --- 3D Visualization Objects ---
    'grid_full': pv.ImageData,           # PyVista 3D volume grid
    'vtk_plotter': pv.Plotter,           # PyVista plotter instance
    'vtk_panel': pn.pane.VTK,            # Panel VTK pane
    'vtk_panel_column': pn.Column,       # Panel layout
    'render_mode': 'isosurface' | 'mip' | 'volume',

    # --- RT Structure Segmentation ---
    'RT': np.ndarray,                    # Raw NRRD data
    'RT_header': dict,                   # NRRD metadata
    'RT_aligned': np.ndarray,            # Transformed RT for 2D overlay
}
```

### User Authentication Data
```python
usuarios = {
    'username': 'hashed_password'  # In-memory dictionary (not persistent)
}

session = {
    'user_logged_in': bool,
    'user_initials': str,           # First 2 letters of username
    'user_session_id': str(uuid4())
}
```

---

## 4. Complete Data Flow

### 4.1. DICOM Upload Flow
```
USER UPLOADS DICOM FILES
         │
         ▼
POST /loadDicom (files via multipart/form-data)
         │
         ├─→ Save files to uploads/
         │
         ├─→ process_dicom_folder()
         │    │
         │    ├─→ Read each DICOM with pydicom.dcmread()
         │    │
         │    ├─→ Group by (StudyInstanceUID, SeriesInstanceUID)
         │    │
         │    └─→ Extract metadata:
         │         • PatientName, dimensions, spacing
         │         • RescaleSlope, RescaleIntercept
         │         • 17 anonymization fields
         │
         ├─→ Store in user_data['dicom_series']
         │
         └─→ Render resultsTableDicom.html
                 (Table of available series)
```

### 4.2. Series Selection & Processing Flow
```
USER SELECTS A SERIES FROM TABLE
         │
         ▼
POST /process_selected_dicom
         │
         ├─→ Load all slices for series
         │    │
         │    ├─→ Read pixel_array from each DICOM
         │    ├─→ Sort by InstanceNumber
         │    └─→ Stack into 3D numpy array (volume_raw)
         │
         ├─→ Apply HU conversion:
         │    Image = volume_raw * slope + intercept
         │
         ├─→ Calculate spatial scaling factors:
         │    scale_axial = dy/dx
         │    scale_coronal = dz/dx
         │    scale_sagittal = dz/dy
         │
         ├─→ Create PyVista 3D grid:
         │    grid_full = pv.ImageData(
         │        dimensions=(Z+1, Y+1, X+1),
         │        origin=ImagePositionPatient,
         │        spacing=(dz, dy, dx)
         │    )
         │
         ├─→ Initialize 3D plotter:
         │    create_or_get_plotter()
         │     │
         │     ├─→ Create pv.Plotter(off_screen=True)
         │     ├─→ Render initial mode (isosurface)
         │     └─→ Start Bokeh server on port 5010
         │
         └─→ Return success
```

### 4.3. Image Viewing Flow (2D Slices)
```
USER MOVES SLICE SLIDER
         │
         ▼
JavaScript: updateImage(view, layer)
         │
         ├─→ GET /image/{view}/{layer}?ww=400&wc=40
         │             │
         │             ├─→ Extract 2D slice from volume_raw
         │             │    Axial: volume[layer, :, :]
         │             │    Coronal: volume[:, layer, :]
         │             │    Sagittal: volume[:, :, layer]
         │             │
         │             ├─→ Apply HU conversion:
         │             │    hu2d = slice * slope + intercept
         │             │
         │             ├─→ Apply Window Leveling:
         │             │    lower = wc - ww/2
         │             │    upper = wc + ww/2
         │             │    normalized = clip(hu2d, lower, upper)
         │             │    image_8bit = (normalized - lower) / ww * 255
         │             │
         │             ├─→ Render with Matplotlib:
         │             │    fig, ax = plt.subplots()
         │             │    ax.imshow(image_8bit, cmap='gray')
         │             │
         │             ├─→ Overlay RT mask (if loaded):
         │             │    ax.imshow(rt_slice, cmap='Reds', alpha=0.8)
         │             │
         │             └─→ Return PNG bytes
         │
         ├─→ Apply LUT (Look-Up Table) from histogram editor:
         │    for each pixel in imageData:
         │        mappedValue = contrastState.lut[grayValue]
         │
         └─→ Draw to Canvas with zoom/pan transform
```

### 4.4. 3D Rendering Flow
```
USER CHANGES 3D MODE (Isosurface/MIP/Volume)
         │
         ▼
POST /update_render_mode
         │
         ├─→ update_3d_render(user_data, mode)
         │    │
         │    ├─→ plotter.clear()
         │    │
         │    ├─→ IF mode == 'isosurface':
         │    │    surface_bone = grid.contour([175])  # HU threshold
         │    │    surface_skin = grid.contour([-200])
         │    │    plotter.add_mesh(bone, color='white')
         │    │    plotter.add_mesh(skin, color='peachpuff', opacity=0.5)
         │    │
         │    ├─→ IF mode == 'mip':
         │    │    plotter.add_volume(grid, cmap='bone', blending='maximum')
         │    │
         │    └─→ IF mode == 'volume':
         │         plotter.add_volume(grid, cmap='bone', blending='composite')
         │
         ├─→ panel_vtk.param.trigger('object')  # Update Panel widget
         │
         └─→ Bokeh server serves updated view at http://127.0.0.1:5010/panel
                 │
                 └─→ iframe in render.html reloads
```

### 4.5. RT Structure Upload Flow
```
USER UPLOADS .nrrd FILE
         │
         ▼
POST /upload_RT
         │
         ├─→ Save to upload_nrrd/
         │
         ├─→ rt_data, rt_header = nrrd.read(filepath)
         │
         ├─→ Apply axis transformation:
         │    rt_data = np.flip(rt_data, axis=(0,2)).transpose(2,0,1)
         │    (Aligns NRRD coordinate system with DICOM)
         │
         ├─→ Create PyVista grid:
         │    rt_grid = pv.ImageData(
         │        dimensions=rt_data.shape + 1,
         │        spacing=grid_full.spacing,
         │        origin=grid_full.origin
         │    )
         │
         ├─→ Add to 3D scene:
         │    surface = rt_grid.contour([0.5])
         │    plotter.add_mesh(surface, color='red', opacity=0.5)
         │
         └─→ Store rt_data for 2D overlay
```

### 4.6. Anonymization Flow
```
USER EDITS DICOM TAGS
         │
         ▼
POST /guardar_cambios
         │
         └─→ Update user_data['dicom_series'][uid]['Anonimize']
                 │
                 ▼
USER CLICKS "EXPORT"
         │
         ▼
POST /exportar_dicom
         │
         ├─→ Create temp directory
         │
         ├─→ For each DICOM file:
         │    │
         │    ├─→ dicom_data = pydicom.dcmread(file)
         │    │
         │    ├─→ For each tag in Anonimize dict:
         │    │    dicom_data[tag] = new_value
         │    │
         │    └─→ dicom_data.save_as(temp/anonimo_*.dcm)
         │
         ├─→ ZIP all files
         │
         └─→ send_file(archivos_anonimizados.zip)
```

---

## 5. API Endpoints & Routes

### Authentication Routes
| Method | Route | Purpose | Returns |
|--------|-------|---------|---------|
| GET/POST | `/login` | User login form | HTML template |
| GET/POST | `/register` | User registration | HTML template |
| GET | `/logout` | Clear session and logout | Redirect to home |

### Main Workflow Routes
| Method | Route | Purpose | Returns |
|--------|-------|---------|---------|
| GET | `/` | Home page | index.html |
| GET/POST | `/loadDicom` | Upload DICOM folder | resultsTableDicom.html |
| GET | `/loadDicomMetadata/<unique_id>` | Get series metadata | JSON |
| POST | `/process_selected_dicom` | Process selected series | JSON status |
| GET | `/render/<render>` | Main viewer page | render.html |

### Image Serving Routes
| Method | Route | Purpose | Returns |
|--------|-------|---------|---------|
| GET | `/image/<view>/<layer>` | Get 2D slice PNG | image/png |
| | | Query params: `ww`, `wc` | |

### Interactive Tools Routes
| Method | Route | Purpose | Returns |
|--------|-------|---------|---------|
| GET | `/hu_value` | Get HU value at (x,y,z) | JSON: {voxel, hu} |
| GET | `/get_histogram` | Get volume histogram | JSON: {counts, bin_edges} |
| GET | `/get_dicom_metadata` | Get technical metadata | JSON |
| POST | `/update_render_mode` | Change 3D rendering | JSON status |
| POST | `/upload_RT` | Upload RT Structure | JSON status |

### Anonymization Routes
| Method | Route | Purpose | Returns |
|--------|-------|---------|---------|
| GET | `/anonimize` | Anonymization editor | anonimize.html |
| POST | `/guardar_cambios` | Save anonymization edits | JSON status |
| POST | `/exportar_dicom` | Export anonymized series | ZIP file |

---

## 6. Frontend Architecture

### Component Structure
```
render.html
  ├── Sidebar (#plugins-sidebar)
  │   ├── Tool Buttons (HU, Inspector, Window/Level, RT, Histogram)
  │   ├── 3D Mode Selector (Isosurface/MIP/Volume)
  │   └── Active Tool Panels (dynamic)
  │
  └── Quadrant Grid (#quadrant-grid)
      ├── Axial View (Canvas + Overlay)
      ├── Sagittal View (Canvas + Overlay)
      ├── Coronal View (Canvas + Overlay)
      └── 3D View (iframe → Bokeh server)
```

### JavaScript State Management (viewer.js)
```javascript
// Global State Objects
viewState = {
    ww: 400,              // Window width
    wc: 40,               // Window center
    baseImages: {},       // Cached images per view
    huMode: false,        // HU picker active
    inspectorMode: false  // 3D inspector active
}

zoomState = {
    axial: { scale, panX, panY, isDragging },
    sagital: { ... },
    coronal: { ... }
}

contrastState = {
    points: [{x, y}, ...],     // Histogram curve control points
    lut: Uint8ClampedArray,    // Lookup table (256 values)
    cutoff: 7.0,               // Histogram display cutoff
    logScale: false,           // Histogram log scale
    histogramData: null        // Server-fetched histogram
}
```

### Key Frontend Features

**1. Tool Activation System**
- Each tool button toggles visual state (`.btn-udg-rojo` class)
- Opens corresponding panel in sidebar
- Mutually exclusive modes (HU vs Inspector)

**2. Window/Level Control**
- Dual input: Sliders + numeric spinners
- Presets: Lung (-600/1500), Bone (480/2500), Soft Tissue (40/400)
- Debounced manual input (250ms delay)
- Instant slider feedback

**3. Zoom & Pan**
- Mouse wheel zoom (centered on cursor)
- Click-drag panning
- Shared transform for Canvas + Overlay
- Double-click to reset

**4. Histogram Editor**
- Draggable control points on curve
- Linear interpolation for LUT generation
- Real-time image re-mapping (no server round-trip)
- Log scale toggle for visualization

**5. HU Picker**
- Converts CSS click coordinates to internal pixel coordinates
- Accounts for `object-fit: contain` letterboxing
- Displays voxel (x,y,z) and HU value
- Draws marker on overlay canvas

**6. 3D Inspector (Crosshair)**
- Click or drag on any view
- Draws crosshair on current view
- Syncs other views to clicked location:
  - Axial (x,y) → Sagittal[x], Coronal[y]
  - Coronal (x,y) → Sagittal[x], Axial[y]
  - Sagittal (x,y) → Coronal[x], Axial[y]

---

## 7. Security Model

### Implemented Security Measures

1. **CSRF Protection**
   - Flask-WTF generates tokens for all forms
   - Token validated on POST requests
   - Meta tag injection: `<meta name="csrf-token" content="{{ csrf_token() }}">`

2. **Password Security**
   - Werkzeug SHA-256 hashing (generate_password_hash)
   - Passwords never stored in plaintext
   - Hash verification with constant-time comparison

3. **Session Security**
   - Flask secret key (from environment or random)
   - Session cookies HttpOnly (default)
   - Server-side session data isolation per UUID

4. **File Upload Validation**
   - NRRD upload: `.nrrd` extension check (main.py:588)
   - DICOM files processed with `pydicom.dcmread(force=True)` (graceful error handling)

### Security Gaps & Recommendations

⚠️ **CRITICAL ISSUES:**
1. **No persistent user storage** - `usuarios` dict resets on server restart
2. **No file size limits** on uploads → DoS risk
3. **No MIME type validation** beyond file extension
4. **Temporary files not cleaned up** (uploads/, upload_nrrd/ accumulate)
5. **No rate limiting** on endpoints
6. **Bokeh server allows all WebSocket origins** (`allow_websocket_origin=["*"]` at main.py:91)
7. **No HTTPS enforcement**
8. **Session data leaks on logout only clear one user** - others persist in memory

---

## 8. External Dependencies

### Required Python Packages (Key Subset)
```
flask==3.0.3              # Web framework
pydicom==2.4.4            # DICOM I/O
pyvista==0.44.2           # 3D rendering (VTK wrapper)
numpy==1.24.4             # Array processing
matplotlib==3.3.2         # 2D plotting
panel==1.2.3              # Embedding dashboards
bokeh==3.1.1              # Interactive visualization backend
pynrrd==1.1.3             # NRRD file format
flask-wtf==1.2.1          # CSRF protection
werkzeug==3.0.6           # Security utilities
```

### External Services
1. **Bokeh Server** (Port 5010)
   - Started in separate thread (main.py:91)
   - Serves 3D VTK widget via WebSocket
   - Must be accessible from client browser

2. **CDN Resources**
   - Bootstrap CSS/JS (jsdelivr.net)
   - Bootstrap Icons (jsdelivr.net)

### Runtime Requirements
- **PyVista off-screen rendering**:
  - Requires VTK 9.2.6
  - Uses `OFF_SCREEN = True` mode (no display server needed)
  - Backend: `'static'` (main.py:35)

---

## 9. Session Management

### Session Lifecycle
```
1. User visits site
   ↓
2. get_user_data() checks for 'user_session_id' in Flask session
   ↓
3. IF NOT EXISTS:
     - Generate UUID: str(uuid4())
     - Store in Flask session cookie
     - Create empty dict in SERVER_SIDE_SESSION_STORE[uuid]
   ↓
4. User uploads DICOM → data stored in SERVER_SIDE_SESSION_STORE[uuid]
   ↓
5. User logs out:
     - DELETE SERVER_SIDE_SESSION_STORE[uuid]
     - session.clear() (Flask cookie cleared)
```

### Data Persistence Rules
- **In-Memory Data**: Lost on server restart
- **Uploaded Files**: Persist in filesystem (never cleaned)
- **User Accounts**: Lost on server restart (no database)

### Multi-User Isolation
- Each browser session gets unique UUID
- Different tabs/windows with SAME cookies = SAME session
- Incognito mode = NEW session
- No data leakage between users (isolated dicts)

---

## 10. File Structure

```
Servicio-Web-APP-2025-2/
│
├── main.py                 # Flask application (726 lines)
│   ├── Routes (17 endpoints)
│   ├── DICOM processing functions
│   ├── 3D rendering logic
│   └── Session management
│
├── templates/
│   ├── home.html           # Base template (navbar, auth, layout)
│   ├── index.html          # Landing page
│   ├── loadDicom.html      # Upload form
│   ├── resultsTableDicom.html  # Series selection table
│   ├── render.html         # Main viewer (4-quadrant grid)
│   ├── anonimize.html      # Anonymization editor
│   ├── login.html          # Login form
│   └── register.html       # Registration form
│
├── static/
│   ├── css/
│   │   └── udg_estilos.css # Custom styles (UDG branding)
│   ├── js/
│   │   └── viewer.js       # Frontend logic (1135 lines)
│   └── img/
│       ├── udg_logo.png
│       └── leones_negros_logo.png
│
├── uploads/                # DICOM files (343+ test files)
├── upload_nrrd/            # RT Structure files (*.nrrd)
├── anonimizado/            # Temporary export folder
│
├── requirements.txt        # ~280 dependencies
├── README.md               # Basic project description
└── .gitignore
```

### Key Code Locations

**DICOM Processing:**
- `process_dicom_folder()` - main.py:286-326
- `process_selected_dicom` route - main.py:360-423

**3D Rendering:**
- `create_or_get_plotter()` - main.py:96-145
- `update_3d_render()` - main.py:147-187
- `add_RT_to_plotter()` - main.py:189-251

**Image Generation:**
- `get_image()` route - main.py:529-577
- Window leveling formula - main.py:544-552

**Frontend Interactivity:**
- Tool activation - viewer.js:74-139
- Window/Level controls - viewer.js:142-247
- Zoom/Pan - viewer.js:819-914
- Histogram editor - viewer.js:384-573
- HU Picker - viewer.js:587-724
- 3D Inspector - viewer.js:917-1117

---

## 11. Recent Architecture Changes & Fixes

**Last Updated:** 2025-11-30

This section documents critical bug fixes and architectural improvements made to the coordinate mapping system for 2D viewer tools (HU Picker and 3D Inspector).

### 11.1. Problem Summary: Zoom Interaction Issues

**Issue:** When users zoomed into 2D medical images, the HU Picker marker and 3D Inspector crosshairs appeared at incorrect screen positions, despite being drawn at the correct internal pixel coordinates.

**Root Cause:** The initial implementation attempted to apply an **inverse CSS transform** when drawing on overlay canvases, misunderstanding how CSS transforms affect canvas rendering.

**Impact:** Tools were unusable at zoom levels other than 1.0×, breaking critical functionality for detailed medical image analysis.

---

### 11.2. Coordinate Space Architecture

The application uses **three distinct coordinate systems** for 2D image rendering:

#### **1. Screen/CSS Coordinates**
- **Definition**: Pixel position relative to the browser viewport
- **Origin**: Top-left corner of the browser window
- **Use Case**: Mouse event coordinates (`evt.clientX`, `evt.clientY`)
- **Example**: User clicks at (500, 300) on screen

#### **2. Canvas Display Coordinates**
- **Definition**: Position within the visible canvas element on screen
- **Origin**: Top-left corner of the canvas element
- **Affected By**: CSS `max-width`, `max-height`, `object-fit: contain`
- **Use Case**: Determining click position relative to displayed image
- **Example**: Click at (200, 150) within the canvas bounding rectangle

#### **3. Internal Pixel Coordinates**
- **Definition**: Position within the canvas's internal pixel grid (PNG dimensions)
- **Origin**: Top-left corner of the internal canvas buffer
- **Dimensions**: Actual data dimensions (e.g., 512×512 for axial, 512×160 for coronal/sagittal after aspect ratio scaling)
- **Use Case**: Indexing into image data, drawing annotations
- **Example**: Pixel (256, 128) in the internal canvas buffer

---

### 11.3. CSS Transform Behavior (Critical Understanding)

The application applies CSS transforms to both the main canvas and overlay canvas:

```css
canvas.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
canvas.style.transformOrigin = '0 0';
```

**How CSS Transforms Work:**
1. Transforms are applied **right-to-left**: `scale` is applied first, then `translate`
2. Drawing at internal pixel position `P` with transform `T` results in screen position:
   ```
   screenX = (P.x × scale) + panX
   screenY = (P.y × scale) + panY
   ```
3. The browser's rendering engine applies transforms **automatically** - no manual calculation needed when drawing on transformed canvases

**Key Insight:** If a canvas has a CSS transform applied, and you draw at internal pixel coordinates `(x, y)`, the browser will automatically display it at the transformed screen position. You do NOT need to manually apply or invert the transform.

---

### 11.4. Coordinate Conversion Function

**Function:** `cssToPngPixels()` (viewer.js:587-635)

**Purpose:** Converts screen click coordinates to internal canvas pixel coordinates.

```javascript
function cssToPngPixels(canvasEl, evt) {
    // Get canvas position and size on screen
    const canvasRect = canvasEl.getBoundingClientRect();

    // Click position relative to canvas element
    const cssX = evt.clientX - canvasRect.left;
    const cssY = evt.clientY - canvasRect.top;

    // Canvas internal dimensions (PNG size)
    const internalW = canvasEl.width;
    const internalH = canvasEl.height;

    // Canvas CSS display dimensions (accounting for transforms)
    const displayW = canvasRect.width;
    const displayH = canvasRect.height;

    // Scaling factor between display and internal
    const scaleX = internalW / displayW;
    const scaleY = internalH / displayH;

    // Convert to internal pixel coordinates
    const xPix = Math.floor(cssX * scaleX);
    const yPix = Math.floor(cssY * scaleY);

    return {
        xPix: xPix,
        yPix: yPix,
        cssX: xPix,  // NOTE: Returns internal coords, naming is misleading
        cssY: yPix
    };
}
```

**Critical Behavior:**
- `getBoundingClientRect()` **automatically accounts for CSS transforms**, returning the actual screen position/size
- The returned coordinates are in **internal pixel space**, NOT screen space (despite the misleading `cssX`/`cssY` naming)
- These coordinates can be used directly for drawing on the overlay canvas

---

### 11.5. The Failed Approach (Inverse Transform)

**Initial Implementation (INCORRECT):**

```javascript
// ❌ WRONG: Attempted to manually invert the CSS transform
function drawCrosshair(view, x, y) {
    const zs = zoomState[view];

    // Attempted inverse transform calculation
    const adjX = (x - zs.panX) / zs.scale;
    const adjY = (y - zs.panY) / zs.scale;

    ctx.moveTo(adjX, 0);  // Draw at "adjusted" position
    ctx.lineTo(adjX, overlay.height);
}
```

**Why It Failed:**
1. The input coordinates `(x, y)` were **already in internal pixel space** (from `cssToPngPixels`)
2. The overlay canvas **already has the same CSS transform** as the main canvas
3. Applying the inverse transform was **double-correcting** the coordinates
4. The browser's CSS transform engine was still applying the transform to the final rendering

**Result:** Crosshairs appeared at completely wrong positions, especially at high zoom levels.

---

### 11.6. The Correct Solution

**Key Principle:** When drawing on a canvas that has a CSS transform, draw at internal pixel coordinates and let the browser apply the transform automatically.

#### **Fix 1: HU Picker Marker (viewer.js:637-660)**

```javascript
function drawMarker(view, cssX, cssY) {
    const overlay = document.getElementById(`overlay_${view}`);
    const mainCanvas = document.getElementById(`canvas_${view}`);
    if (!overlay || !mainCanvas) return;

    const ctx = overlay.getContext("2d");
    ctx.clearRect(0, 0, overlay.width, overlay.height);

    // cssX, cssY are already in internal pixel coordinates (from cssToPngPixels)
    // The overlay canvas has the same transform as the main canvas,
    // so we just draw at the pixel coordinates directly.
    // The browser will apply the zoom/pan transform automatically.
    const zs = zoomState[view];

    // Marker styling
    ctx.fillStyle = "#FFD700";
    ctx.strokeStyle = "red";
    ctx.lineWidth = 2 / zs.scale; // Scale line width for constant visual size

    ctx.beginPath();
    ctx.arc(cssX, cssY, 5 / zs.scale, 0, 2 * Math.PI); // Draw directly at internal coords
    ctx.fill();
    ctx.stroke();
}
```

**Changes Made:**
1. ✅ Removed inverse transform calculation
2. ✅ Draw directly at input coordinates: `ctx.arc(cssX, cssY, ...)`
3. ✅ Scale line widths inversely: `lineWidth = 2 / scale` (keeps visual size constant)
4. ✅ Added explanatory comments

#### **Fix 2: 3D Inspector Crosshair (viewer.js:917-950)**

```javascript
function drawCrosshair(view, x, y) {
    const overlay = document.getElementById(`overlay_${view}`);
    const mainCanvas = document.getElementById(`canvas_${view}`);
    if (!overlay || !mainCanvas) return;

    // Resize overlay to match main canvas
    overlay.width = mainCanvas.width;
    overlay.height = mainCanvas.height;

    const ctx = overlay.getContext("2d");
    ctx.clearRect(0, 0, overlay.width, overlay.height);

    // x, y are already in internal pixel coordinates (from cssToPngPixels)
    // The overlay canvas has the same transform as the main canvas,
    // so we just draw at the pixel coordinates directly.
    // The browser will apply the zoom/pan transform automatically.
    const zs = zoomState[view];

    // Crosshair styling
    ctx.strokeStyle = "#00FFFF";  // Cyan color
    ctx.lineWidth = 1 / zs.scale; // Scale line width for constant visual size
    ctx.setLineDash([5 / zs.scale, 3 / zs.scale]); // Scale dash pattern

    // Vertical line - draw at pixel coordinate x
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, overlay.height);
    ctx.stroke();

    // Horizontal line - draw at pixel coordinate y
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(overlay.width, y);
    ctx.stroke();
}
```

**Changes Made:**
1. ✅ Removed inverse transform calculation
2. ✅ Draw lines at input coordinates: `ctx.moveTo(x, 0)` and `ctx.moveTo(0, y)`
3. ✅ Scale line width and dash pattern inversely
4. ✅ Added explanatory comments

---

### 11.7. Visual Size Consistency

**Problem:** When zoomed in, drawn elements (lines, circles) become proportionally larger because the CSS transform scales everything.

**Solution:** Inverse scaling of drawing properties:

```javascript
const zs = zoomState[view];

// Line width: 2px at 1.0× zoom, 1px at 2.0× zoom, 0.5px at 4.0× zoom
ctx.lineWidth = 2 / zs.scale;

// Circle radius: 5px at 1.0× zoom, 2.5px at 2.0× zoom
ctx.arc(x, y, 5 / zs.scale, 0, 2 * Math.PI);

// Dash pattern: [5px, 3px] at 1.0× zoom, [2.5px, 1.5px] at 2.0× zoom
ctx.setLineDash([5 / zs.scale, 3 / zs.scale]);
```

**Result:** Visual elements appear at constant screen size regardless of zoom level, improving usability.

---

### 11.8. Aspect Ratio Scaling (Background Context)

The application compensates for non-isotropic voxel spacing (physical dimensions differ in X, Y, Z):

**Backend Calculation (main.py:270-272):**
```python
def _compute_view_scales(dx, dy, dz):
    """Calculate aspect ratio scaling factors."""
    eps = 1e-8
    return (
        max(eps, dy / dx),  # scale_axial
        max(eps, dz / dx),  # scale_coronal
        max(eps, dz / dy)   # scale_sagittal
    )
```

**PNG Generation (main.py:558-582):**
```python
# Determine aspect ratio based on view
if v_lower == "axial":
    display_w, display_h = w_px, h_px  # Already square in physical space
elif v_lower in ["coronal", "sagital", "sagittal"]:
    # Scale height by slice thickness ratio
    aspect_ratio = dz / dx
    display_w = w_px
    display_h = int(h_px * aspect_ratio)

# Create figure with correct physical proportions
fig, ax = plt.subplots(figsize=(display_w / dpi, display_h / dpi), dpi=dpi)
ax.imshow(image_8bit, cmap="gray", aspect='auto')  # 'auto' stretches to figsize
```

**Frontend Usage:**
- Scaling factors returned in `/hu_value` response (main.py:654-658)
- Used to convert voxel coordinates to pixel coordinates
- Applied when syncing views in 3D Inspector

---

### 11.9. Complete Coordinate Flow Example

**Scenario:** User clicks on axial view at screen position (800, 600) with zoom 2.0× and pan (-100, -50)

**Step-by-Step:**

1. **Mouse Event:**
   ```javascript
   evt.clientX = 800  // Screen coordinates
   evt.clientY = 600
   ```

2. **Get Canvas Rect (accounts for CSS transform):**
   ```javascript
   const canvasRect = canvas.getBoundingClientRect();
   // canvasRect.left = 300
   // canvasRect.top = 200
   // canvasRect.width = 600  (displayed size after transform)
   // canvasRect.height = 600
   ```

3. **Canvas-Relative Coordinates:**
   ```javascript
   const cssX = 800 - 300 = 500  // Click position within canvas
   const cssY = 600 - 200 = 400
   ```

4. **Internal Canvas Dimensions:**
   ```javascript
   canvas.width = 512   // Internal pixel grid
   canvas.height = 512
   ```

5. **Scale Factor:**
   ```javascript
   scaleX = 512 / 600 = 0.853
   scaleY = 512 / 600 = 0.853
   ```

6. **Internal Pixel Coordinates:**
   ```javascript
   xPix = Math.floor(500 × 0.853) = 426
   yPix = Math.floor(400 × 0.853) = 341
   ```

7. **Draw Marker on Overlay (which has transform applied):**
   ```javascript
   ctx.arc(426, 341, 5 / 2.0, ...)  // Draw at (426, 341) with radius 2.5px
   ```

8. **Browser Applies CSS Transform:**
   ```
   screenX = (426 × 2.0) + (-100) = 752
   screenY = (341 × 2.0) + (-50) = 632
   ```

9. **Final Result:** Marker appears at correct screen position (752, 632), directly under the user's click.

---

### 11.10. Backend Changes (Previous Session)

**Modified:** `main.py:/hu_value` endpoint (lines 636-658)

**Change:** Added `scales` object to response to support frontend coordinate conversions:

```python
@app.route("/hu_value")
def hu_value():
    # ... (coordinate calculation) ...

    # Return voxel coordinates AND scaling factors
    return jsonify({
        "voxel": {"z": z, "y": yy, "x": xx},
        "hu": hu,
        "scales": {
            "axial": s_ax,     # dy/dx
            "coronal": s_co,   # dz/dx
            "sagittal": s_sa   # dz/dy
        }
    })
```

**Purpose:** Allows frontend to correctly convert pixel coordinates to voxel coordinates accounting for aspect ratio scaling, essential for 3D Inspector view synchronization.

---

### 11.11. Known Issues Resolved

The following issues from the "Known Issues & Technical Debt" section are now **RESOLVED**:

- ~~Zoom interaction breaks HU Picker~~ ✅ **FIXED** (2025-11-30)
- ~~3D Inspector crosshair position incorrect when zoomed~~ ✅ **FIXED** (2025-11-30)
- ~~Coordinate mapping doesn't account for aspect ratio~~ ✅ **FIXED** (previous session)

---

### 11.12. Testing Recommendations

To verify the fixes work correctly:

1. **Load a DICOM series** with non-isotropic voxel spacing (e.g., slice thickness ≠ pixel spacing)
2. **Activate HU Picker** tool
3. **Zoom in** to 2.0× or higher on any view
4. **Click on the image** - marker should appear exactly under cursor
5. **Pan the image** and click again - marker should still be accurate
6. **Activate 3D Inspector**
7. **Click and drag** on any view - crosshairs should follow cursor precisely
8. **Verify view synchronization** - crosshairs on other views should align with anatomical position
9. **Test at various zoom levels** (1.0×, 2.6×, 5.0×, 10.0×)

---

### 11.13. Future Considerations

**Potential Improvements:**

1. **Rename `cssToPngPixels` function** to `screenToInternalPixels` for clarity
2. **Rename returned properties** `cssX`/`cssY` to `internalX`/`internalY` to avoid confusion
3. **Add coordinate space documentation** to code comments for future developers
4. **Consider caching `getBoundingClientRect()`** results (currently called on every mouse event)
5. **Add unit tests** for coordinate conversion functions with mock canvas elements

**Performance Note:** The current implementation calls `getBoundingClientRect()` on every mouse move event during Inspector drag operations. This is a synchronous layout query that can cause reflows. Consider throttling or caching if performance issues arise on low-end devices.

---

### 11.14. Key Takeaways for Future Development

1. **CSS transforms are applied by the browser automatically** - don't manually apply/invert them when drawing on transformed canvases
2. **`getBoundingClientRect()` accounts for transforms** - it returns the actual screen position/size after transformations
3. **Coordinate space confusion is easy** - clearly document which space each function operates in
4. **Inverse scaling maintains visual consistency** - divide drawing sizes by zoom scale to keep constant screen size
5. **Test at multiple zoom levels** - bugs often only appear at high zoom (2.0×+)

---

## Data Flow Diagrams

### Complete End-to-End Flow
```
┌───────────┐
│  Browser  │
└─────┬─────┘
      │
      │ 1. POST /loadDicom (DICOM files)
      ▼
┌──────────────────────────────────────────┐
│  Flask: process_dicom_folder()           │
│  • Parse DICOM metadata                  │
│  • Group by Study/Series                 │
│  • Store in SERVER_SIDE_SESSION_STORE    │
└─────┬────────────────────────────────────┘
      │
      │ 2. Render table of series
      ▼
┌───────────┐
│  Browser  │ ← User selects series
└─────┬─────┘
      │
      │ 3. POST /process_selected_dicom
      ▼
┌──────────────────────────────────────────┐
│  Flask: Load volume + Create 3D grid    │
│  • volume_raw = stack(DICOM slices)     │
│  • grid_full = PyVista ImageData        │
│  • Start Bokeh server (once)            │
└─────┬────────────────────────────────────┘
      │
      │ 4. Redirect to /render/dicom
      ▼
┌──────────────────────────────────────────┐
│  Browser: 4-quadrant viewer loads       │
│  • 3 Canvas (Axial/Sagital/Coronal)     │
│  • 1 iframe (Bokeh 3D)                  │
└─────┬────────────────────────────────────┘
      │
      ├─5a. GET /image/axial/50?ww=400&wc=40
      │     ▼
      │  ┌──────────────────────────┐
      │  │ Slice extraction + render│ → PNG
      │  └──────────────────────────┘
      │
      ├─5b. User moves slice slider
      │     ▼ (Repeat 5a)
      │
      ├─5c. User adjusts window/level
      │     ▼ (Repeat 5a with new ww/wc)
      │
      └─5d. User uploads RT Structure
            ▼
         ┌──────────────────────────┐
         │ POST /upload_RT          │
         │ • Add to 3D scene        │
         │ • Store for 2D overlay   │
         └──────────────────────────┘
```

---

## Performance Characteristics

### Bottlenecks
1. **Image Generation**: Each slice request generates PNG via Matplotlib (CPU-bound)
2. **3D Rendering**: PyVista contouring can be slow for large volumes (>500 slices)
3. **Session Storage**: All volume data kept in RAM (can be GBs per user)

### Optimization Strategies (Currently NOT Implemented)
- No caching of generated slice images
- No chunking/streaming of large volumes
- No background job queue
- No cleanup of old sessions

---

## Critical Architecture Decisions

### 1. Why No Database?
- **Rationale**: Educational/prototype application for single-institution use
- **Trade-off**: No persistent users, loses data on restart
- **Impact**: Not production-ready for multi-day workflows

### 2. Why In-Memory Session Storage?
- **Rationale**: Fast access to volumetric data (no serialization)
- **Trade-off**: RAM usage scales with concurrent users × volume size
- **Impact**: Server restart = all users lose work

### 3. Why Bokeh for 3D?
- **Rationale**: PyVista doesn't natively embed in Flask
- **Trade-off**: Requires separate server on port 5010
- **Impact**: Network configuration complexity (firewall, WebSocket)

### 4. Why Matplotlib for 2D Slices?
- **Rationale**: Simple PNG generation with scientific colormaps
- **Trade-off**: Slower than pre-rendered tiles
- **Impact**: Noticeable lag when scrubbing through slices

---

## Deployment Considerations

### Development vs. Production
**Current Config (main.py:726):**
```python
app.run(debug=True, port=5001)
```

**Production Requirements:**
1. Use WSGI server (Gunicorn, uWSGI)
2. Set `debug=False`
3. Configure proper secret keys (not random)
4. Add HTTPS reverse proxy (nginx)
5. Implement database for users
6. Add file cleanup cron job
7. Set upload size limits
8. Configure Bokeh server security

### Environment Variables Needed
```bash
FLASK_SECRET_KEY=<strong-random-key>
WTF_CSRF_SECRET_KEY=<another-key>
FLASK_ENV=production
MAX_UPLOAD_SIZE=500M
```

---

## Known Issues & Technical Debt

### Issues Resolved (2025-11-30)
- ~~Zoom interaction breaks HU Picker~~ ✅ **FIXED**
- ~~3D Inspector crosshair position incorrect when zoomed~~ ✅ **FIXED**
- ~~Coordinate mapping doesn't account for aspect ratio~~ ✅ **FIXED**

See [Section 11: Recent Architecture Changes & Fixes](#11-recent-architecture-changes--fixes) for details.

### Outstanding Issues

1. **RT Structure Alignment**: Hardcoded axis transformations (main.py:210) may not work for all NRRD formats
2. **Hardcoded Ports**: Flask (5001), Bokeh (5010) not configurable
3. **No Logging**: No structured logging (print statements only)
4. **Error Handling**: Most try/except blocks silently continue
5. **File Leakage**: Uploaded files never deleted
6. **Memory Leaks**: Session data never garbage collected
7. **No Tests**: No unit or integration tests
8. **Magic Numbers**: HU thresholds (175, -200) hardcoded for bone/skin
9. **Browser Compatibility**: Only tested on Chrome (likely)
10. **Misleading Function Names**: `cssToPngPixels` returns internal pixel coords, not CSS coords (naming confusion)

---

## Future Enhancement Opportunities

### High Priority
1. Add PostgreSQL/SQLite for persistent user storage
2. Implement Redis for session caching
3. Add Celery for async DICOM processing
4. Pre-generate slice tiles for faster scrubbing
5. Add file upload size limits and validation

### Medium Priority
6. Implement DICOM C-STORE server (receive from PACS)
7. Add multi-timepoint comparison views
8. Support DICOM-RT Plan files
9. Add measurement tools (distance, area, volume)
10. Export rendered 3D views as STL/OBJ

### Low Priority
11. Add user roles (doctor, student, admin)
12. Implement audit logging
13. Add batch anonymization
14. Support DICOM Query/Retrieve (C-FIND, C-MOVE)
15. Add AI model integration (tumor detection, segmentation)

---

## Conclusion

This application is a **feature-rich medical imaging viewer** with impressive 3D visualization capabilities, but architecturally suited for **educational/research environments** rather than production clinical use. The lack of persistent storage and security hardening would need to be addressed for HIPAA-compliant deployment.

**Recent Improvements (2025-11-30):**
- ✅ Fixed zoom interaction issues with HU Picker and 3D Inspector
- ✅ Resolved coordinate mapping bugs with aspect ratio scaling
- ✅ Improved visual consistency at all zoom levels
- ✅ Enhanced documentation with comprehensive coordinate system architecture

**Strengths:**
- Clean separation of 2D and 3D rendering pipelines
- Sophisticated frontend with zoom, pan, histogram editing
- Multi-user session isolation
- Flexible RT Structure overlay
- **Robust coordinate mapping system** (recently fixed)
- **Precise HU measurements at any zoom level** (recently fixed)

**Weaknesses:**
- No data persistence
- Memory-intensive session storage
- Missing production security features
- No cleanup mechanisms for uploaded files
- Some misleading function/variable names (legacy code)

**Best Use Cases:**
- Medical imaging education
- Research prototyping
- Single-user workstation analysis
- DICOM viewer demos
- Detailed radiological analysis with zoom/pan tools

**NOT Suitable For:**
- Clinical production deployment
- Multi-day analysis workflows
- High-concurrency environments (>10 simultaneous users)
- PACS integration (without major refactoring)
