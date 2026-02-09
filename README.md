# 🏥 Servicio Web APP 2025 - Aplicación Web de Procesamiento de Imágenes Médicas

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.3-green.svg)](https://flask.palletsprojects.com/)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()

## 📋 Descripción

**Servicio-Web-APP-2025** es una aplicación web de servicio social desarrollada para la **Universidad de Guadalajara** que permite el procesamiento, visualización y análisis avanzado de imágenes médicas DICOM con herramientas profesionales de radiología.

Esta plataforma proporciona capacidades completas para:
- 📊 Visualización de imágenes DICOM (CT, MRI, etc.)
- 🎯 Renderización 3D volumétrica interactiva
- 🔍 Análisis detallado con herramientas de medición precisas
- 🛡️ Anonimización segura de datos de pacientes
- 📥 Carga y visualización de estructuras de segmentación (NRRD)

**Casos de Uso Ideales:**
- 👨‍⚕️ Educación médica y formación en radiología
- 🔬 Investigación biomédica y análisis de imágenes
- 🎓 Enseñanza de análisis DICOM a estudiantes
- 💼 Demostración de visualizadores médicos
- 📋 Análisis de casos clínicos para educación

---

## 📖 Tabla de Contenidos

- [🎯 Características Principales](#-características-principales)
- [🛠️ Stack Tecnológico](#️-stack-tecnológico)
- [📦 Instalación](#-instalación)
- [🚀 Uso Rápido](#-uso-rápido)
- [📁 Estructura del Proyecto](#-estructura-del-proyecto)
- [🔌 API Endpoints](#-api-endpoints)
- [⚙️ Configuración](#️-configuración)
- [🔒 Seguridad](#-seguridad)
- [❓ FAQ & Troubleshooting](#-faq--troubleshooting)
- [⚠️ Limitaciones Conocidas](#️-limitaciones-conocidas)
- [🤝 Contribuciones](#-contribuciones)
- [⚖️ Licencia](#️-licencia)
- [📞 Contacto y Soporte](#-contacto-y-soporte)
- [🗺️ Roadmap Futuro](#️-roadmap-futuro)

---

## 🎯 Características Principales

### 2D Viewer Multi-plano
- **Visualización Axial, Sagital y Coronal**: Tres planos ortogonales simultáneamente sincronizados
- **Window/Level Controls Avanzados**: Ajuste de contraste mediante controles deslizantes y presets
  - 🫁 **Pulmón**: WW=1500, WC=-600
  - 🦴 **Hueso**: WW=2500, WC=480
  - 🧬 **Tejido Blando**: WW=400, WC=40
- **Zoom y Pan Fluido**: Navegación con zoom centrado en cursor (hasta 10x)
- **Herramienta HU Picker**: Medición de valores Hounsfield (HU) precisos en cualquier punto
- **Editor de Histograma**: Control avanzado de contraste mediante curvas personalizables

### 3D Viewer
- **Múltiples Modos de Renderización**:
  - 🎨 **Isosurface**: Visualización de superficies óseas y de piel
  - 📊 **MIP (Maximum Intensity Projection)**: Proyección de máxima intensidad
  - 🌊 **Volume Rendering**: Renderización volumétrica completa
- **Interacción 3D en Tiempo Real**: Rotación, zoom y pan fluidos
- **Overlay de Segmentaciones**: Carga de máscaras RT (NRRD) en 2D y 3D

### Inspector 3D (Crosshair)
- Sincronización automática de vistas: hacer clic en una vista actualiza las otras
- Marcas precisas en coordenadas anatómicas 3D
- Visualización de posición en tiempo real (X, Y, Z)

### Herramientas Avanzadas
- **Anonimización de DICOM**: Edición segura y exportación de imágenes sin identificadores
- **Extracción de Metadata**: Información técnica detallada de series
- **Histogramas**: Análisis de distribución de intensidades
- **Exportación Segura**: Descarga de series anonimizadas en ZIP

---

## 🛠️ Stack Tecnológico

### Backend
| Componente | Versión | Propósito |
|-----------|---------|-----------|
| **Flask** | 3.0.3 | Framework web (rutas, plantillas, sesiones) |
| **PyDICOM** | 2.4.4 | Lectura y procesamiento de archivos DICOM |
| **PyVista** | 0.44.2 | Motor de renderización 3D (wrapper de VTK) |
| **NumPy** | 1.24.4 | Procesamiento de arrays numéricos |
| **Matplotlib** | 3.3.2 | Generación de imágenes 2D en PNG |
| **Panel/Bokeh** | 1.2.3 / 3.1.1 | Embedding de visualizaciones 3D |
| **pynrrd** | 1.1.3 | Lectura/escritura de archivos NRRD |

### Frontend
| Componente | Versión | Propósito |
|-----------|---------|-----------|
| **Bootstrap** | 5.3.3 | Framework CSS y diseño responsivo |
| **JavaScript (ES6)** | Vanilla | Interactividad cliente (viewer.js) |
| **Canvas HTML5** | Nativo | Renderización de imágenes 2D |
| **Bootstrap Icons** | 1.11.3 | Iconografía de interfaz |

### Seguridad
| Componente | Versión | Propósito |
|-----------|---------|-----------|
| **Flask-WTF** | 1.2.1 | Protección CSRF |
| **Werkzeug** | 3.0.6 | Hash seguro de contraseñas (SHA-256) |

---

## 📦 Instalación

### Requisitos Previos

#### Hardware
- **CPU**: Intel i5/Ryzen 5 o superior
- **RAM**: Mínimo 4GB (8GB recomendado)
- **Espacio en disco**: 500MB para aplicación + 100-500MB por DICOM

#### Software
- **Python**: 3.8, 3.9, 3.10, 3.11, 3.12
- **pip**: 20.0 o superior
- **Git**: (opcional, para clonar repositorio)

#### Sistema Operativo
- ✅ Windows 7 SP1, 8.1, 10, 11
- ✅ macOS 10.14+
- ✅ Linux (Ubuntu 18.04+, Debian 10+)

#### Navegadores Soportados
- ✅ Chrome/Chromium 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+

### Pasos de Instalación

#### 1. Clonar el repositorio
```bash
git clone https://github.com/Cesar-8A/Servicio-Web-APP-2025.git
cd Servicio-Web-APP-2025
```
## 🚀 Uso Rápido

### Workflow Básico

#### Paso 1: Registrarse/Iniciar Sesión
1. En la página de inicio, click en **"Registrarse"** o **"Iniciar Sesión"**
2. Crear cuenta con usuario y contraseña
3. **Nota**: Las credenciales se almacenan en memoria (se pierden al reiniciar)

#### Paso 2: Cargar Imágenes DICOM
1. Click en **"Cargar DICOM"** en el menú principal
2. Seleccionar carpeta que contenga archivos `.dcm`
3. Esperar a que termine el procesamiento

#### Paso 3: Seleccionar Serie
1. Se mostrará tabla con series disponibles
2. Click en la serie deseada
3. Sistema cargará la serie y abrirá el visor

#### Paso 4: Explorar Imágenes
- **Navegación**: Usa deslizadores para cambiar slices
- **Contraste**: Ajusta Window/Level con controles o presets
- **Herramientas**: 
  - 🎯 **HU Picker**: Mide valores en puntos específicos
  - 🔍 **Inspector**: Sincroniza vistas haciendo clic
  - 📊 **Histograma**: Edita contraste con curvas
  - 🟥 **RT Overlay**: Carga segmentaciones NRRD

#### Paso 5: Anonimizar y Exportar
1. Click en **"Anonimizar"**
2. Editar campos de paciente
3. Click en **"Exportar"**
4. Descargar ZIP con series anonimizadas

### Ejemplos de Código

**Obtener un valor HU en coordenadas específicas:**
```javascript
const huValue = await fetch(`/hu_value?x=256&y=128&z=50`);
const data = await huValue.json();
console.log(`HU en (256,128,50): ${data.hu}`);
```
## 📁 Estructura del Proyecto
```
Servicio-Web-APP-2025/
├── main.py 
│   ├── Rutas (17 endpoints)
│   ├── Procesamiento DICOM
│   ├── Lógica de renderización 3D
│   └── Gestión de sesiones
├── templates/
│   ├── home.html
│   ├── index.html
│   ├── loadDicom.html
│   ├── resultsTableDicom.html
│   ├── render.html
│   ├── anonimize.html
│   ├── login.html
│   └── register.html
├── static/
│   ├── css/
│   │   └── udg_estilos.css
│   ├── js/
│   │   └── viewer.js
│   └── img/
│       ├── udg_logo.png
│       └── leones_negros_logo.png
├── uploads/
├── upload_nrrd/
├── anonimizado/
├── ARCHITECTURE.md
├── requirements.txt
├── README.md
├── .gitignore
└── LICENSE
```

## 🔌 API Endpoints

### 🔐 Autenticación

| Método    | Ruta       | Descripción                          |
|-----------|------------|--------------------------------------|
| GET/POST | `/login`   | Formulario y procesamiento de login  |
| GET/POST | `/register`| Registro de nuevos usuarios          |
| GET      | `/logout`  | Cierre de sesión                     |


### 🔄 Flujo Principal

| Método    | Ruta                         | Descripción                    | Retorna     |
|-----------|------------------------------|--------------------------------|-------------|
| GET       | `/`                          | Página de inicio               | HTML        |
| GET/POST | `/loadDicom`                 | Carga de carpeta DICOM         | HTML (tabla)|
| POST      | `/process_selected_dicom`    | Procesar serie seleccionada   | JSON        |
| GET       | `/render/<tipo>`             | Visor principal                | HTML        |


### 🖼️ Servicios de Imagen

| Método | Ruta                              | Descripción                   | Parámetros |
|-------|-----------------------------------|-------------------------------|------------|
| GET   | `/image/<view>/<layer>`           | Obtener slice 2D en PNG       | `ww`, `wc` |
| GET   | `/hu_value`                       | Valor HU en coordenada        | `x`, `y`, `z` |
| GET   | `/get_histogram`                  | Histograma del volumen        | -          |
| GET   | `/get_dicom_metadata`             | Metadata técnica DICOM        | -          |


### 🧊 Herramientas 3D

| Método | Ruta                  | Descripción                         |
|-------|-----------------------|-------------------------------------|
| POST  | `/update_render_mode` | Cambiar modo de visualización 3D    |
| POST  | `/upload_RT`          | Cargar estructura de segmentación   |


### 🕵️ Anonimización

| Método | Ruta               | Descripción                          |
|-------|--------------------|--------------------------------------|
| GET   | `/anonimize`       | Editor de anonimización              |
| POST  | `/guardar_cambios` | Guardar cambios realizados           |
| POST  | `/exportar_dicom`  | Exportar ZIP DICOM anonimizado       |

---

## ⚙️ Configuración

### 🔐 Variables de Entorno

Crear un archivo `.env` en la raíz del proyecto con el siguiente contenido:

```bash
FLASK_SECRET_KEY=tu_clave_super_secreta_aqui
WTF_CSRF_SECRET_KEY=otra_clave_secreta
FLASK_ENV=development
FLASK_DEBUG=False
MAX_UPLOAD_SIZE=500M
FLASK_PORT=5001
BOKEH_PORT=5010
```
Estas variables controlan la seguridad, el entorno de ejecución y los límites de carga del sistema.

### 🎚️ Configuración de Presets Window / Level

En el archivo main.py, se definen presets para la visualización médica utilizando valores Window Center (WC) y Window Width (WW):
```python
PRESETS = {
    'lungs': {'wc': -600, 'ww': 1500},
    'bone': {'wc': 480, 'ww': 2500},
    'soft_tissue': {'wc': 40, 'ww': 400}
}
```
Estos presets permiten una visualización optimizada según el tipo de tejido.

### 🚀 Configuración para Producción

Para un entorno productivo, se recomienda habilitar las siguientes opciones de seguridad en la configuración de Flask:
```
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB
```
Estas configuraciones mejoran la seguridad de las sesiones y limitan el tamaño máximo de archivos cargados.

---

## 🔒 Seguridad

### Medidas Implementadas ✅

| Medida | Estado | Nivel |
|--------|--------|-------|
| Protección CSRF | ✅ Implementada | ALTO |
| Hash de Contraseñas | ✅ SHA-256 + Salt | ALTO |
| Sesiones Servidor-lado | ✅ Implementadas | ALTO |
| Validación de Archivos | ✅ Extensión NRRD | MEDIO |

### Aspectos de Seguridad a Considerar ⚠️

| Aspecto | Estado | Riesgo | Recomendación |
|--------|--------|--------|---------------|
| Base de datos | ❌ NO | ALTO | Implementar PostgreSQL/SQLite |
| Límites de carga | ⚠️ Parcial | ALTO | Agregar validación |
| HTTPS | ❌ NO | CRÍTICO | Usar en producción |
| Rate limiting | ❌ NO | ALTO | Agregar Flask-Limiter |
| Limpieza de archivos | ❌ NO | MEDIO | Implementar cron job |

### NO es Apto Para:
- ❌ Datos HIPAA/GDPR sin modificaciones
- ❌ Sistemas clínicos en producción
- ❌ Múltiples usuarios simultáneos (>10)
- ❌ Almacenamiento persistente de credenciales

---

## ❓ FAQ & Troubleshooting

### Instalación

**P: Recibo error `ModuleNotFoundError: No module named 'flask'`**

R: El entorno virtual no está activado.
```bash
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

---

## ⚠️ Limitaciones Conocidas

### ⚙️ Funcionales

| Limitación                         | Impacto                              | Workaround / Mitigación              |
|-----------------------------------|--------------------------------------|--------------------------------------|
| No soporta JPEG2000 completo      | Algunos DICOM comprimidos fallan     | Descomprimir previamente             |
| Máx. 500–600 slices por volumen   | Volúmenes grandes presentan lentitud | Usar equipo con mayor RAM            |
| Sin multiusuario simultáneo       | Conflictos de sesión                 | Un usuario a la vez                  |
| Sesiones perdidas al reiniciar    | Datos no persistentes                | Exportar antes de reiniciar          |


### 🚀 De Rendimiento

| Limitación                     | Síntoma                             | Solución / Estado        |
|--------------------------------|-------------------------------------|--------------------------|
| Generación de slices lenta     | Lag al cambiar slice                | Usar volúmenes pequeños |
| Render 3D lento en HW débil    | Pixelado o entrecortado             | Equipo más potente      |
| Sin precarga de slices         | Espera entre cambios                | En desarrollo           |


### 🌐 Compatibilidad de Navegadores

| Navegador   | Estado         | Observaciones                  |
|-------------|----------------|--------------------------------|
| Mobile (iOS / Android) | ❌ No soportado | No optimizado actualmente |
| Internet Explorer 11   | ❌ No soportado | Obsoleto                  |
| Safari                 | ⚠️ Soportado   | Rendimiento inferior      |
| Chromium (Chrome, Edge)| ✅ Recomendado | Mejor rendimiento general |

---

## ⚖️ Licencia

Este proyecto está distribuido bajo la **Licencia MIT**.  
Consulta el archivo [`LICENSE`](LICENSE) para más detalles.

Se permite el uso, modificación y distribución del software de forma libre, siempre que se incluya la licencia original y el aviso de copyright correspondiente.
