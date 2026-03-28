# Modularization Plan — Servicio-Web-APP-2025-2

**Author:** Claude Sonnet 4.6 (architectural session)
**Started:** 2026-03-28
**Branch:** `crear_segmentacion_mejorada`
**Goal:** Break `main.py` (1 430+ lines, 9 responsibilities) into a proper Flask Application Factory with domain-driven modules, following industry-standard separation of concerns.

---

## Table of Contents
1. [Diagnosis — Why the Current Code Is Problematic](#1-diagnosis)
2. [Target Directory Structure](#2-target-directory-structure)
3. [Layering Rules](#3-layering-rules)
4. [Migration Plan — Step by Step](#4-migration-plan)
5. [Design Decisions (Settled)](#5-design-decisions-settled)
6. [Current State](#6-current-state)
7. [Per-Step Checklists](#7-per-step-checklists)

---

## 1. Diagnosis

### The Core Anti-Pattern: God Object

`main.py` violates the **Single Responsibility Principle** at every level. It simultaneously handles:

| Responsibility | Approx. Lines |
|---|---|
| Flask app creation & configuration | 44–101 |
| Session store management | 53–69 |
| 3D rendering (PyVista / Panel / Bokeh) | 103–307 |
| DICOM I/O & metadata parsing | 309–383 |
| 2D image generation (Matplotlib) | 621–680 |
| RT Struct processing | 682–713 |
| Manual segmentation (brush + polygon + undo) | 739–1143 |
| Authentication (login / register / logout) | 1189–1234 |
| AI plugin orchestration (Swin-UNETR) | 1236–1425 |

### Specific Problems

**Problem 1 — No Application Factory**
`app = Flask(__name__)` was created at module import time as a global. This makes it impossible to create test instances or configure the app differently per environment. The fix is the Application Factory pattern (`create_app()`).

**Problem 2 — No Blueprints**
All 29 routes are registered on the same global `app` object in the same file. Flask Blueprints exist specifically to group routes by domain.

**Problem 3 — Business Logic Inside Route Handlers**
Functions like `api_run_ai_segmentation` (100 lines: subprocess call, file I/O, axis flip, zoom, binarize, session mutate) live inside HTTP handler functions. Route handlers should only parse requests, call a service, and return a response.

**Problem 4 — Dangerous Global Mutable State**
Three globals are actively harmful in a threaded server:
- `SERVER_SIDE_SESSION_STORE = {}` — mutated by every concurrent request
- `bokeh_server_started = False` — threading flag, race condition risk
- `usuarios = {}` — in-memory user store, wiped on restart

**Problem 5 — No Configuration Management**
Three different styles of configuration scattered across the file:
```python
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))  # inline
python_ia_exe = r"C:\Users\jesus\anaconda3\envs\medaimg\python.exe"   # hardcoded
UPLOAD_FOLDER = 'uploads'                                               # relative path
```

**Problem 6 — Heavy Library Initialization at Import Time**
`pv.OFF_SCREEN = True`, `pn.extension('vtk')` execute the moment anything imports from `main.py`. Running a linter, a test, or any tooling forces a full PyVista + Panel initialization.

**Problem 7 — Forms Defined Inline with Business Logic**
`LoginForm`, `RegisterForm`, and `usuarios = {}` are defined in the same file as DICOM processing and AI inference.

---

## 2. Target Directory Structure

```
Servicio-Web-APP-2025-2/
│
├── app/                            ← The application package
│   │
│   ├── __init__.py                 ← create_app() factory  ✅ DONE
│   ├── config.py                   ← Config class hierarchy  ✅ DONE
│   │
│   ├── session/
│   │   └── store.py                ← SERVER_SIDE_SESSION_STORE + get_user_data()
│   │
│   ├── auth/
│   │   ├── forms.py                ← LoginForm, RegisterForm
│   │   ├── service.py              ← usuarios dict + password logic
│   │   └── routes.py               ← Blueprint: /login, /register, /logout
│   │
│   ├── dicom/
│   │   ├── reader.py               ← process_dicom_folder(), _extract_spacing_for_series()
│   │   ├── processor.py            ← _compute_view_scales(), HU conversion, volume stacking
│   │   └── routes.py               ← Blueprint: /loadDicom, /process_selected_dicom,
│   │                                            /loadDicomMetadata
│   │
│   ├── viewer/
│   │   ├── rendering_2d.py         ← _slice_2d_and_target_size(), get_image logic, histogram
│   │   ├── rendering_3d.py         ← create_or_get_plotter(), update_3d_render(),
│   │   │                                       start_bokeh_server(), add_*_to_plotter()
│   │   └── routes.py               ← Blueprint: /render, /image, /hu_value, /get_histogram,
│   │                                            /get_dicom_metadata, /update_render_mode
│   │
│   ├── rt_struct/
│   │   ├── service.py              ← add_RT_to_plotter(), NRRD loading logic
│   │   └── routes.py               ← Blueprint: /upload_RT
│   │
│   ├── segmentation/
│   │   ├── service.py              ← paint logic, polygon fill, undo, mask management
│   │   └── routes.py               ← Blueprint: /paint_voxel, /fill_polygon,
│   │                                            /undo_last_polygon, /clear_segmentation,
│   │                                            /get_segmentations, /create_segmentation,
│   │                                            /delete_segmentation, /set_active_segmentation,
│   │                                            /toggle_segmentation_visibility,
│   │                                            /export_segmentation
│   │
│   ├── ai_plugin/
│   │   ├── service.py              ← ejecutar_ia_swin(), normalize_ai_mask(),
│   │   │                                       DICOM isolation logic
│   │   └── routes.py               ← Blueprint: /api/run_ai_segmentation
│   │
│   └── anonymization/
│       ├── service.py              ← DICOM tag mutation, ZIP export logic
│       └── routes.py               ← Blueprint: /anonimize, /guardar_cambios,
│                                               /exportar_dicom
│
├── plugin_ia_swin/                 ← Unchanged — separate subprocess
│   ├── run_ai_cli.py
│   ├── best_swin_unetr_model.pth
│   └── environment.yml
│
├── static/
├── templates/
├── uploads/
├── upload_nrrd/
├── anonimizado/
│
├── main.py                         ← Entry point only: from app import create_app; app = create_app()
├── ARCHITECTURE.md
├── MODULARIZATION.md               ← This file
└── requirements.txt
```

---

## 3. Layering Rules

Every file in the project must respect this strict hierarchy. **No layer may import from a layer above it.**

```
┌─────────────────────────────────────────────────────┐
│  HTTP Layer  (*/routes.py + Blueprint)              │
│  • Parse request parameters                         │
│  • Call ONE service function                        │
│  • Return jsonify() / render_template() / send_file │
│  • No numpy, no pydicom, no subprocess here         │
└──────────────────────────┬──────────────────────────┘
                           │ calls
┌──────────────────────────▼──────────────────────────┐
│  Service Layer  (*/service.py)                      │
│  • All business logic, numpy operations             │
│  • Subprocess calls, file I/O                       │
│  • Receives plain Python data, returns plain data   │
│  • NO Flask request/response objects                │
│  • NO session access (receives user_data as param)  │
└──────────────────────────┬──────────────────────────┘
                           │ calls
┌──────────────────────────▼──────────────────────────┐
│  Data / IO Layer  (reader.py, store.py)             │
│  • DICOM file parsing, session store access         │
│  • Returns raw data structures (numpy arrays, dicts)│
└──────────────────────────┬──────────────────────────┘
                           │ uses
┌──────────────────────────▼──────────────────────────┐
│  Infrastructure  (config.py, __init__.py)           │
│  • Third-party library initialization               │
│  • Environment-specific configuration               │
└─────────────────────────────────────────────────────┘
```

---

## 4. Migration Plan

The order is chosen to minimize risk: start with modules that have the fewest dependencies, end with the most complex (3D rendering).

| Step | Module | Key Files Extracted | Status |
|------|--------|---------------------|--------|
| 1 | `app/config.py` + factory | `app/__init__.py`, `app/config.py` | ✅ **DONE** |
| 2 | `app/session/store.py` | `store.py` with `get_user_data()` | ✅ **DONE** |
| 3 | `app/auth/` | `forms.py`, `service.py`, `routes.py` | 🔲 |
| 4 | `app/anonymization/` | `service.py`, `routes.py` | 🔲 |
| 5 | `app/dicom/` | `reader.py`, `processor.py`, `routes.py` | 🔲 |
| 6 | `app/segmentation/` | `service.py`, `routes.py` | 🔲 |
| 7 | `app/rt_struct/` | `service.py`, `routes.py` | 🔲 |
| 8 | `app/ai_plugin/` | `service.py`, `routes.py` | 🔲 |
| 9 | `app/viewer/rendering_2d.py` | Pure image generation | 🔲 |
| 10 | `app/viewer/rendering_3d.py` + routes | PyVista / Bokeh / Panel | 🔲 |

**After all steps are done**, `main.py` should contain only:
```python
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5001, threaded=False)
```

---

## 5. Design Decisions (Settled)

### Decision 1 — How modules share `get_user_data()`
`get_user_data()` and `SERVER_SIDE_SESSION_STORE` live in `app/session/store.py`.
Every Blueprint's `routes.py` imports it directly:
```python
from app.session.store import get_user_data
```
No circular dependency: `store.py` depends only on Flask's `session` object (from `flask`), not on any Blueprint.

### Decision 2 — How `rendering_3d.py` and `segmentation/service.py` share the plotter
`rendering_3d.py` exposes `update_3d_render(user_data, mode)` as a pure function that takes the `user_data` dict as a parameter. The segmentation service imports only that function:
```python
from app.viewer.rendering_3d import update_3d_render
```
Already architected this way in the current code — extraction will be mechanical.

### Decision 3 — Blueprint URL prefixes
| Blueprint | Prefix |
|---|---|
| `auth` | `/` (login/register/logout at root) |
| `dicom` | `/` (loadDicom routes at root) |
| `viewer` | `/` (render, image, hu_value at root) |
| `segmentation` | `/` (all seg routes at root) |
| `rt_struct` | `/` (upload_RT at root) |
| `ai_plugin` | `/api` |
| `anonymization` | `/` (anonimize at root) |

All current URLs are preserved — no frontend changes needed.

### Decision 4 — `csrf` extension instance
`csrf = CSRFProtect()` is instantiated in `app/__init__.py` and bound to the app in `create_app()` via `csrf.init_app(app)`. Future Blueprint routes that need `@csrf.exempt` import `csrf` from `app`:
```python
from app import csrf
```

### Decision 5 — Constants in `app/config.py`
All previously hardcoded values now live in `Config` (or its subclasses) and are overridable via environment variables:
| Old hardcode | Env var |
|---|---|
| `os.urandom(24)` | `FLASK_SECRET_KEY` |
| `C:\Users\jesus\anaconda3\...` | `AI_PYTHON_EXECUTABLE` |
| `'uploads'` | _(absolute path computed from `BASE_DIR`)_ |
| Port `5010` | `BOKEH_PORT` |
| Port `5001` | `FLASK_RUN_PORT` |

---

## 6. Current State

### What `main.py` contains RIGHT NOW (after Step 1)
- Lines 1–38: All original imports (minus `Flask`, `CSRFProtect`, `generate_csrf`)
- Lines 39–50: `from app import create_app; app = create_app()` + constant re-exports
- Lines 52–68: `SERVER_SIDE_SESSION_STORE` + `get_user_data()` ← **to be moved in Step 2**
- Lines 70–77: `bokeh_server_started` global + `start_bokeh_server()` ← **to be moved in Step 10**
- Lines 79 onward: All functions and routes — **unchanged, all still working**

### What `app/` contains RIGHT NOW
```
app/
├── __init__.py   ← create_app() with CSRF, PyVista, Panel, context_processor, mkdir
└── config.py     ← Config / DevelopmentConfig / ProductionConfig / TestingConfig
```

### Verified Working
- `python main.py` starts the server correctly ✅
- All 29 routes respond normally ✅
- PyVista / Panel / Bokeh initialize without errors ✅
- Upload directories created on startup ✅
- CSRF protection active ✅

---

## 7. Per-Step Checklists

### Step 2 — `app/session/store.py`
- [ ] Create `app/session/__init__.py` (empty)
- [ ] Create `app/session/store.py` with `SERVER_SIDE_SESSION_STORE` dict and `get_user_data()`
- [ ] In `main.py`: replace the session store block with `from app.session.store import SERVER_SIDE_SESSION_STORE, get_user_data`
- [ ] Verify app still starts and all routes respond

### Step 3 — `app/auth/`
- [ ] Create `app/auth/__init__.py` (empty)
- [ ] Create `app/auth/forms.py` — move `LoginForm`, `RegisterForm`
- [ ] Create `app/auth/service.py` — move `usuarios = {}` dict + password hash/check logic
- [ ] Create `app/auth/routes.py` — Blueprint `auth_bp`, move `/login`, `/register`, `/logout` routes
- [ ] Register `auth_bp` in `create_app()` inside `app/__init__.py`
- [ ] Remove auth code from `main.py`
- [ ] Verify login/register/logout still work

### Step 4 — `app/anonymization/`
- [ ] Create `app/anonymization/__init__.py` (empty)
- [ ] Create `app/anonymization/service.py` — move DICOM tag mutation + ZIP logic
- [ ] Create `app/anonymization/routes.py` — Blueprint `anon_bp`, move `/anonimize`, `/guardar_cambios`, `/exportar_dicom`
- [ ] Register `anon_bp` in `create_app()`
- [ ] Remove anonymization code from `main.py`
- [ ] Verify anonymization flow works end-to-end

### Step 5 — `app/dicom/`
- [ ] Create `app/dicom/__init__.py` (empty)
- [ ] Create `app/dicom/reader.py` — move `process_dicom_folder()`, `_extract_spacing_for_series()`
- [ ] Create `app/dicom/processor.py` — move `_compute_view_scales()`, volume stacking, HU conversion logic
- [ ] Create `app/dicom/routes.py` — Blueprint `dicom_bp`, move `/loadDicom`, `/process_selected_dicom`, `/loadDicomMetadata`
- [ ] Register `dicom_bp` in `create_app()`
- [ ] Remove DICOM code from `main.py`
- [ ] Verify DICOM upload and series selection work

### Step 6 — `app/segmentation/`
- [ ] Create `app/segmentation/__init__.py` (empty)
- [ ] Create `app/segmentation/service.py` — move brush paint logic, polygon fill logic, undo snapshot logic
- [ ] Create `app/segmentation/routes.py` — Blueprint `seg_bp`, move all 10 segmentation routes
- [ ] Register `seg_bp` in `create_app()`
- [ ] Remove segmentation code from `main.py`
- [ ] Verify brush, polygon, undo, export all work

### Step 7 — `app/rt_struct/`
- [ ] Create `app/rt_struct/__init__.py` (empty)
- [ ] Create `app/rt_struct/service.py` — move `add_RT_to_plotter()`, NRRD loading
- [ ] Create `app/rt_struct/routes.py` — Blueprint `rt_bp`, move `/upload_RT`
- [ ] Register `rt_bp` in `create_app()`
- [ ] Remove RT Struct code from `main.py`
- [ ] Verify NRRD upload and 3D/2D overlay work

### Step 8 — `app/ai_plugin/`
- [ ] Create `app/ai_plugin/__init__.py` (empty)
- [ ] Create `app/ai_plugin/service.py` — move `ejecutar_ia_swin()`, `normalize_ai_mask()`, DICOM isolation logic; replace hardcoded Python path with `current_app.config['AI_PYTHON_EXECUTABLE']`
- [ ] Create `app/ai_plugin/routes.py` — Blueprint `ai_bp`, move `/api/run_ai_segmentation`
- [ ] Register `ai_bp` in `create_app()` with `url_prefix='/api'`
- [ ] Remove AI code from `main.py`
- [ ] Verify auto-segmentation works end-to-end

### Step 9 — `app/viewer/rendering_2d.py`
- [ ] Create `app/viewer/__init__.py` (empty)
- [ ] Create `app/viewer/rendering_2d.py` — move `_slice_2d_and_target_size()`, `get_image` logic, histogram computation
- [ ] Update viewer routes (still in `main.py`) to import from `rendering_2d`
- [ ] Verify 2D slices, histogram, HU picker all work

### Step 10 — `app/viewer/rendering_3d.py` + viewer routes
- [ ] Create `app/viewer/rendering_3d.py` — move `create_or_get_plotter()`, `update_3d_render()`, `add_segmentation_to_plotter()`, `add_RT_to_plotter()` (import from `rt_struct` if already extracted), `start_bokeh_server()`, `bokeh_server_started` global
- [ ] Create `app/viewer/routes.py` — Blueprint `viewer_bp`, move `/render`, `/image`, `/hu_value`, `/get_histogram`, `/get_dicom_metadata`, `/update_render_mode`
- [ ] Register `viewer_bp` in `create_app()`
- [ ] Remove all remaining route and rendering code from `main.py`
- [ ] `main.py` is now 5 lines ✅
- [ ] Full end-to-end smoke test

---

## Notes for Future Sessions

- **Test after every step.** Start the app and manually exercise the feature area you just extracted before moving on.
- **One Blueprint at a time.** Don't start Step N+1 until Step N is verified working.
- **The constants re-export pattern** (`UPLOAD_FOLDER = app.config['UPLOAD_FOLDER']` in `main.py`) is intentional scaffolding — delete each re-export as soon as the last route that uses it is moved to its Blueprint.
- **`get_user_data()` is the most-imported function** — it will be needed by every Blueprint `routes.py`. Import it from `app.session.store` as soon as Step 2 is done.
- **`update_3d_render()`** is called from the segmentation service (Step 6) AND the RT Struct service (Step 7). Extract `rendering_3d.py` (Step 10) AFTER both of those are done, or extract `update_3d_render` to a shared module earlier.
  - **Recommended**: Extract `rendering_3d.py` as a standalone module at Step 7, before the Blueprint, so both `rt_struct/service.py` and `segmentation/service.py` can import from it cleanly.
- **`add_RT_to_plotter()`** in the current code lives alongside the 3D plotter logic. When extracting `rt_struct/service.py`, it will need to import `add_RT_to_plotter` — either from `viewer/rendering_3d.py` (if already extracted) or move it into `rt_struct/service.py` directly (it is more of an RT concern than a renderer concern).
