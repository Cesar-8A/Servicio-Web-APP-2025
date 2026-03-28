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
12. [Multi-Segmentation System](#12-multi-segmentation-system)
13. [AI Segmentation Plugin — Swin-UNETR](#13-ai-segmentation-plugin--swin-unetr)

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

    # --- Manual / AI Segmentation System ---
    'segmentations': {
        0: {
            'name': str,                 # User-defined label
            'mask': np.ndarray,          # uint8 volume (Z, Y, X) — 0 or 255
            'color': str,                # Hex color e.g. '#00FFFF'
            'visible': bool,
            'last_polygon_operation': {  # Snapshot for 1-level undo (or None)
                'view': str,
                'layer': int,
                'vertices': list,
                'mode': str,
                'mask_before': np.ndarray  # Full mask copy before the operation
            }
        },
        # Keys are integers 0–4 (max 5 concurrent segmentations)
    },
    'active_segmentation_id': int | str | None,  # int (manual) or str "ai_swin_<ts>"
    'brush_size': int,                   # Brush radius in voxels (default 1)
    'paint_mode': str,                   # 'paint' | 'erase'
    'current_cmap': str,                 # Active colormap for 2D/3D (default 'bone')
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
| | | Query params: `ww`, `wc`, `cmap` | |

### Interactive Tools Routes
| Method | Route | Purpose | Returns |
|--------|-------|---------|---------|
| GET | `/hu_value` | Get HU value at (x,y,z) | JSON: {voxel, hu, scales} |
| GET | `/get_histogram` | Get volume histogram | JSON: {counts, bin_edges, segments} |
| GET | `/get_dicom_metadata` | Get technical metadata | JSON |
| POST | `/update_render_mode` | Change 3D render mode and colormap | JSON status |
| POST | `/upload_RT` | Upload RT Structure (.nrrd) | JSON status |

### Multi-Segmentation Routes
| Method | Route | Purpose | Returns |
|--------|-------|---------|---------|
| GET | `/get_segmentations` | List all segmentations + active ID | JSON |
| POST | `/create_segmentation` | Create new segmentation layer | JSON: {id, name, color, segmentations, active_id} |
| POST | `/delete_segmentation` | Delete segmentation by ID | JSON: {new_active_id} |
| POST | `/set_active_segmentation` | Switch active segmentation | JSON: {id, has_undo} |
| POST | `/toggle_segmentation_visibility` | Show/hide a segmentation | JSON: {id, visible} |
| POST | `/paint_voxel` | Paint/erase voxels with brush | JSON status |
| POST | `/fill_polygon` | Fill closed polygon region | JSON status |
| POST | `/undo_last_polygon` | Restore mask to pre-polygon state | JSON status |
| POST | `/clear_segmentation` | Zero-out active mask | JSON status |
| POST | `/export_segmentation` | Export active or all masks as NRRD | NRRD or ZIP |

### AI Segmentation Routes
| Method | Route | Purpose | Returns |
|--------|-------|---------|---------|
| POST | `/api/run_ai_segmentation` | Run Swin-UNETR inference | JSON: {status} |

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
  │   ├── Tool Buttons (Inspector, Window/Level, RT Struct, Histogram, Segmentation, AI)
  │   ├── 3D Mode Selector (Isosurface / MIP / MIP Inverted / Volume)
  │   ├── Colormap Dropdown (#colormapSelect) — affects 2D and 3D simultaneously
  │   └── Active Tool Panels (dynamic, shown/hidden per active button)
  │       ├── Window/Level Panel: sliders + spinners + presets
  │       ├── Contrast Editor Panel: histogram canvas + curve canvas
  │       ├── RT Struct Panel: NRRD upload form
  │       ├── Segmentation Panel: layer list, brush/polygon tool, export buttons
  │       └── AI Plugin Panel: Auto-Segmentar button (Swin-UNETR)
  │
  └── Quadrant Grid (#quadrant-grid)
      ├── Axial View
      │   ├── canvas#canvas_axial (image + LUT)
      │   ├── canvas#overlay_axial (crosshair / polygon preview)
      │   └── minimap#minimap_container_axial (visible only at zoom > 1.1×)
      ├── Sagital View  (same structure as Axial)
      ├── Coronal View  (same structure as Axial)
      └── 3D View (iframe#DicomRender → Bokeh server port 5010)
```

### JavaScript State Management (viewer.js)
```javascript
// Global State Objects

viewState = {
    ww: 400,                          // Window width (HU)
    wc: 40,                           // Window center (HU)
    baseImages: {},                   // Cached Image objects per view
    inspectorMode: false,             // 3D Inspector active
    segmentationMode: false,          // Segmentation tool active
    brushSize: 1,                     // Brush radius in voxels
    paintMode: 'paint',               // 'paint' | 'erase'
    segmentationTool: 'brush',        // 'brush' | 'polygon'
    colormap: 'gray',                 // Active colormap (e.g. 'gray','bone','hot')
    scales: { axial, coronal, sagittal }, // Aspect-ratio factors from backend
    lastVoxel: { x, y, z },           // Last clicked voxel (for crosshair persistence)
    activeSegmentationId: null,       // int or "ai_swin_<ts>"
    segmentations: []                 // Mirror of backend list
}

polygonState = {
    vertices: [],       // [{x, y}] in internal pixel coordinates
    isDrawing: false,
    currentView: null,  // 'axial' | 'sagital' | 'coronal'
    currentLayer: null, // Slice index
    lastOperation: null // For 1-level undo
}

segUndoState = {}  // { segmentationId: bool } — tracks undo availability per layer

zoomState = {
    axial:   { scale: 1, panX: 0, panY: 0, isDragging: false },
    sagital: { scale: 1, panX: 0, panY: 0, isDragging: false },
    coronal: { scale: 1, panX: 0, panY: 0, isDragging: false }
}

contrastState = {
    points: [{ x: -1024, y: 0 }, { x: 3071, y: 255 }],  // Control points
    activePointIndex: null,
    isDragging: false,
    histogramData: null,  // Server-fetched { counts, bin_edges, segments }
    cutoff: 7.0,
    logScale: false,
    minHU: -1024,
    maxHU: 3071,
    lut: Uint8ClampedArray(256)  // Lookup table applied to grayscale pixels
}
```

### Key Frontend Features

**1. Tool Activation System**
- Each tool button toggles visual state (`.btn-udg-rojo` class) via `setupPluginButton()`
- Shows/hides a corresponding panel container
- Inspector and Segmentation modes are **mutually exclusive** — activating one deactivates the other
- Segmentation mode changes cursor to crosshair; Inspector to pointer; default is grab

**2. Window/Level Control**
- Dual input: range sliders + numeric spinners with `+/-` buttons (step = 10)
- Presets: Lung (-600 / 1500), Bone (480 / 2500), Soft Tissue (40 / 400)
- Active preset button is highlighted (`.preset-active` class); any manual change clears highlight
- Debounced 250ms update from text fields; immediate update from sliders

**3. Colormap Selector**
- Dropdown (`#colormapSelect`) sets `viewState.colormap`
- 2D views reload immediately from server with the new `cmap` query parameter
- 3D colormap is sent to the server next time render mode changes (via `update_render_mode`)
- LUT is only applied in the browser when `colormap === 'gray'` (preserves colored medical maps)

**4. Zoom & Pan**
- Mouse wheel zoom (cursor-anchored, range 1×–10×)
- Click-drag panning; disabled while Inspector or Segmentation mode is active
- Both `canvas_*` and `overlay_*` receive the same CSS transform (`translate + scale`, origin `0 0`)
- Double-click resets zoom and pan to default
- **Minimap** (`updateMinimap(view)`): appears as a 120px thumbnail overlay when zoom > 1.1×, with a yellow viewport rectangle. Clicking the minimap repositions the pan.

**5. Histogram & Contrast Curve Editor**
- Two stacked canvases: `histogramCanvas` (bar chart) + `curveCanvas` (transfer function)
- Histogram colored by HU range: dark gray (air), yellow (fat), red (soft tissue), white (bone)
- Control points on the curve are draggable (mouse + touch); double-click adds a point
- Navigation buttons: Prev/Next/Add/Remove point; Reset restores linear 0→255
- Curve computes and applies a 256-entry LUT client-side (no server round-trip)
- `ResizeObserver` keeps canvas dimensions in sync with the sidebar panel width

**6. 3D Inspector (Crosshair)**
- Click or drag on any view to set the 3D intersection point
- Crosshair drawn at **internal pixel coordinates** on the overlay canvas; CSS transform positions it on screen automatically
- Backend `/hu_value` returns `{voxel: {x,y,z}, hu, scales}` — voxel coordinates used to sync other views
- `syncViewsFromVoxel()` updates the two other view sliders and calls `drawCrosshairsOnAllViews()`
- Crosshair persists across slice changes (redrawn from `viewState.lastVoxel` in `applyLutAndDraw`)
- Old `syncViews()` is deprecated (did not account for aspect-ratio scaling)

**7. Segmentation Tool**
- **Brush sub-tool**: radius selectable via radio buttons (1–5 voxels); click sends to `/paint_voxel`
- **Polygon sub-tool**: click to place vertices; preview line follows mouse; fill sent to `/fill_polygon`
  - Close polygon: click near first vertex (within 10px), or press **Enter**
  - Remove last vertex: **Backspace**; cancel all: **Escape**
  - Polygon color matches the active segmentation color; erase mode shows red
- **Undo**: 1-level per segmentation (full mask snapshot stored on backend)
- Max 5 concurrent segmentation layers; each auto-assigned a color from `SEGMENTATION_COLORS`
- Per-layer visibility toggle; delete; export active (`.nrrd`) or all (`.zip`)
- AI segmentation result injected as a new layer with id `"ai_swin_<timestamp>"`

**8. Loading Overlays**
- `showViewLoader(view)` / `hideViewLoader(view)` inject a spinner inside each image wrapper
- Used during polygon fill (all 3 views) and RT Struct upload

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
├── main.py                 # Flask application (~1430 lines)
│   ├── Routes (29 endpoints)
│   ├── DICOM processing functions
│   ├── 3D rendering logic
│   ├── Multi-segmentation system
│   ├── AI plugin orchestration
│   └── Session management
│
├── plugin_ia_swin/         # AI segmentation microservice
│   ├── run_ai_cli.py       # CLI script — called via subprocess
│   ├── best_swin_unetr_model.pth  # Trained model weights
│   └── environment.yml     # Conda env definition (medaimg)
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
│   │   └── viewer.js       # Frontend logic (~2300 lines)
│   └── img/
│       ├── udg_logo.png
│       └── leones_negros_logo.png
│
├── uploads/                # DICOM files (uploaded by users)
├── upload_nrrd/            # RT Structure files (*.nrrd)
├── anonimizado/            # Temporary export folder
│   └── AI_RESULTS/         # Swin-UNETR output masks (.nii.gz)
│       └── temp_dicom_<uid>/   # Isolated DICOM copy for each inference
│
├── requirements.txt        # ~280 dependencies
├── README.md               # Basic project description
├── ARCHITECTURE.md         # This document
└── .gitignore
```

### Key Code Locations

**DICOM Processing:**
- `process_dicom_folder()` - main.py:343-383
- `process_selected_dicom` route - main.py:417-486

**3D Rendering:**
- `create_or_get_plotter()` - main.py:105-155
- `update_3d_render()` - main.py:157-206 (modes: isosurface, mip, mip_inverted, volume)
- `add_RT_to_plotter()` - main.py:208-260
- `add_segmentation_to_plotter()` - main.py:262-307

**Image Generation:**
- `get_image()` route - main.py:621-680
- Window/level + colormap + segmentation overlay rendering - main.py:628-679

**Segmentation Backend:**
- `paint_voxel` route - main.py:739-815
- `fill_polygon` route - main.py:817-936
- `undo_last_polygon` route - main.py:938-971
- `create_segmentation` route - main.py:1011-1049

**AI Plugin:**
- `ejecutar_ia_swin()` - main.py:1238-1275 (subprocess orchestration)
- `normalize_ai_mask()` - main.py:1277-1321 (coordinate alignment)
- `api_run_ai_segmentation` route - main.py:1323-1425
- `plugin_ia_swin/run_ai_cli.py` - full inference pipeline

**Frontend Interactivity:**
- Tool activation (`setupPluginButton`) - viewer.js:92-177
- Window/Level controls - viewer.js:183-284
- Colormap selector - viewer.js:873-886
- Zoom/Pan + Minimap - viewer.js:890-1044
- 3D Inspector (crosshair) - viewer.js:1047-1275
- Segmentation management UI - viewer.js:1277-1498
- Brush/Polygon drawing - viewer.js:1499-2017
- AI plugin button - viewer.js:2019-2074
- Minimap (`updateMinimap`) - viewer.js:2230-2279
- Crosshair persistence (`drawCrosshairFromVoxel`) - viewer.js:2281-2293

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

---

## 12. Multi-Segmentation System

### Overview
The application supports up to **5 concurrent manual segmentation layers** per user session, plus an unlimited number of AI-generated layers (each time-stamped). All masks are stored as `uint8` NumPy arrays with shape `(Z, Y, X)` containing values `0` (background) or `255` (foreground).

### Backend Data Model
```python
user_data['segmentations'] = {
    0: {
        'name': 'Tumor',
        'mask': np.zeros((Z, Y, X), dtype=np.uint8),
        'color': '#00FFFF',          # From SEGMENTATION_COLORS list
        'visible': True,
        'last_polygon_operation': None  # or snapshot dict for undo
    },
    # ... up to index 4 for manual layers
    'ai_swin_1712345678': {          # AI layers use string keys
        'name': 'Segmentación IA',
        'mask': np.ndarray,
        'color': '#00FFFF',
        'visible': True
        # Note: AI layers do NOT have last_polygon_operation
    }
}
```

### Color Palette (fixed assignment by slot index)
```python
SEGMENTATION_COLORS = ['#00FFFF', '#ADFF2F', '#FF8C00', '#FF00FF', '#FFD700']
#                       Cyan       Green-Yellow  Orange   Magenta    Gold
```

### Segmentation Tools

#### Brush Tool
- Sends pixel coordinates + `brush_size` radius to `/paint_voxel`
- Backend paints a square kernel of radius `brush_size` around the click
- Coordinate conversion: same formula as `/hu_value` (scaled by aspect-ratio factors)
- Supports paint (255) and erase (0) modes

#### Polygon Tool
- Vertices accumulated client-side in `polygonState.vertices`
- Preview line drawn from last vertex to mouse cursor (dashed)
- Fill preview shown when ≥ 3 vertices (translucent color)
- Closed by: clicking near first vertex (within 10px), pressing Enter, or calling `closeAndFillPolygon()`
- Sends all vertices + view + layer to `/fill_polygon`
- Backend uses `skimage.draw.polygon()` to rasterize into the mask
- Keyboard shortcuts: **ESC** cancel, **Backspace** remove last vertex, **Enter** close and fill

### Undo System
- 1-level undo per segmentation layer
- Before each `/fill_polygon` call, backend stores a **full mask copy** (`mask_before`) in `last_polygon_operation`
- `/undo_last_polygon` uses `np.copyto()` to restore the snapshot
- Undo state is cleared on: polygon success, segmentation clear, and layer deletion
- UI: undo button styled orange (`.btn-outline-warning`) when undo is available

### 2D Rendering (Overlay)
Each segmentation layer is composited as an `imshow` overlay in `get_image()`:
```python
for seg_entry in user_data.get('segmentations', {}).values():
    if not seg_entry.get('visible', True):
        continue
    seg_cmap = LinearSegmentedColormap.from_list(
        f"seg_{id(seg_entry)}", ['#000000', seg_entry['color']]
    )
    ax.imshow(ma.masked_where(seg == 0, seg), cmap=seg_cmap,
              vmin=0, vmax=255, alpha=0.6, aspect='auto', interpolation='nearest')
```

### 3D Rendering (Segmentation Surface)
`add_segmentation_to_plotter()` converts the active segmentation mask to a 3D surface:
- Creates a `pv.ImageData` grid with the same spacing/origin as the main volume
- Runs `contour([1.0])` to extract the iso-surface
- Adds as a solid cyan mesh (`opacity=1.0`, `name="ia_segmentation"`)
- Called from `update_3d_render()` if an active segmentation exists

### Export
- **Active segmentation**: exported as a single `.nrrd` file with full spatial metadata (spacing, origin, directions)
- **All segmentations**: exported as a `.zip` containing one `.nrrd` per layer
- NRRD header includes: `space`, `kinds`, `space directions`, `space origin`

### Complete Segmentation Data Flow
```
USER CREATES SEGMENTATION
         │
         ▼
POST /create_segmentation {name}
         │
         ├─→ Assign next free slot (0-4)
         ├─→ Allocate np.zeros(dims, dtype=uint8)
         └─→ Return {id, name, color}

USER DRAWS WITH BRUSH
         │
         ▼
JavaScript: handleSegmentationClick(view, evt)
         │
         ├─→ cssToPngPixels() → {xPix, yPix}
         │
         ▼
POST /paint_voxel {view, xPix, yPix, layer, brush_size, mode}
         │
         ├─→ Convert pixel → voxel (same as /hu_value)
         ├─→ Paint square kernel: seg_mask[z, ny, nx] = 255 or 0
         └─→ Return success → Frontend reloads image

USER DRAWS POLYGON
         │
         ▼
JavaScript: accumulates polygonState.vertices
         │
         ▼
POST /fill_polygon {view, layer, vertices, mode}
         │
         ├─→ Store mask snapshot (last_polygon_operation)
         ├─→ skimage.draw.polygon() → rr, cc
         ├─→ seg_mask[layer, rr, cc] = 255 or 0
         └─→ Return success → Frontend reloads all views
```

---

## 13. AI Segmentation Plugin — Swin-UNETR

### Architecture Overview
The AI plugin runs as a **subprocess** in a separate Conda environment, completely isolated from the Flask process to avoid dependency conflicts between medical imaging libraries.

```
Flask Process (main.py)
        │
        │ subprocess.run(["python", "run_ai_cli.py", ...])
        │ (captures stdout, waits for completion)
        ▼
Conda env: medaimg
        │
        │ run_ai_cli.py — 5-step pipeline
        │    │
        │    ├─ 1. sitk.ImageSeriesReader → read DICOM natively
        │    ├─ 2. TorchIO preprocessing → resample + crop + normalize
        │    ├─ 3. SwinUNETR inference → sliding window
        │    ├─ 4. sitk.ResampleImageFilter → reproject to native space
        │    └─ 5. sitk.WriteImage → save MASK_FINAL_<ts>.nii.gz
        │
        │ Prints single JSON line to stdout:
        │   {"status":"success","mask_path":"/abs/path/MASK_FINAL.nii.gz"}
        ▼
Flask reads JSON, loads mask via SimpleITK, injects into session
```

### Python Environment
- **Conda environment name**: `medaimg`
- **Python executable** (hardcoded): `C:\Users\jesus\anaconda3\envs\medaimg\python.exe`
- **Key dependencies** (inside medaimg env):
  - `torch` (CUDA or CPU fallback)
  - `monai` — SwinUNETR model, `sliding_window_inference`
  - `torchio` — spatial transforms, intensity normalization
  - `SimpleITK` — DICOM reading, image resampling
  - `nibabel` — NIfTI file I/O
  - Environment defined in `plugin_ia_swin/environment.yml`

### 5-Step Inference Pipeline (`run_ai_cli.py`)

**Step 1 — Native DICOM Read**
```python
reader = sitk.ImageSeriesReader()
dicom_names = reader.GetGDCMSeriesFileNames(dicom_dir)
reader.SetFileNames(dicom_names)
native_sitk = reader.Execute()
sitk.WriteImage(native_sitk, "input_vol_native.nii.gz")
```
Preserves original voxel spacing and orientation as reference for reprojection.

**Step 2 — TorchIO Preprocessing**
```python
spatial_transform = tio.Compose([
    tio.Resample(1.0),                    # Isotropic 1mm spacing
    tio.CropOrPad((160, 192, 160))        # Fixed model input size
])
intensity_transform = tio.RescaleIntensity(
    out_min_max=(0, 1), percentiles=(0.1, 99.9)
)
```

**Step 3 — Neural Network Inference**
```python
model = SwinUNETR(
    in_channels=1, out_channels=8,        # 8-class segmentation
    feature_size=24, use_checkpoint=False
)
logits = sliding_window_inference(
    input_tensor,
    roi_size=(96, 96, 96),
    sw_batch_size=4,
    overlap=0.5,
    mode="gaussian"
)
mask_array = torch.argmax(logits, dim=1, keepdim=True)
```

**Step 4 — Reproject to Native Space (critical fix for coordinate alignment)**
```python
pred_nifti = nib.Nifti1Image(mask_array, subj_spat.mri.affine)
pred_sitk = sitk.ReadImage(temp_mask_path)
resampler = sitk.ResampleImageFilter()
resampler.SetReferenceImage(native_sitk)          # Use original DICOM as template
resampler.SetInterpolator(sitk.sitkNearestNeighbor)
final_mask_sitk = resampler.Execute(pred_sitk)
```
This step ensures the output mask has the **exact same shape, spacing, and orientation** as the original DICOM, regardless of what TorchIO did internally.

**Step 5 — Save**
```python
sitk.WriteImage(final_mask_sitk, f"MASK_FINAL_{int(time.time())}.nii.gz")
print(json.dumps({"status": "success", "mask_path": mask_out_path}))
```

### Flask-Side Integration (`api_run_ai_segmentation`)

After the subprocess completes:
1. Mask is read back via `SimpleITK` (returns Z, Y, X array directly)
2. **Z-axis sync**: Detects if pydicom ordered slices opposite to SimpleITK's physical ordering; if so, flips `mask_data[::-1]`
3. **Dimension sync**: If shape doesn't exactly match `user_data['dims']`, applies `scipy.ndimage.zoom` with order=0
4. **Class extraction**: Finds `max_class = np.max(mask_data)`; converts to binary `(mask == max_class) * 255`
5. Injects as a new segmentation entry with key `"ai_swin_<timestamp>"`

### DICOM Isolation
Before calling the subprocess, Flask:
- Creates `anonimizado/AI_RESULTS/temp_dicom_<uid>/` directory
- Clears any previous files from that directory
- Copies only the files belonging to the active series (by absolute path)
- Passes this isolated directory as `--input` to the CLI

### AI Segmentation Data Flow
```
USER CLICKS "Auto-Segmentar"
         │
         ▼
POST /api/run_ai_segmentation
         │
         ├─→ Resolve DICOM file paths from session
         ├─→ Copy files to temp_dicom_<uid>/
         │
         ├─→ ejecutar_ia_swin(temp_dicom_dir, out_dir)
         │    │
         │    └─→ subprocess.run(["medaimg/python", "run_ai_cli.py", ...])
         │         └─→ Returns JSON: {"status","mask_path"}
         │
         ├─→ sitk.ReadImage(mask_path) → mask_data (Z,Y,X)
         ├─→ Z-axis flip if orientation mismatch
         ├─→ scipy.zoom if shape mismatch
         ├─→ Binarize: max_class → 255
         │
         ├─→ user_data['segmentations']['ai_swin_<ts>'] = {mask, color, ...}
         ├─→ user_data['active_segmentation_id'] = 'ai_swin_<ts>'
         └─→ Return {"status": "success"}
                  │
                  ▼
         Frontend reloads all 3 views + 3D iframe
```

### Output Files
| File | Location | Description |
|------|----------|-------------|
| `input_vol_native.nii.gz` | `anonimizado/AI_RESULTS/` | Intermediate NIfTI for preprocessing |
| `temp_mask.nii.gz` | `anonimizado/AI_RESULTS/` | Raw model output (TorchIO space) |
| `MASK_FINAL_<ts>.nii.gz` | `anonimizado/AI_RESULTS/` | Final mask in native DICOM space |

### Known Limitations
- Python executable path is **hardcoded** to one machine's Conda install
- Inference is **synchronous** — Flask worker blocks for the entire duration (30s–several minutes)
- Model weights (`best_swin_unetr_model.pth`) are tracked by Git LFS or stored locally; not in the repo by default
- 8-class output: only the dominant class (`max_class`) is surfaced to the user — multi-class visualization is not yet implemented

---

## Conclusion

This application is a **feature-rich medical imaging viewer** with impressive 3D visualization capabilities, but architecturally suited for **educational/research environments** rather than production clinical use. The lack of persistent storage and security hardening would need to be addressed for HIPAA-compliant deployment.

**Improvements:**
- ✅ Fixed zoom interaction issues with HU Picker and 3D Inspector (2025-11-30)
- ✅ Resolved coordinate mapping bugs with aspect ratio scaling
- ✅ Improved visual consistency at all zoom levels
- ✅ Multi-layer manual segmentation system (brush + polygon tools, undo, export)
- ✅ Minimap navigation overlay for zoomed-in views
- ✅ AI-powered auto-segmentation via Swin-UNETR plugin
- ✅ Colormap selector for 2D and 3D views
- ✅ MIP Inverted rendering mode

**Strengths:**
- Clean separation of 2D and 3D rendering pipelines
- Sophisticated frontend with zoom, pan, minimap, histogram editing
- Multi-user session isolation
- Flexible RT Structure overlay + up to 5 manual segmentation layers
- AI segmentation isolated in its own process/environment (no dependency conflicts)
- **Robust coordinate mapping system** (fixed 2025-11-30)
- **Precise HU measurements at any zoom level** (fixed 2025-11-30)

**Weaknesses:**
- No data persistence (everything lost on server restart)
- Memory-intensive session storage (full volumes + masks per user)
- Missing production security features
- No cleanup mechanisms for uploaded files
- AI inference is synchronous (blocks Flask worker for minutes)
- Python executable path for AI is hardcoded to one machine
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
