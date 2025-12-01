# Medical Image Processing Web Application - Architecture Documentation

**Repository:** Servicio-Web-APP-2025-2
**Purpose:** Medical imaging web application for DICOM visualization, anonymization, and 3D rendering
**Target Users:** Medical professionals, radiologists, students (Universidad de Guadalajara context)
**Last Analysis:** 2025-11-30

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
- Zoom/Pan - viewer.js:784-879
- Histogram editor - viewer.js:357-545

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

1. **RT Structure Alignment**: Hardcoded axis transformations (main.py:210) may not work for all NRRD formats
2. **Hardcoded Ports**: Flask (5001), Bokeh (5010) not configurable
3. **No Logging**: No structured logging (print statements only)
4. **Error Handling**: Most try/except blocks silently continue
5. **File Leakage**: Uploaded files never deleted
6. **Memory Leaks**: Session data never garbage collected
7. **No Tests**: No unit or integration tests
8. **Magic Numbers**: HU thresholds (175, -200) hardcoded for bone/skin
9. **Browser Compatibility**: Only tested on Chrome (likely)

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

**Strengths:**
- Clean separation of 2D and 3D rendering pipelines
- Sophisticated frontend with zoom, pan, histogram editing
- Multi-user session isolation
- Flexible RT Structure overlay

**Weaknesses:**
- No data persistence
- Memory-intensive session storage
- Missing production security features
- No cleanup mechanisms for uploaded files

**Best Use Cases:**
- Medical imaging education
- Research prototyping
- Single-user workstation analysis
- DICOM viewer demos

**NOT Suitable For:**
- Clinical production deployment
- Multi-day analysis workflows
- High-concurrency environments (>10 simultaneous users)
- PACS integration (without major refactoring)
