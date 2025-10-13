// Se asegura de que el código se ejecute solo después de que toda la página se haya cargado
document.addEventListener('DOMContentLoaded', function() {
    // --- ESTADO GLOBAL Y CONFIGURACIÓN ---
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    // Estado para los visores 2D (zoom, pan, etc.)
    const viewStates = {
        axial: { scale: 1, x: 0, y: 0, isPanning: false, startX: 0, startY: 0 },
        sagital: { scale: 1, x: 0, y: 0, isPanning: false, startX: 0, startY: 0 },
        coronal: { scale: 1, x: 0, y: 0, isPanning: false, startX: 0, startY: 0 },
    };

    // Estado de la aplicación
    const appState = {
        huMode: false,
        windowLevel: { ww: 400, wc: 40 }
    };

    // --- LÓGICA DE PLUGINS DE LA BARRA LATERAL ---
    function setupPluginButton(btnId, containerId, onToggleCallback) {
        const btn = document.getElementById(btnId);
        const container = document.getElementById(containerId);
        if (!btn || !container) return;
        let isActive = false;
        btn.addEventListener('click', () => {
            isActive = !isActive;
            btn.classList.toggle('btn-secondary', !isActive);
            btn.classList.toggle('btn-udg-rojo', isActive);
            container.style.display = isActive ? 'block' : 'none';
            if (onToggleCallback) onToggleCallback(isActive);
        });
    }
    
    function updateHuInfo() {
        const huInfo = document.getElementById("huInfo");
        if (huInfo) huInfo.textContent = appState.huMode ? "Haz click en una imagen para obtener el valor HU." : "";
        if (!appState.huMode) { // Limpiar marcadores si se desactiva
            clearAllHuMarkers();
            document.getElementById("huResult").innerHTML = "";
        }
    }

    // --- LÓGICA DE AJUSTE DE VENTANA (WW/WC) ---
    const wwSlider = document.getElementById('ww_slider');
    const wcSlider = document.getElementById('wc_slider');
    const wwValueSpan = document.getElementById('ww_value');
    const wcValueSpan = document.getElementById('wc_value');

    function applyWindowLevel(ww, wc, updateSliders = true) {
        appState.windowLevel.ww = ww;
        appState.windowLevel.wc = wc;

        if (updateSliders) {
            if (wwSlider) wwSlider.value = ww;
            if (wcSlider) wcSlider.value = wc;
        }
        if (wwValueSpan) wwValueSpan.textContent = ww;
        if (wcValueSpan) wcValueSpan.textContent = wc;
        updateAll2DViews();
    }

    // --- LÓGICA DE ACTUALIZACIÓN DE IMÁGENES Y SLIDERS 2D ---
    function updateImage(view, layer) {
        const image = document.getElementById(`image_${view}`);
        if (!image) return;
        const { ww, wc } = appState.windowLevel;
        image.src = `/image/${view}/${layer}?ww=${ww}&wc=${wc}&t=${new Date().getTime()}`;
    }

    function updateAll2DViews() {
        Object.keys(viewStates).forEach(view => {
            const slider = document.getElementById(`slider_${view}`);
            if (slider) updateImage(view, slider.value);
        });
    }

    function setupSliceSlider(view) {
        const slider = document.getElementById(`slider_${view}`);
        const numberInput = document.getElementById(`number_${view}`);
        if (!slider || !numberInput) return;
        
        const update = (value) => {
            updateImage(view, value);
            if(appState.huMode) {
                 clearHuMarker(view);
                 document.getElementById("huResult").innerHTML = "";
            }
        };

        slider.addEventListener('input', () => { numberInput.value = slider.value; update(slider.value); });
        numberInput.addEventListener('input', () => {
            let val = Number(numberInput.value);
            const max = parseInt(slider.max, 10);
            const min = parseInt(slider.min, 10);
            if (val < min) val = min; if (val > max) val = max;
            slider.value = val; update(val);
        });
    }

    // --- LÓGICA DE ZOOM, PANEO Y SELECTOR HU ---
    function setupZoomAndPan(view) {
        const img = document.getElementById(`image_${view}`);
        if (!img) return;
        const canvas = document.getElementById(`overlay_${view}`);
        const wrapper = img.parentElement;
        const state = viewStates[view];

        function applyTransform() {
            const transform = `translate(${state.x}px, ${state.y}px) scale(${state.scale})`;
            img.style.transform = transform;
            canvas.style.transform = transform;
        }

        wrapper.addEventListener('wheel', e => {
            e.preventDefault();
            const rect = wrapper.getBoundingClientRect();
            const mouseX = e.clientX - rect.left; const mouseY = e.clientY - rect.top;
            const zoomIntensity = 0.1;
            const direction = e.deltaY < 0 ? 1 : -1;
            const newScale = Math.max(1, state.scale + direction * zoomIntensity * state.scale);
            if (newScale === 1) { state.x = 0; state.y = 0; } 
            else {
                state.x = mouseX - (mouseX - state.x) * (newScale / state.scale);
                state.y = mouseY - (mouseY - state.y) * (newScale / state.scale);
            }
            state.scale = newScale;
            applyTransform();
        });

        wrapper.addEventListener('mousedown', e => {
            if (e.button !== 0) return; e.preventDefault();
            state.isPanning = true;
            state.startX = e.clientX - state.x; state.startY = e.clientY - state.y;
        });
        
        wrapper.addEventListener('dblclick', e => {
            e.preventDefault();
            state.scale = 1; state.x = 0; state.y = 0;
            applyTransform();
        });

        // Listeners en window para que el paneo no se corte si el mouse sale del cuadro
        window.addEventListener('mouseup', () => { if (state.isPanning) state.isPanning = false; });
        window.addEventListener('mousemove', e => {
            if (!state.isPanning) return; e.preventDefault();
            state.x = e.clientX - state.startX; state.y = e.clientY - state.startY;
            applyTransform();
        });
        
        // Listener de click para el selector HU, integrado con zoom/pan
        wrapper.addEventListener('click', e => {
            if (!appState.huMode || state.isPanning) return;
            const rect = wrapper.getBoundingClientRect();
            const wrapperX = e.clientX - rect.left; const wrapperY = e.clientY - rect.top;
            const imageX = (wrapperX - state.x) / state.scale; const imageY = (wrapperY - state.y) / state.scale;
            const nW = img.naturalWidth; const nH = img.naturalHeight;
            const dispW = rect.width / state.scale; const dispH = rect.height / state.scale;
            const scaleX = nW / dispW; const scaleY = nH / dispH;
            const xPix = Math.floor(imageX * scaleX); const yPix = Math.floor(imageY * scaleY);
            if (xPix < 0 || yPix < 0 || xPix >= nW || yPix >= nH) return;

            const slider = document.getElementById(`slider_${view}`);
            const idx = parseInt(slider.value, 10);
            fetch(`/hu_value?view=${view}&x=${xPix}&y=${yPix}&index=${idx}`)
            .then(r => r.json())
            .then(data => {
                const huResult = document.getElementById("huResult");
                if (data.error) { huResult.textContent = "Error: " + data.error; return; }
                huResult.innerHTML = `Voxel (X,Y,Z): ${data.voxel.x}, ${data.voxel.y}, ${data.voxel.z}<br>Valor HU: ${data.hu}`;
                clearAllHuMarkers();
                drawHuMarker(view, imageX, imageY);
            }).catch(() => { document.getElementById("huResult").textContent = "Error al obtener valor HU."; });
        });
    }

    // --- LÓGICA DEL MARCADOR HU ---
    const dpr = window.devicePixelRatio || 1;
    function syncCanvasToImage(imgEl, canvasEl) {
        if (!imgEl || !canvasEl) return null;
        const rect = imgEl.getBoundingClientRect();
        canvasEl.width = Math.round(rect.width * dpr); canvasEl.height = Math.round(rect.height * dpr);
        const ctx = canvasEl.getContext("2d");
        ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.scale(dpr, dpr);
        ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
        return ctx;
    }
    function drawHuMarker(view, cssX, cssY) {
        const canvas = document.getElementById(`overlay_${view}`);
        const img = document.getElementById(`image_${view}`);
        if (!canvas || !img) return;
        const ctx = syncCanvasToImage(img, canvas);
        ctx.fillStyle = "rgba(255, 0, 0, 0.8)";
        ctx.beginPath(); ctx.arc(cssX, cssY, 5 / dpr, 0, 2 * Math.PI); ctx.fill();
    }
    function clearHuMarker(view) { syncCanvasToImage(document.getElementById(`image_${view}`), document.getElementById(`overlay_${view}`)); }
    function clearAllHuMarkers(){ Object.keys(viewStates).forEach(clearHuMarker); }

    // --- LÓGICA DE CAMBIO DE RENDERIZADO 3D ---
    function setup3DRendererControls() {
        const renderModeRadios = document.querySelectorAll('input[name="renderMode"]');
        const iframe = document.getElementById('DicomRender');
        if (!iframe || renderModeRadios.length === 0) return;

        renderModeRadios.forEach(radio => {
            radio.addEventListener('change', function() {
                iframe.style.opacity = '0.5'; // Indicar carga
                const token = document.querySelector('meta[name="csrf-token"]').content;
                fetch('/update_render_mode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
                    body: JSON.stringify({ mode: this.value })
                })
                .then(response => response.json())
                .then(data => {
                    if(data.status === 'success') { iframe.src += ''; } // Forzar recarga
                    else { alert('Error al cambiar el modo de renderizado.'); iframe.style.opacity = '1'; }
                })
                .catch(error => { console.error("Error en fetch:", error); iframe.style.opacity = '1'; });
                iframe.onload = () => { iframe.style.opacity = '1'; }; // Quitar indicador de carga
            });
        });
    }

    // --- INICIALIZACIÓN DE TODAS LAS FUNCIONALIDADES ---
    // Plugins
    setupPluginButton('rtStructPluginBtn', 'rtStructPluginContainer');
    setupPluginButton('huPickerPluginBtn', 'huPickerPluginContainer', (isActive) => { appState.huMode = isActive; updateHuInfo(); });
    setupPluginButton('windowLevelBtn', 'windowLevelControls');

    // Controles de ventana
    if (wwSlider) wwSlider.addEventListener('input', () => applyWindowLevel(parseInt(wwSlider.value, 10), appState.windowLevel.wc, false));
    if (wcSlider) wcSlider.addEventListener('input', () => applyWindowLevel(appState.windowLevel.ww, parseInt(wcSlider.value, 10), false));
    document.getElementById('presetBtnLung')?.addEventListener('click', () => applyWindowLevel(1500, -600));
    document.getElementById('presetBtnBone')?.addEventListener('click', () => applyWindowLevel(2500, 480));
    document.getElementById('presetBtnSoftTissue')?.addEventListener('click', () => applyWindowLevel(400, 40));

    // Visores 2D y 3D
    Object.keys(viewStates).forEach(view => {
        setupSliceSlider(view);
        setupZoomAndPan(view);
    });
    setup3DRendererControls();

    // Formulario de RT Struct
    const rtStructForm = document.getElementById('rtStructForm');
    if (rtStructForm) {
        rtStructForm.addEventListener("submit", function (event) {
            event.preventDefault();
            let formData = new FormData(this);
            const token = document.querySelector('meta[name="csrf-token"]').content;
            fetch("/upload_RT", { method: "POST", headers: { 'X-CSRFToken': token }, body: formData })
            .then(() => { 
                alert("Archivo cargado correctamente. La página se recargará para mostrar los cambios.");
                window.location.reload();
            });
        });
    }
});

// --- FUNCIONES GLOBALES (para onclick de HTML) ---
function toggleFullscreen(id) {
    const element = document.getElementById(id);
    if (!element) return;
    if (!document.fullscreenElement) {
        element.requestFullscreen().catch(err => {
            alert(`Error al intentar entrar en pantalla completa: ${err.message}`);
        });
    } else {
        document.exitFullscreen();
    }
}