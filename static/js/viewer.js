document.addEventListener('DOMContentLoaded', function() {
    // --- ESTADO GLOBAL Y CONFIGURACIÓN ---
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    // Agregamos { trigger: 'hover' } para que el clic no deje pegado el tooltip
    [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl, {
        trigger: 'hover' 
    }));

    // --- FUNCIÓN DEBOUNCE (Para escritura manual) ---
    function debounce(func, delay = 250) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                func.apply(this, args);
            }, delay);
        };
    }

    // --- LÓGICA PARA BOTONES PERSONALIZADOS ---
    // ================================
        (() => {

        const aiBtn = document.getElementById("aiPluginBtn");
        const aiContainer = document.getElementById("aiPluginContainer");
        const runBtn = document.getElementById("runAIPocBtn");
        const resultBox = document.getElementById("aiResult");

        // Si el HTML no existe, salir sin romper nada
        if (!aiBtn || !aiContainer) return;

        aiBtn.addEventListener("click", () => {

            // Guardamos estado ANTES de ocultar todo
            const wasVisible = aiContainer.style.display === "block";

            // Oculta todos los paneles
            if (typeof hideAllToolPanels === "function") {
            hideAllToolPanels();
            }

            // Toggle
            if (!wasVisible) {
            aiContainer.style.display = "block";
            }
            // Si estaba visible, queda oculto (toggle OFF)
        });

        runBtn?.addEventListener("click", async () => {

            if (!resultBox) return;

            resultBox.style.display = "block";
            resultBox.textContent = "Procesando (POC)...";

            try {
            const response = await fetch("/ai/poc", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({})
            });

            if (!response.ok) {
                throw new Error("Ruta IA no disponible");
            }

            const data = await response.json();
            resultBox.textContent = JSON.stringify(data, null, 2);

            } catch (err) {
            resultBox.textContent =
                "POC activa.\nBackend aún no conectado.\nSin errores críticos.";
            }
        });

        })();


    function setupCustomSpinner(inputId, step, updateCallback) {
        const input = document.getElementById(inputId);
        const minusBtn = document.getElementById(`${inputId}-minus`);
        const plusBtn = document.getElementById(`${inputId}-plus`);

        if (!input || !minusBtn || !plusBtn) return;

        minusBtn.addEventListener('click', () => {
            const currentValue = parseFloat(input.value);
            if (isNaN(currentValue)) return;
            input.value = (currentValue - step).toFixed(input.step.includes('.') ? 1 : 0); // Respetar decimales
            // Llama a la función de actualización INMEDIATAMENTE
            updateCallback();
        });

        plusBtn.addEventListener('click', () => {
            const currentValue = parseFloat(input.value);
            if (isNaN(currentValue)) return;
            input.value = (currentValue + step).toFixed(input.step.includes('.') ? 1 : 0);
            // Llama a la función de actualización INMEDIATAMENTE
            updateCallback();
        });
    }

    // --- ESTADO GLOBAL DEL VISOR ---
    const VIEWS = ['axial', 'sagital', 'coronal'];
    const viewState = {
        ww: 400,
        wc: 40,
        baseImages: { axial: null, sagital: null, coronal: null },
        inspectorMode: false,
        segmentationMode: false,
        crosshairMode: false,
        rulerMode: false,
        brushSize: 1,
        paintMode: 'paint',
        segmentationTool: 'brush', // 'brush' or 'polygon'
        scales: (typeof DICOM_SPACING !== 'undefined' && DICOM_SPACING.dx > 0)
            ? { axial:    DICOM_SPACING.dy / DICOM_SPACING.dx,
                coronal:  DICOM_SPACING.dz / DICOM_SPACING.dx,
                sagittal: DICOM_SPACING.dz / DICOM_SPACING.dx }
            : { axial: 1.0, coronal: 1.0, sagittal: 1.0 },
        colormap: 'gray',
        lastVoxel: { x: null, y: null, z: null },
        activeSegmentationId: null,
        segmentations: []
    };

    // Posición de la intersección de los tres planos (en índices de vóxel)
    const crosshairState = { x: null, y: null, z: null };

    // Estado CINE
    const CINE = { active: false, view: 'all', fps: 8, loop: true, _id: null };

    // Transformaciones de imagen (flip/invert) — globales, aplicadas a todas las vistas
    const viewTransforms = { flipH: false, flipV: false, invert: false };

    // Estado de la regla (ruler)
    const rulerState = { active: false, ptA: null, ptB: null, view: null, drawing: false };

    // --- POLYGON STATE ---
    const polygonState = {
        vertices: [],           // Array of {x, y} in internal pixel coordinates
        isDrawing: false,       // Currently drawing a polygon?
        currentView: null,      // Which view (axial/sagital/coronal)
        currentLayer: null,     // Which slice index
        lastOperation: null     // Store last polygon for undo: {view, layer, vertices, mode}
    };
    const segUndoState = {};  // {segmentationId: bool}
    const zoomState = {
        axial:   { scale: 1, panX: 0, panY: 0, isDragging: false },
        sagital: { scale: 1, panX: 0, panY: 0, isDragging: false },
        coronal: { scale: 1, panX: 0, panY: 0, isDragging: false }
    };

    // --- ESTADO DEL EDITOR DE CONTRASTE ---
    const contrastState = {
        points: [{ x: -1024, y: 0 }, { x: 3071, y: 255 }],
        activePointIndex: null,
        isDragging: false,
        histogramData: null,
        cutoff: 7.0,
        logScale: false,
        minHU: -1024,
        maxHU: 3071,
    };
    contrastState.lut = new Uint8ClampedArray(256).map((_, i) => i);

    // --- LÓGICA DE PLUGINS (Versión Limpia) ---
    function setupPluginButton(btnId, containerId, onToggleCallback) {
        const btn = document.getElementById(btnId);
        const container = containerId ? document.getElementById(containerId) : null;
        
        if (!btn) return;

        btn.addEventListener('click', () => {
            const isActive = btn.classList.contains('btn-udg-rojo');
            
            if (isActive) {
                // DESACTIVAR
                btn.classList.remove('btn-udg-rojo');
                if (container) container.style.display = 'none';
            } else {
                // ACTIVAR
                btn.classList.add('btn-udg-rojo');
                if (container) container.style.display = 'block';
            }

            if (onToggleCallback) onToggleCallback(!isActive);
        });
    }

    setupPluginButton('rtStructPluginBtn', 'rtStructPluginContainer');

    setupPluginButton('segmentationToolBtn', 'segmentationToolContainer', (isActive) => {
        viewState.segmentationMode = isActive;

        if (isActive) {
            // Change cursor to crosshair
            updateCursorStyle('crosshair');

            // Deactivate Inspector if active
            if (viewState.inspectorMode) {
                const inspectorBtn = document.getElementById('inspectorPluginBtn');
                const inspectorContainer = document.getElementById('inspectorPluginContainer');
                if (inspectorBtn) inspectorBtn.classList.remove('btn-udg-rojo');
                if (inspectorContainer) inspectorContainer.style.display = 'none';
                viewState.inspectorMode = false;
            }
        } else {
            // Clear overlays and restore cursor
            VIEWS.forEach(view => clearOverlay(view));
            updateCursorStyle('grab');
        }
    });

    setupPluginButton('windowLevelBtn', 'windowLevelControls');

    setupPluginButton('contrastEditorBtn', 'contrastEditorContainer', (isActive) => {
        if (isActive && !contrastState.histogramData) {
            fetchHistogram();
        } else {
            drawCurveAndHistogram();
        }
    });

    // Configuración del botón Inspector
    setupPluginButton('inspectorPluginBtn', 'inspectorPluginContainer', (isActive) => {
        viewState.inspectorMode = isActive;

        if (isActive) {
            // Cambiar cursor a pointer en todas las vistas
            updateCursorStyle('pointer');

            // Deactivate segmentation if active
            if (viewState.segmentationMode) {
                const segBtn = document.getElementById('segmentationToolBtn');
                const segContainer = document.getElementById('segmentationToolContainer');
                if (segBtn) segBtn.classList.remove('btn-udg-rojo');
                if (segContainer) segContainer.style.display = 'none';
                viewState.segmentationMode = false;
            }

        } else {
            // Limpiamos los canvas de todas las vistas para borrar las líneas
            VIEWS.forEach(view => clearOverlay(view));

            // Restaurar cursor a grab
            updateCursorStyle('grab');

            // Limpiar el display de resultados
            const huResult = document.getElementById('huResult');
            if (huResult) huResult.innerHTML = '-';
        }
    });

    // --- LÓGICA DE AJUSTE DE VENTANA (WW/WC) ---
    const wwSlider = document.getElementById('ww_slider');
    const wcSlider = document.getElementById('wc_slider');

    function updateWWWC(ww, wc, updateSource = null) {
        viewState.ww = Math.max(1, ww);
        viewState.wc = wc;
        
        // Actualizar la posición visual de las barras (Solo si no las estamos moviendo nosotros)
        if (updateSource !== 'sliders') {
            if(wwSlider) wwSlider.value = viewState.ww;
            if(wcSlider) wcSlider.value = viewState.wc;
        }
        
        // Actualizar los inputs numéricos de arriba (Solo si no estamos escribiendo en ellos)
        if (updateSource !== 'fields') {
            const levelIn = document.getElementById('levelInput');
            const windowIn = document.getElementById('windowInput');
            if(levelIn) levelIn.value = Math.round(viewState.wc);
            if(windowIn) windowIn.value = Math.round(viewState.ww);
        }

        //--- Actualizar SIEMPRE los textos pequeños al lado del título ---
        // Esto debe ocurrir sin importar de dónde venga el cambio
        const wwDisp = document.getElementById('ww_val_display');
        const wcDisp = document.getElementById('wc_val_display');
        if (wwDisp) wwDisp.textContent = viewState.ww;
        if (wcDisp) wcDisp.textContent = viewState.wc;
        // -----------------------------------------------------------------------------

        VIEWS.forEach(view => updateImage(view, document.getElementById(`slider_${view}`)?.value, true));
    }
    
    // --- EXPOSICIÓN GLOBAL DE PRESETS ---
    // Esto permite que los botones del HTML con 'onclick' funcionen correctamente
    window.setWindowPreset = function(preset) {
        let ww, wc;
        switch(preset) {
            case 'LUNG':          ww = 1500; wc = -600; break;
            case 'BONE':          ww = 2500; wc =  480; break;
            case 'TISSUE':        ww =  400; wc =   40; break;
            case 'BRAIN':         ww =   80; wc =   40; break;
            case 'ABDOMEN':       ww =  400; wc =   50; break;
            case 'HIGH_CONTRAST': ww =  200; wc =   60; break;
            case 'MR_AUTO':       ww = 1000; wc =  500; break;
            case 'MR_CONTRAST':   ww =  600; wc =  300; break;
            case 'MR_T1':         ww =  600; wc =  300; break;
            case 'MR_T2':         ww =  800; wc =  400; break;
            default: return;
        }
        updateWWWC(ww, wc);
        highlightPreset(preset);
    };
    
    // El debounce se mantiene para la escritura manual en los campos.
    const debouncedUpdateFromFields = debounce((ww, wc) => {
        updateWWWC(ww, wc, 'fields');
    });

    wwSlider?.addEventListener('input', () => updateWWWC(parseInt(wwSlider.value), parseInt(wcSlider.value), 'sliders'));
    wcSlider?.addEventListener('input', () => updateWWWC(parseInt(wwSlider.value), parseInt(wcSlider.value), 'sliders'));
    
    levelInput?.addEventListener('input', () => debouncedUpdateFromFields(parseInt(windowInput.value), parseInt(levelInput.value)));
    windowInput?.addEventListener('input', () => debouncedUpdateFromFields(parseInt(windowInput.value), parseInt(levelInput.value)));
    minInput?.addEventListener('input', () => {
        const min = parseInt(minInput.value);
        const max = parseInt(maxInput.value);
        debouncedUpdateFromFields(max - min, (max + min) / 2);
    });
    maxInput?.addEventListener('input', () => {
        const min = parseInt(minInput.value);
        const max = parseInt(maxInput.value);
        debouncedUpdateFromFields(max - min, (max + min) / 2);
    });
    
    // --- LÓGICA DE PRESETS CON FEEDBACK VISUAL ---
    
    function highlightPreset(presetName) {
        document.querySelectorAll('[data-preset]').forEach(btn => {
            btn.classList.remove('preset-active');
            // Solo restaurar btn-outline-secondary en botones Bootstrap normales
            if (!btn.classList.contains('preset-card') && !btn.classList.contains('preset-pill')) {
                btn.classList.add('btn-outline-secondary');
            }
        });
        if (presetName) {
            document.querySelectorAll(`[data-preset="${presetName}"]`).forEach(btn => {
                if (!btn.classList.contains('preset-card') && !btn.classList.contains('preset-pill')) {
                    btn.classList.remove('btn-outline-secondary');
                }
                btn.classList.add('preset-active');
            });
        }
    }

    // Listeners para Presets — cada botón delega en setWindowPreset para consistencia
    const PRESET_BTN_MAP = {
        presetBtnLung:         'LUNG',
        presetBtnBone:         'BONE',
        presetBtnSoftTissue:   'TISSUE',
        presetBtnBrain:        'BRAIN',
        presetBtnHighContrast: 'HIGH_CONTRAST',
    };
    Object.entries(PRESET_BTN_MAP).forEach(([id, preset]) => {
        document.getElementById(id)?.addEventListener('click', () => window.setWindowPreset(preset));
    });

    wwSlider?.addEventListener('input', () => {
        updateWWWC(parseInt(wwSlider.value), parseInt(wcSlider.value), 'sliders');
        highlightPreset(null);
    });

    wcSlider?.addEventListener('input', () => {
        updateWWWC(parseInt(wwSlider.value), parseInt(wcSlider.value), 'sliders');
        highlightPreset(null);
    });

    // Atajos de teclado: teclas 1-5 activan presets CT (solo si no hay foco en input)
    document.addEventListener('keydown', (e) => {
        if (document.activeElement.matches('input, textarea, select')) return;
        const keyPresets = { '1': 'LUNG', '2': 'BONE', '3': 'TISSUE', '4': 'BRAIN', '5': 'HIGH_CONTRAST' };
        const preset = keyPresets[e.key];
        if (preset) window.setWindowPreset(preset);
    });


    // --- LÓGICA DE SLIDERS DE CORTE ---
    function setupSliceSlider(view) {
        const slider = document.getElementById(`slider_${view}`);
        const number = document.getElementById(`number_${view}`);
        if (!slider || !number) return;

        let isUpdating = false; // Flag to prevent circular updates

        // Slider changes: update number input and image (uses 'input' for smooth dragging)
        slider.addEventListener('change', () => {
            if (isUpdating) return;
            isUpdating = true;
            number.value = slider.value;
            updateImage(view, slider.value, true);

            // Clear polygon if slice changes while drawing
            if (polygonState.isDrawing && polygonState.currentView === view) {
                clearPolygon();
            }

            setTimeout(() => { isUpdating = false; }, 0);
        });

        // Number input changes: use 'change' event instead of 'input'
        // 'change' only fires when user is done (releases mouse/focus), not continuously
        number.addEventListener('change', () => {
            if (isUpdating) return;
            isUpdating = true;
            slider.value = number.value;
            updateImage(view, number.value, true);
            setTimeout(() => { isUpdating = false; }, 0);
        });
    }

    // --- LÓGICA DE IMAGEN Y CANVAS ---
    function updateImage(view, layer, forceReloadFromServer, showLoader = false) {
        const slider = document.getElementById(`slider_${view}`);
        if (!slider) return;
        const currentLayer = layer ?? slider.value;
        if (forceReloadFromServer) {
            if (showLoader) showViewLoader(view);
            const img = new Image();
            img.crossOrigin = "Anonymous";
            img.onload = () => {
                if (showLoader) hideViewLoader(view);
                viewState.baseImages[view] = img;
                applyLutAndDraw(view);
            };
            if (showLoader) img.onerror = () => hideViewLoader(view);
            const cmapParam = viewState.colormap ? `&cmap=${viewState.colormap}` : '';
            img.src = `/image/${view}/${currentLayer}?ww=${viewState.ww}&wc=${viewState.wc}${cmapParam}&t=${new Date().getTime()}`;
        } else {
            applyLutAndDraw(view);
        }
    }

    function applyLutAndDraw(view) {
        const baseImage = viewState.baseImages[view];
        const canvas = document.getElementById(`canvas_${view}`);
        const overlay = document.getElementById(`overlay_${view}`);
        if (!baseImage || !canvas || !baseImage.complete || baseImage.naturalWidth === 0) return;
        const ctx = canvas.getContext('2d', { willReadFrequently: true });

        // 1. Sincronizar dimensiones internas
        canvas.width = baseImage.naturalWidth;
        canvas.height = baseImage.naturalHeight;

        // 2. LÓGICA DE CENTRADO SEGURO
        const zs = zoomState[view];
        const wrapper = canvas.parentElement;
        // Solo centramos automáticamente si es la carga inicial (escala 1 y sin paneo)
        if (zs.scale === 1 && zs.panX === 0 && zs.panY === 0) {
            zs.panX = (wrapper.clientWidth - canvas.width) / 2;
            zs.panY = (wrapper.clientHeight - canvas.height) / 2;
        }

        // 3. Dibujar imagen base (con flip si está activo)
        ctx.save();
        if (viewTransforms.flipH || viewTransforms.flipV) {
            ctx.translate(viewTransforms.flipH ? canvas.width : 0, viewTransforms.flipV ? canvas.height : 0);
            ctx.scale(viewTransforms.flipH ? -1 : 1, viewTransforms.flipV ? -1 : 1);
        }
        ctx.drawImage(baseImage, 0, 0);
        ctx.restore();

        // 4. APLICAR LUT DEL HISTOGRAMA (Respuesta en tiempo real)
        // Solo aplica si no hay un mapa de color activo (para no alterar colores térmicos/médicos)
        if (viewState.colormap === 'gray' || !viewState.colormap) {
            const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            const data = imageData.data;
            const lut = contrastState.lut;

            for (let i = 0; i < data.length; i += 4) {
                // Skip LUT for colored overlays (segmentation cyan, RT struct red)
                const isGrayscale = (data[i] === data[i+1] && data[i+1] === data[i+2]);
                if (isGrayscale) {
                    const val = data[i]; // Rojo (R=G=B en escala de grises)
                    const newVal = lut[val];
                    data[i] = data[i + 1] = data[i + 2] = newVal;
                }
                // If not grayscale (colored overlay), preserve original RGB values
            }
            ctx.putImageData(imageData, 0, 0);
        }

        // 4b. INVERTIR (solo píxeles en escala de grises, preserva overlays de color)
        if (viewTransforms.invert) {
            const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            const d = imgData.data;
            for (let i = 0; i < d.length; i += 4) {
                if (d[i] === d[i+1] && d[i+1] === d[i+2]) {
                    d[i] = d[i+1] = d[i+2] = 255 - d[i];
                }
            }
            ctx.putImageData(imgData, 0, 0);
        }

        // 5. SINCRONIZAR CAPAS (Imagen + Herramientas)
        if (overlay) {
            // Evitamos borrar el overlay si el tamaño ya es correcto
            if (overlay.width !== canvas.width || overlay.height !== canvas.height) {
                overlay.width = canvas.width;
                overlay.height = canvas.height;
            }
            
            const transform = `translate(${zs.panX}px, ${zs.panY}px) scale(${zs.scale})`;
            canvas.style.transform = transform;
            canvas.style.transformOrigin = '0 0';
            overlay.style.transform = transform;
            overlay.style.transformOrigin = '0 0';
        }

        // 6. PERSISTENCIA DEL INSPECTOR
        // Si el usuario marcó un punto, lo redibujamos automáticamente tras la actualización
        if (viewState.lastVoxel && viewState.lastVoxel.x !== null) {
            drawCrosshairFromVoxel(view);
        }

        updateMinimap(view);
        drawReferenceLines();
    }
    
    // --- LÓGICA DEL HISTOGRAMA ---
    const histogramCanvas = document.getElementById('histogramCanvas');
    const cutoffInput = document.getElementById('cutoffInput');
    const logScaleCheckbox = document.getElementById('logScaleCheckbox');
    const histCtx = histogramCanvas.getContext('2d');

    async function fetchHistogram() {
        try {
            const response = await fetch('/get_histogram');
            if (!response.ok) throw new Error('Failed to fetch histogram');
            const data = await response.json();
            contrastState.histogramData = data;
            
            // --- ACTUALIZAR ESTADÍSTICAS EN PANTALLA ---
            if (data.stats) {
                const minEl = document.getElementById('statMinVal');
                const maxEl = document.getElementById('statMaxVal');
                const meanEl = document.getElementById('statMeanVal');
                
                if (minEl) minEl.textContent = data.stats.min + (data.modality === 'CT' ? ' UH' : ' SI');
                if (maxEl) maxEl.textContent = data.stats.max + (data.modality === 'CT' ? ' UH' : ' SI');
                if (meanEl) meanEl.textContent = data.stats.mean + (data.modality === 'CT' ? ' UH' : ' SI');
            }

            drawCurveAndHistogram();
        } catch (error) {
            console.error(error);
        }
    }

    function drawHistogram() {
        if (!contrastState.histogramData) return;
        
        const { width, height } = histogramCanvas;
        histCtx.clearRect(0, 0, width, height);
        
        const data = contrastState.histogramData;
        
        // --- 1. MODO BINARIO (Para máscaras, se queda igual) ---
        if (data.mode === 'binary') {
            const counts = data.counts;
            const labels = data.labels || [];
            const maxCount = Math.max(...counts) || 1;
            const barWidth = width / counts.length;
            
            counts.forEach((count, i) => {
                const barHeight = (count / maxCount) * (height * 0.9);
                const x = i * barWidth;
                const y = height - barHeight;
                
                histCtx.fillStyle = labels[i] === '0' ? '#444444' : '#0dcaf0';
                histCtx.fillRect(x + 5, y, barWidth - 10, barHeight);
                
                histCtx.fillStyle = 'white';
                histCtx.font = '10px monospace';
                if(labels[i]) histCtx.fillText(labels[i], x + (barWidth/2) - 5, height - 5);
            });
            return;
        }

        // --- 2. MODO ITK-SNAP (CORREGIDO: Ignorar Aire para escalar) ---
        const { counts, bin_edges } = data;
        
        // CÁLCULO DE ESCALA INTELIGENTE:
        // Ignoramos los primeros 5 bins (que contienen el aire/fondo -1000 HU)
        // para calcular la altura máxima. Así el tejido no se ve aplastado.
        let maxCount = 1;
        if (counts.length > 20) {
             // Cortamos el inicio (aire) y un poco del final (metal/ruido)
             const tissueCounts = counts.slice(10, counts.length - 5); 
             maxCount = Math.max(...tissueCounts) || 1;
        } else {
             maxCount = Math.max(...counts) || 1;
        }

        const binCount = counts.length;
        const barWidth = width / binCount; 

        for (let i = 0; i < binCount; i++) {
            const count = counts[i];
            if (count === 0) continue;
            
            // Altura (Usamos Logarítmica para suavizar picos)
            let barHeight;
            if (contrastState.logScale) {
                barHeight = (Math.log1p(count) / Math.log1p(maxCount)) * height;
            } else {
                // Limitamos la altura al 100% del canvas para que el aire no se salga
                const rawHeight = (count / maxCount) * height;
                barHeight = Math.min(rawHeight, height); 
            }
            
            const x = i * barWidth;
            const y = height - barHeight;
            
            // --- COLOREADO ESTILO ITK ---
            const huVal = bin_edges[i];
            let color = '#6c757d'; 
            
            if (huVal < -300) color = '#343a40';       // Aire: Gris oscuro
            else if (huVal >= -150 && huVal < -30) color = '#ffc107'; // Grasa: Amarillo
            else if (huVal >= 30 && huVal < 100) color = '#dc3545';   // Tejido: Rojo
            else if (huVal >= 200) color = '#f8f9fa';  // Hueso: Blanco
            
            histCtx.fillStyle = color;
            
            // Dibujamos la barra con un pequeño espacio (-0.5) para definición
            const finalWidth = barWidth > 1 ? barWidth - 0.5 : barWidth;
            
            if (barHeight > 0) {
                 histCtx.fillRect(x, y, finalWidth, barHeight);
            }
        }
    }

    cutoffInput?.addEventListener('change', () => {
        contrastState.cutoff = parseFloat(cutoffInput.value) || 0;
        drawCurveAndHistogram();
    });
    logScaleCheckbox?.addEventListener('change', () => {
        contrastState.logScale = logScaleCheckbox.checked;
        drawCurveAndHistogram();
    });

    // --- LÓGICA DEL EDITOR DE CURVA DE CONTRASTE ---
    const curveCanvas = document.getElementById('curveCanvas');
    const resetContrastBtn = document.getElementById('resetContrastBtn');
    const selectedPointInfo = document.getElementById('selectedPointInfo');
    const addPointBtn = document.getElementById('addPointBtn');
    const removePointBtn = document.getElementById('removePointBtn');
    const prevPointBtn = document.getElementById('prevPointBtn');
    const nextPointBtn = document.getElementById('nextPointBtn');
    const curveCtx = curveCanvas.getContext('2d');

    function drawCurveAndHistogram() {
        requestAnimationFrame(() => {
            if (histogramCanvas.offsetParent !== null) {
                drawHistogram();
                drawCurve();
            }
        });
    }

    function computeAndUpdateLUT() {
        const lut = new Uint8ClampedArray(256);
        const sortedPoints = [...contrastState.points].sort((a, b) => a.x - b.x);
        const interp = (x0, y0, x1, y1, x) => (y0 + (x - x0) * (y1 - y0) / (x1 - x0));
        for (let i = 0; i < lut.length; i++) {
            const huValue = contrastState.minHU + (i / 255) * (contrastState.maxHU - contrastState.minHU);
            let y_hu;
            if (huValue <= sortedPoints[0].x) {
                y_hu = sortedPoints[0].y;
            } else if (huValue >= sortedPoints[sortedPoints.length - 1].x) {
                y_hu = sortedPoints[sortedPoints.length - 1].y;
            } else {
                for (let j = 0; j < sortedPoints.length - 1; j++) {
                    if (huValue >= sortedPoints[j].x && huValue <= sortedPoints[j + 1].x) {
                        y_hu = interp(sortedPoints[j].x, sortedPoints[j].y, sortedPoints[j+1].x, sortedPoints[j+1].y, huValue);
                        break;
                    }
                }
            }
            let norm = Math.max(0, Math.min(1, y_hu / 255));
            lut[i] = Math.round(norm * 255);
        }
        contrastState.lut = lut;
        VIEWS.forEach(view => applyLutAndDraw(view));
    }

    function drawCurve() {
        const { width, height } = curveCanvas;
        curveCtx.clearRect(0, 0, width, height);
        const { minHU, maxHU } = contrastState;
        const pointsToCanvas = (p) => ({
            x: ((p.x - minHU) / (maxHU - minHU)) * width,
            y: height - (p.y / 255) * height,
        });
        const canvasPoints = contrastState.points.map(pointsToCanvas).sort((a,b) => a.x - b.x);
        curveCtx.strokeStyle = '#FFD700';
        curveCtx.lineWidth = 2;
        curveCtx.beginPath();
        curveCtx.moveTo(canvasPoints[0].x, canvasPoints[0].y);
        for (let i = 1; i < canvasPoints.length; i++) {
            curveCtx.lineTo(canvasPoints[i].x, canvasPoints[i].y);
        }
        curveCtx.stroke();
        canvasPoints.forEach((pt, idx) => {
            const originalIndex = contrastState.points.findIndex(p => pointsToCanvas(p).x === pt.x && pointsToCanvas(p).y === pt.y);
            curveCtx.beginPath();
            curveCtx.fillStyle = originalIndex === contrastState.activePointIndex ? '#AE1C28' : '#343a40';
            curveCtx.arc(pt.x, pt.y, 5, 0, Math.PI * 2);
            curveCtx.fill();
        });
    }

    function updateSelectedPointInfo() {
        const pointIdVal = document.getElementById('pointIdVal');
        const pointXVal = document.getElementById('pointXVal');
        const pointYVal = document.getElementById('pointYVal');
        if (!pointIdVal || !pointXVal || !pointYVal) return;
        if (contrastState.activePointIndex !== null && contrastState.points[contrastState.activePointIndex]) {
            const pt = contrastState.points[contrastState.activePointIndex];
            pointIdVal.textContent = contrastState.activePointIndex;
            pointXVal.textContent = pt.x.toFixed(1);
            pointYVal.textContent = (pt.y / 255).toFixed(3);
        } else {
            pointIdVal.textContent = `(ninguno)`;
            pointXVal.textContent = '-';
            pointYVal.textContent = '-';
        }
    }

    function handleCurveInteraction(e) {
        e.preventDefault();
        const rect = curveCanvas.getBoundingClientRect();
        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const clientY = e.touches ? e.touches[0].clientY : e.clientY;
        const canvasX = clientX - rect.left;
        const canvasY = clientY - rect.top;
        const x_hu = contrastState.minHU + (canvasX / rect.width) * (contrastState.maxHU - contrastState.minHU);
        const y_val = 255 - (canvasY / rect.height) * 255;
        if (e.type === 'mousedown' || e.type === 'touchstart') {
            let nearestIdx = -1, minDist = 15;
            contrastState.points.forEach((pt, idx) => {
                const canvasPt = { x: (pt.x - contrastState.minHU) / (contrastState.maxHU - contrastState.minHU) * rect.width, y: rect.height - (pt.y / 255) * rect.height };
                const d = Math.hypot(canvasPt.x - canvasX, canvasPt.y - canvasY);
                if (d < minDist) {
                    minDist = d;
                    nearestIdx = idx;
                }
            });
            if (nearestIdx !== -1) {
                contrastState.activePointIndex = nearestIdx;
                contrastState.isDragging = true;
            } else {
                contrastState.activePointIndex = null;
            }
        } else if ((e.type === 'mousemove' || e.type === 'touchmove') && contrastState.isDragging && contrastState.activePointIndex !== null) {
            const activePoint = contrastState.points[contrastState.activePointIndex];
            if (activePoint) {
                if (contrastState.activePointIndex > 0 && contrastState.activePointIndex < contrastState.points.length - 1) {
                    activePoint.x = x_hu;
                }
                activePoint.y = y_val;
            }
        } else if (e.type === 'mouseup' || e.type === 'touchend') {
            contrastState.isDragging = false;
        } else if (e.type === 'dblclick') {
            contrastState.points.push({ x: x_hu, y: y_val });
        }
        contrastState.points.sort((a,b) => a.x - b.x);
        updateSelectedPointInfo();
        drawCurveAndHistogram();
        computeAndUpdateLUT();
    }
    
    curveCanvas.addEventListener('mousedown', handleCurveInteraction);
    window.addEventListener('mousemove', handleCurveInteraction);
    window.addEventListener('mouseup', handleCurveInteraction);
    curveCanvas.addEventListener('dblclick', handleCurveInteraction);
    curveCanvas.addEventListener('touchstart', handleCurveInteraction, { passive: false });
    window.addEventListener('touchmove', handleCurveInteraction, { passive: false });
    window.addEventListener('touchend', handleCurveInteraction);
    
    resetContrastBtn?.addEventListener('click', () => {
        contrastState.points = [{ x: contrastState.minHU, y: 0 }, { x: contrastState.maxHU, y: 255 }];
        contrastState.activePointIndex = null;
        updateSelectedPointInfo();
        drawCurveAndHistogram();
        computeAndUpdateLUT();
    });

    addPointBtn?.addEventListener('click', () => {
        if (contrastState.points.length < 2) return;
        const lastPt = contrastState.points[contrastState.points.length-1];
        const secondLastPt = contrastState.points[contrastState.points.length-2];
        const newX = (lastPt.x + secondLastPt.x) / 2;
        const newY = (lastPt.y + secondLastPt.y) / 2;
        contrastState.points.push({x: newX, y: newY});
        contrastState.points.sort((a,b) => a.x - b.x);
        drawCurveAndHistogram();
        computeAndUpdateLUT();
    });

    removePointBtn?.addEventListener('click', () => {
        if (contrastState.activePointIndex !== null && contrastState.activePointIndex > 0 && contrastState.activePointIndex < contrastState.points.length - 1) {
            contrastState.points.splice(contrastState.activePointIndex, 1);
            contrastState.activePointIndex = null;
            updateSelectedPointInfo();
            drawCurveAndHistogram();
            computeAndUpdateLUT();
        }
    });

    prevPointBtn?.addEventListener('click', () => {
        if (contrastState.points.length === 0) return;
        let newIndex = (contrastState.activePointIndex === null || contrastState.activePointIndex === 0)
          ? contrastState.points.length - 1
          : contrastState.activePointIndex - 1;
        contrastState.activePointIndex = newIndex;
        updateSelectedPointInfo();
        drawCurveAndHistogram();
    });

    nextPointBtn?.addEventListener('click', () => {
        if (contrastState.points.length === 0) return;
        let newIndex = (contrastState.activePointIndex === null || contrastState.activePointIndex >= contrastState.points.length - 1)
            ? 0
            : contrastState.activePointIndex + 1;
        contrastState.activePointIndex = newIndex;
        updateSelectedPointInfo();
        drawCurveAndHistogram();
    });


    function cssToPngPixels(canvasEl, evt) {
        const wrapper = canvasEl.parentElement;
        const wrapRect = wrapper.getBoundingClientRect();
        const view = canvasEl.id.split('_')[1]; 
        const zs = zoomState[view];

        // 1. Posición del mouse relativa al contenedor negro
        const mouseX = evt.clientX - wrapRect.left;
        const mouseY = evt.clientY - wrapRect.top;

        // 2. FÓRMULA MAESTRA: Píxel = (Mouse - Paneo) / Escala
        const xPix = (mouseX - zs.panX) / zs.scale;
        const yPix = (mouseY - zs.panY) / zs.scale;

        // 3. Validación de límites
        if (xPix < 0 || yPix < 0 || xPix >= canvasEl.width || yPix >= canvasEl.height) {
            return null;
        }

        return {
            xPix: Math.floor(xPix),
            yPix: Math.floor(yPix),
            cssX: xPix, 
            cssY: yPix
        };
    }

    function clearOverlay(view) {
        const overlay = document.getElementById(`overlay_${view}`);
        if (overlay) {
             const ctx = overlay.getContext("2d");
             ctx.clearRect(0, 0, overlay.width, overlay.height);
        }
    }

    function showViewLoader(view) {
        const wrapper = document.getElementById(`card_${view}`)?.querySelector('.image-wrapper');
        if (!wrapper || wrapper.querySelector('.view-loading-overlay')) return;
        const loader = document.createElement('div');
        loader.className = 'view-loading-overlay';
        loader.innerHTML = '<div class="spinner-border spinner-border-sm text-light" role="status"></div>';
        wrapper.appendChild(loader);
    }

    function hideViewLoader(view) {
        const wrapper = document.getElementById(`card_${view}`)?.querySelector('.image-wrapper');
        if (!wrapper) return;
        wrapper.querySelectorAll('.view-loading-overlay').forEach(el => el.remove());
    }

    function updateCursorStyle(cursorType) {
        // Update cursor style for all view wrappers, canvases, and overlays
        VIEWS.forEach(view => {
            const wrapper = document.getElementById(`card_${view}`).querySelector('.image-wrapper');
            const canvas = document.getElementById(`canvas_${view}`);
            const overlay = document.getElementById(`overlay_${view}`);

            if (wrapper) wrapper.style.cursor = cursorType;
            if (canvas) canvas.style.cursor = cursorType;
            if (overlay) overlay.style.cursor = cursorType;
        });
    }

    // --- LÓGICA DEL FORMULARIO RT STRUCT (Robustecida) ---
    const rtStructForm = document.getElementById('rtStructForm');
    if (rtStructForm) {
        rtStructForm.addEventListener("submit", function (event) {
            event.preventDefault();
            
            let formData = new FormData(this);
            const token = document.querySelector('meta[name="csrf-token"]').content;
            const loader = document.getElementById('loader-wrapper');
            const submitBtn = this.querySelector('button[type="submit"]');
            // Feedback visual: mostrar carga y deshabilitar botón
            if (loader) { loader.style.display = 'flex'; loader.style.opacity = '1'; }
            if (submitBtn) { submitBtn.disabled = true; submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Procesando...'; }

            fetch("/upload_RT", {
                method: "POST",
                headers: { 'X-CSRFToken': token },
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    console.log("RT cargado:", data.message);
                    window.refresh3dImage?.();
                    alert("Segmentación cargada correctamente.");
                } else {
                    // ERROR CONTROLADO (Backend dijo que no pudo)
                    throw new Error(data.message || "Error desconocido al procesar.");
                }
            })
            .catch(error => {
                // ERROR DE RED O PROCESAMIENTO
                console.error("Error RT:", error);
                alert("⚠️ No se pudo cargar la segmentación:\n" + error.message + "\n\nLa visualización actual se mantendrá.");
            })
            .finally(() => {
                // RESTAURAR UI (Pase lo que pase)
                if (loader) {
                    loader.style.opacity = '0';
                    setTimeout(() => { loader.style.display = 'none'; }, 500);
                }
                if (submitBtn) { 
                    submitBtn.disabled = false; 
                    submitBtn.innerHTML = '<i class="bi bi-upload"></i> Procesar'; 
                }
                // Limpiar el input file
                rtStructForm.reset();
            });
        });
    }

    // --- VISOR 3D: Three.js (isosurface) + PNG (volume/MIP) ---

    let current3dView   = 'isometric';
    let _threejsState   = null;   // { renderer, scene, camera, controls, animId }

    /** Destruye la escena Three.js anterior si existe. */
    function _destroyThreejs() {
        if (!_threejsState) return;
        const { renderer, controls, animId } = _threejsState;
        cancelAnimationFrame(animId);
        controls.dispose();
        renderer.dispose();
        const c = renderer.domElement;
        if (c.parentNode) c.parentNode.removeChild(c);
        _threejsState = null;
    }

    /** Convierte base64 → ArrayBuffer. */
    function _b64toBuffer(b64) {
        const bin = atob(b64);
        const buf = new ArrayBuffer(bin.length);
        const u8  = new Uint8Array(buf);
        for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
        return buf;
    }

    /** Inicializa Three.js en #threejs-container con los datos de mallas recibidos. */
    function _initThreejs(meshesData) {
        _destroyThreejs();

        const container = document.getElementById('threejs-container');
        if (!container || typeof THREE === 'undefined') return;

        const W = container.clientWidth  || 400;
        const H = container.clientHeight || 500;

        // Renderer
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
        renderer.setPixelRatio(window.devicePixelRatio);
        renderer.setSize(W, H);
        renderer.setClearColor(0x0a0e17, 1);
        container.appendChild(renderer.domElement);

        // Escena y cámara
        const scene  = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 100000);

        // Luces
        scene.add(new THREE.AmbientLight(0xffffff, 0.45));
        const dir1 = new THREE.DirectionalLight(0xffffff, 0.75);
        dir1.position.set(1, 2, 2);
        scene.add(dir1);
        const dir2 = new THREE.DirectionalLight(0x6688cc, 0.3);
        dir2.position.set(-2, -1, -1);
        scene.add(dir2);

        // Mallas
        const box = new THREE.Box3();
        for (const md of meshesData) {
            const geo = new THREE.BufferGeometry();
            geo.setAttribute('position',
                new THREE.BufferAttribute(new Float32Array(_b64toBuffer(md.vertices)), 3));
            geo.setIndex(
                new THREE.BufferAttribute(new Uint32Array(_b64toBuffer(md.faces)), 1));
            geo.computeVertexNormals();
            box.expandByObject(new THREE.Mesh(geo));

            const mat = new THREE.MeshPhongMaterial({
                color:       new THREE.Color(md.color),
                opacity:     md.opacity,
                transparent: md.opacity < 0.99,
                side:        THREE.DoubleSide,
                shininess:   60,
            });
            scene.add(new THREE.Mesh(geo, mat));
        }

        // Centrar cámara en el bounding box de la escena
        const center = new THREE.Vector3();
        const size   = new THREE.Vector3();
        box.getCenter(center);
        box.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z);
        const dist   = maxDim / (2 * Math.tan(THREE.MathUtils.degToRad(22.5)));
        camera.position.set(center.x + dist * 0.6, center.y + dist * 0.4, center.z + dist);
        camera.lookAt(center);
        camera.near = dist * 0.01;
        camera.far  = dist * 10;
        camera.updateProjectionMatrix();

        // OrbitControls
        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.target.copy(center);
        controls.enableDamping = true;
        controls.dampingFactor = 0.08;
        controls.update();

        // Resize observer
        const ro = new ResizeObserver(() => {
            const nW = container.clientWidth;
            const nH = container.clientHeight;
            if (!nW || !nH) return;
            renderer.setSize(nW, nH);
            camera.aspect = nW / nH;
            camera.updateProjectionMatrix();
        });
        ro.observe(container);

        // Loop de animación
        let animId;
        function animate() {
            animId = requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        }
        animate();

        _threejsState = { renderer, scene, camera, controls, animId, ro };
    }

    /** Muestra el visor Three.js, oculta controles PNG. */
    function _showThreejs() {
        document.getElementById('threejs-container')?.style.setProperty('display', 'block');
        document.getElementById('png-container')?.style.setProperty('display', 'none');
        document.getElementById('png-view-btns')?.style.setProperty('display', 'none');
        const hint = document.getElementById('threejs-hint');
        if (hint) hint.style.display = 'inline';
    }

    /** Muestra el visor PNG con botones de vista; destruye Three.js si existía. */
    function _showPng() {
        _destroyThreejs();
        document.getElementById('threejs-container')?.style.setProperty('display', 'none');
        document.getElementById('png-container')?.style.setProperty('display', 'block');
        document.getElementById('png-view-btns')?.style.setProperty('display', 'flex');
        const hint = document.getElementById('threejs-hint');
        if (hint) hint.style.display = 'none';
    }

    /** Recarga el visor 3D activo (Three.js si es isosurface, PNG si es volume/MIP). */
    window.refresh3dImage = function() {
        if (_threejsState) {
            fetch('/render_3d_meshes')
                .then(r => r.json())
                .then(meshData => {
                    if (meshData.mode === 'isosurface' && meshData.meshes?.length) {
                        _initThreejs(meshData.meshes);
                    }
                })
                .catch(e => console.error('refresh3dImage mesh error:', e));
            return;
        }
        const img     = document.getElementById('DicomRender');
        const spinner = document.getElementById('render3dSpinner');
        if (!img) return;
        spinner?.classList.remove('d-none');
        img.style.opacity = '0.4';
        const src = `/render_3d_frame?view=${current3dView}&t=${Date.now()}`;
        const tmp = new Image();
        tmp.onload  = () => { img.src = src; img.style.opacity = '1'; spinner?.classList.add('d-none'); };
        tmp.onerror = () => { img.style.opacity = '1'; spinner?.classList.add('d-none'); };
        tmp.src = src;
    };

    /** Carga o recarga la vista 3D: Three.js para isosurface, PNG para volume/MIP. */
    function load3dContent(mode) {
        const token = document.querySelector('meta[name="csrf-token"]')?.content;
        fetch('/update_render_mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
            body: JSON.stringify({ mode, cmap: viewState.colormap })
        })
        .then(r => r.json())
        .then(data => {
            if (data.status !== 'success') return;
            if (mode === 'isosurface') {
                _tryLoadThreejs();
            } else {
                _showPng();
                window.refresh3dImage();
            }
        })
        .catch(e => console.error('load3dContent error:', e));
    }

    /** Intenta cargar Three.js; si falla o no hay mallas, muestra PNG. */
    function _tryLoadThreejs() {
        if (typeof THREE === 'undefined' || typeof THREE.OrbitControls === 'undefined') {
            console.warn('Three.js no disponible — usando visor PNG');
            _showPng();
            window.refresh3dImage();
            return;
        }
        fetch('/render_3d_meshes')
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                return r.json();
            })
            .then(meshData => {
                console.log('render_3d_meshes:', meshData.mode,
                            'mallas:', meshData.meshes?.length ?? 0);
                if (meshData.mode === 'isosurface' && meshData.meshes?.length) {
                    _showThreejs();
                    _initThreejs(meshData.meshes);
                } else {
                    _showPng();
                    window.refresh3dImage();
                }
            })
            .catch(e => {
                console.error('render_3d_meshes error:', e);
                _showPng();
                window.refresh3dImage();
            });
    }

    function setup3DRendererControls() {
        const renderModeRadios = document.querySelectorAll('input[name="renderMode"]');
        const colormapSelect   = document.getElementById('colormapSelect');

        if (!document.getElementById('threejs-container') &&
            !document.getElementById('DicomRender')) return;

        // Cambio de modo 3D
        renderModeRadios.forEach(radio => {
            radio.addEventListener('change', () => load3dContent(radio.value));
        });

        // Botones de vista PNG
        document.querySelectorAll('.view3d-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.view3d-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                current3dView = btn.dataset.view || 'isometric';
                window.refresh3dImage();
            });
        });

        // Botón refrescar
        document.getElementById('refresh3dBtn')?.addEventListener('click', () => {
            const activeRadio = document.querySelector('input[name="renderMode"]:checked');
            load3dContent(activeRadio?.value || 'isosurface');
        });

        // Colormap: 2D inmediato + 3D actualizado
        colormapSelect?.addEventListener('change', function () {
            viewState.colormap = this.value;
            VIEWS.forEach(view => {
                const slider = document.getElementById(`slider_${view}`);
                if (slider) updateImage(view, slider.value, true);
            });
            load3dContent(
                document.querySelector('input[name="renderMode"]:checked')?.value || 'isosurface'
            );
        });

        // Carga inicial
        const initMode = (typeof CURRENT_RENDER_MODE !== 'undefined')
            ? CURRENT_RENDER_MODE : 'isosurface';
        if (initMode === 'isosurface') {
            _tryLoadThreejs();
        } else {
            _showPng();
        }
        // Para volume/mip el img src="/render_3d_frame" ya está en el HTML → se carga solo
    }

    // --- LÓGICA DE ZOOM Y PANEO ---
    function setupZoomPan(view) {
        const wrapper = document.getElementById(`card_${view}`).querySelector('.image-wrapper');
        const canvas = document.getElementById(`canvas_${view}`);
        const overlay = document.getElementById(`overlay_${view}`);
        
        if (!wrapper || !canvas || !overlay) return;

        const updateTransform = () => {
            const zs = zoomState[view];
            const transform = `translate(${zs.panX}px, ${zs.panY}px) scale(${zs.scale})`;

            // Aplicamos transformación a la imagen Y al dibujo (overlay)
            canvas.style.transform = transform;
            canvas.style.transformOrigin = '0 0';
            overlay.style.transform = transform;
            overlay.style.transformOrigin = '0 0';
            // --- NUEVO: Actualizar el mini-mapa al mover o hacer zoom ---
            updateMinimap(view);
            drawReferenceLines();
        };

        // ZOOM (Rueda del mouse)
        wrapper.addEventListener('wheel', (e) => {
            // Disable zoom when inspector mode or segmentation mode is active
            if (viewState.inspectorMode || viewState.segmentationMode) return;

            e.preventDefault();
            const zs = zoomState[view];
            const zoomIntensity = 0.1;
            const delta = e.deltaY < 0 ? 1 : -1;

            const newScale = Math.min(Math.max(1, zs.scale + (delta * zoomIntensity)), 10);

            // Matemáticas para hacer zoom hacia el puntero del mouse
            const canvasRect = canvas.getBoundingClientRect();
            const mouseX = e.clientX - canvasRect.left;
            const mouseY = e.clientY - canvasRect.top;

            if (newScale === 1) {
                zs.panX = 0;
                zs.panY = 0;
            } else {
                zs.panX = mouseX - (mouseX - zs.panX) * (newScale / zs.scale);
                zs.panY = mouseY - (mouseY - zs.panY) * (newScale / zs.scale);
            }

            zs.scale = newScale;
            updateTransform();
        });

        let isDown = false;
        let startX, startY;
        let initialPanX, initialPanY;

        // W/L drag state (clic derecho)
        let wlDown = false;
        let wlStart = { x: 0, y: 0, ww: 400, wc: 40 };

        // Crosshair drag state
        let crosshairDown = false;

        // Evitar menú contextual sobre la imagen
        wrapper.addEventListener('contextmenu', e => e.preventDefault());

        wrapper.addEventListener('mousedown', (e) => {
            // --- CLIC DERECHO: arranca W/L drag ---
            if (e.button === 2) {
                wlDown = true;
                wlStart = { x: e.clientX, y: e.clientY, ww: viewState.ww, wc: viewState.wc };
                wrapper.style.cursor = 'col-resize';
                e.preventDefault();
                return;
            }

            if (viewState.inspectorMode || viewState.segmentationMode) return;

            // --- MODO CROSSHAIR: clic izquierdo actualiza el crosshair ---
            if (viewState.crosshairMode) {
                crosshairDown = true;
                moveCrosshair(view, e);
                return;
            }

            // --- MODO REGLA: primer clic fija ptA, arrastre dibuja, mouseup fija ptB ---
            if (viewState.rulerMode) {
                const mapped = cssToPngPixels(canvas, e);
                if (mapped) {
                    rulerState.ptA = { x: mapped.xPix, y: mapped.yPix };
                    rulerState.ptB = null;
                    rulerState.view = view;
                    rulerState.drawing = true;
                }
                return;
            }

            // --- MODO NORMAL: pan ---
            isDown = true;
            zoomState[view].isDragging = false;

            startX = e.clientX;
            startY = e.clientY;

            initialPanX = zoomState[view].panX;
            initialPanY = zoomState[view].panY;

            wrapper.style.cursor = 'grabbing';
            canvas.style.cursor = 'grabbing';
            overlay.style.cursor = 'grabbing';
        });

        window.addEventListener('mousemove', (e) => {
            // W/L drag (clic derecho)
            if (wlDown) {
                const dx = e.clientX - wlStart.x;
                const dy = e.clientY - wlStart.y;
                const sens = Math.max(1.5, wlStart.ww / 150);
                const newWW = Math.max(1, Math.round(wlStart.ww + dx * sens));
                const newWC = Math.round(wlStart.wc - dy * (sens * 0.55));
                updateWWWC(newWW, newWC, 'drag');
                return;
            }

            // Crosshair drag
            if (crosshairDown) {
                moveCrosshair(view, e);
                return;
            }

            // Ruler preview
            if (rulerState.drawing && rulerState.view === view && rulerState.ptA) {
                const mapped = cssToPngPixels(canvas, e);
                if (mapped) drawRulerPreview(view, rulerState.ptA, { x: mapped.xPix, y: mapped.yPix });
                return;
            }

            if (!isDown) return;
            e.preventDefault();

            const dx = e.clientX - startX;
            const dy = e.clientY - startY;

            if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
                zoomState[view].isDragging = true;
            }

            zoomState[view].panX = initialPanX + dx;
            zoomState[view].panY = initialPanY + dy;

            updateTransform();
        });

        window.addEventListener('mouseup', (e) => {
            if (wlDown && e.button === 2) {
                wlDown = false;
                const cur = viewState.crosshairMode ? 'crosshair' : 'grab';
                wrapper.style.cursor = cur;
                return;
            }
            if (crosshairDown) {
                crosshairDown = false;
                return;
            }
            // Finalizar regla
            if (rulerState.drawing && rulerState.view === view) {
                const mapped = cssToPngPixels(canvas, e);
                if (mapped && rulerState.ptA) {
                    rulerState.ptB = { x: mapped.xPix, y: mapped.yPix };
                    rulerState.drawing = false;
                    drawRulerFinal(view, rulerState.ptA, rulerState.ptB);
                }
                return;
            }
            isDown = false;
            if (!viewState.inspectorMode && !viewState.segmentationMode) {
                const cur = viewState.crosshairMode ? 'crosshair' :
                            viewState.rulerMode ? 'crosshair' : 'grab';
                wrapper.style.cursor = cur;
                canvas.style.cursor = cur;
                overlay.style.cursor = cur;
            }

            setTimeout(() => {
                zoomState[view].isDragging = false;
            }, 50);
        });

        // Reset con doble clic
        wrapper.addEventListener('dblclick', () => {
            zoomState[view] = { scale: 1, panX: 0, panY: 0, isDragging: false };
            updateTransform();
        });


        // Dentro de setupZoomPan(view)...
        const minimapContainer = document.getElementById(`minimap_container_${view}`);
        minimapContainer.addEventListener('mousedown', (e) => {
            e.stopPropagation();
            
            const miniCanvas = document.getElementById(`minimap_canvas_${view}`);
            const mainCanvas = document.getElementById(`canvas_${view}`);
            const rect = miniCanvas.getBoundingClientRect();
            const zs = zoomState[view];
            const wrapper = mainCanvas.parentElement;
            
            // 1. Obtener porcentaje del clic dentro del Mini-mapa (0 a 1)
            const pctX = (e.clientX - rect.left) / rect.width;
            const pctY = (e.clientY - rect.top) / rect.height;
            
            // 2. Centrar la vista: movemos el paneo para que el punto clicado esté en el centro del cuadrante
            // pan = (Centro del Visor) - (Punto en Imagen * Zoom)
            zs.panX = (wrapper.clientWidth / 2) - (pctX * mainCanvas.width * zs.scale);
            zs.panY = (wrapper.clientHeight / 2) - (pctY * mainCanvas.height * zs.scale);

            updateTransform();
        });

        // Función para sincronizar la "cámara" en las 3 vistas
        function syncTransforms(sourceView) {
            const sourceState = zoomState[sourceView];
            VIEWS.forEach(targetView => {
                if (targetView !== sourceView && targetView !== '3D') {
                    const targetState = zoomState[targetView];
                    targetState.scale = sourceState.scale;
                    targetState.panX = sourceState.panX;
                    targetState.panY = sourceState.panY;
                    
                    // Forzar actualización visual del canvas y su minimapa
                    const canvas = document.getElementById(`canvas_${targetView}`);
                    const overlay = document.getElementById(`overlay_${targetView}`);
                    const transform = `translate(${targetState.panX}px, ${targetState.panY}px) scale(${targetState.scale})`;
                    
                    if (canvas) canvas.style.transform = transform;
                    if (overlay) overlay.style.transform = transform;

                    updateMinimap(targetView);
                }
            });
            drawReferenceLines();
        }
    }

    // --- LÓGICA DEL INSPECTOR 3D (CROSSHAIR) ---
    function drawCrosshair(view, x, y) {
        const overlay = document.getElementById(`overlay_${view}`);
        const mainCanvas = document.getElementById(`canvas_${view}`);
        if (!overlay || !mainCanvas) return;

        // Limpiar y preparar
        overlay.width = mainCanvas.width;
        overlay.height = mainCanvas.height;
        const ctx = overlay.getContext("2d");
        ctx.clearRect(0, 0, overlay.width, overlay.height);

        // x, y are already in internal pixel coordinates (from cssToPngPixels)
        // The overlay canvas has the same transform as the main canvas,
        // so we just draw at the pixel coordinates directly.
        // The browser will apply the zoom/pan transform automatically.
        const zs = zoomState[view];

        // Dibujar Cruz (Azul cian muy visible)
        ctx.strokeStyle = "#00FFFF";
        ctx.lineWidth = 1 / zs.scale; // Scale line width so it appears constant size on screen
        ctx.setLineDash([5 / zs.scale, 3 / zs.scale]); // Scale dash pattern too

        // Línea Vertical - draw at pixel coordinate x
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, overlay.height);
        ctx.stroke();

        // Línea Horizontal - draw at pixel coordinate y
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(overlay.width, y);
        ctx.stroke();
    }

    function syncViews(sourceView, x, y) {
        // DEPRECATED: Use syncViewsFromVoxel() instead
        // This function uses pixel coordinates which don't account for aspect ratio
        // Keeping for backward compatibility

        let updates = {};

        if (sourceView === 'axial') {
            updates['sagital'] = x;
            updates['coronal'] = y;
        } else if (sourceView === 'coronal') {
            updates['sagital'] = x;
            updates['axial'] = y;
        } else if (sourceView === 'sagital') {
            updates['coronal'] = x;
            updates['axial'] = y;
        }

        // Aplicar actualizaciones a los sliders
        Object.keys(updates).forEach(targetView => {
            const slider = document.getElementById(`slider_${targetView}`);
            const number = document.getElementById(`number_${targetView}`);
            if (slider) {
                let val = Math.max(0, Math.min(updates[targetView], slider.max));

                if (Math.abs(slider.value - val) > 0) {
                    slider.value = val;
                    number.value = val;
                    updateImage(targetView, val, true);
                }
            }
        });
    }

    function syncViewsFromVoxel(sourceView, voxel) {
        // NEW: Uses voxel coordinates from backend (accounts for aspect ratio scaling)
        // voxel = {x, y, z} in volume space

        let updates = {};

        // The backend returns voxel coordinates in (z, y, x) order
        // We need to map these to the correct slider positions for each view

        if (sourceView === 'axial') {
            // Axial view: we clicked on slice Z, pixel position (X, Y)
            // Update sagittal to X position, coronal to Y position
            updates['sagital'] = voxel.x;
            updates['coronal'] = voxel.y;
        } else if (sourceView === 'coronal') {
            // Coronal view: we clicked on slice Y, pixel position (X, Z)
            // Update sagittal to X position, axial to Z position
            updates['sagital'] = voxel.x;
            updates['axial'] = voxel.z;
        } else if (sourceView === 'sagital') {
            // Sagittal view: we clicked on slice X, pixel position (Y, Z)
            // Update coronal to Y position, axial to Z position
            updates['coronal'] = voxel.y;
            updates['axial'] = voxel.z;
        }

        // Aplicar actualizaciones a los sliders
        Object.keys(updates).forEach(targetView => {
            const slider = document.getElementById(`slider_${targetView}`);
            const number = document.getElementById(`number_${targetView}`);
            if (slider) {
                let val = Math.max(0, Math.min(updates[targetView], slider.max));

                if (Math.abs(slider.value - val) > 0) {
                    slider.value = val;
                    number.value = val;
                    updateImage(targetView, val, true);
                }
            }
        });

        // Draw crosshairs on ALL views to show the 3D intersection point
        drawCrosshairsOnAllViews(voxel);
    }

    function drawCrosshairsOnAllViews(voxel) {
        // Draw crosshair on each view at the corresponding 2D position
        // voxel = {x, y, z} in volume space
        // Need to convert voxel coords to pixel coords using aspect ratio scaling

        // Axial view: crosshair at (X, Y) pixel position
        // Axial Y needs to be scaled by scale_axial
        const axialPixelX = voxel.x;
        const axialPixelY = Math.round(voxel.y * viewState.scales.axial);
        drawCrosshair('axial', axialPixelX, axialPixelY);

        // Coronal view: crosshair at (X, Z) pixel position
        // Coronal Z needs to be scaled by scale_coronal
        const coronalPixelX = voxel.x;
        const coronalPixelZ = Math.round(voxel.z * viewState.scales.coronal);
        drawCrosshair('coronal', coronalPixelX, coronalPixelZ);

        // Sagittal view: crosshair at (Y, Z) pixel position
        // Sagittal Z needs to be scaled by scale_sagittal
        const sagittalPixelY = voxel.y;
        const sagittalPixelZ = Math.round(voxel.z * viewState.scales.sagittal);
        drawCrosshair('sagital', sagittalPixelY, sagittalPixelZ);
    }

    function bindInspector(view) {
        const wrapper = document.getElementById(`card_${view}`).querySelector('.image-wrapper');
        const mainCanvas = document.getElementById(`canvas_${view}`);

        if (!wrapper) return;

        // Helper function to get voxel coordinates from backend and update HU display
        function getVoxelCoordinates(view, mapped, callback) {
            const slider = document.getElementById(`slider_${view}`);
            const idx = parseInt(slider.value, 10);
            const huResult = document.getElementById('huResult');

            fetch(`/hu_value?view=${view}&x=${mapped.xPix}&y=${mapped.yPix}&index=${idx}`)
                .then(r => r.json())
                .then(data => {
                    if (!data.error && data.voxel) {
                        // Store the scaling factors for crosshair drawing
                        if (data.scales) {
                            viewState.scales = data.scales;
                        }

                        // Update HU display panel with formatted output
                        if (huResult) {
                            huResult.innerHTML = `
                                <div class="mb-1 lh-1">
                                    <span style="color: #bbbbbb; font-size: 0.7rem; letter-spacing: 1px; text-transform: uppercase;">Coordenadas:</span>
                                </div>

                                <div class="d-flex justify-content-between mb-2 font-monospace px-1" style="font-size: 0.9rem;">
                                    <span><span style="color: #777;">x:</span> <span style="color: #fff;">${data.voxel.x}</span></span>
                                    <span><span style="color: #777;">y:</span> <span style="color: #fff;">${data.voxel.y}</span></span>
                                    <span><span style="color: #777;">z:</span> <span style="color: #fff;">${data.voxel.z}</span></span>
                                </div>

                                <div class="d-flex justify-content-between align-items-center pt-2" style="border-top: 1px solid #444;">
                                    <span style="color: #bbbbbb; font-size: 0.7rem; letter-spacing: 1px; text-transform: uppercase;">${DICOM_MODALITY === 'MR' ? 'Intensidad' : 'Densidad'}:</span>
                                    <span style="color: #0dcaf0; font-weight: bold; font-size: 1rem;">${data.hu} ${DICOM_MODALITY === 'MR' ? 'SI' : 'UH'}</span>
                                </div>
                            `;
                        }

                        callback(data.voxel);
                    } else if (data.error && huResult) {
                        huResult.textContent = "Error: " + data.error;
                    }
                })
                .catch(err => {
                    console.error("Inspector coordinate fetch error:", err);
                    if (huResult) huResult.textContent = "Error al obtener valor UH.";
                });
        }

        // Evento de Arrastre (Drag) para navegación fluida
        wrapper.addEventListener('mousemove', (e) => {
            // Solo si está activo el modo y se está presionando el clic (buttons === 1)
            if (!viewState.inspectorMode || e.buttons !== 1) return;

            const mapped = cssToPngPixels(mainCanvas, e);
            if (!mapped) return;

            // 1. Dibujar cruz en la vista actual
            drawCrosshair(view, mapped.cssX, mapped.cssY);

            // 2. Get correct voxel coordinates from backend, then sync
            getVoxelCoordinates(view, mapped, (voxel) => {
                syncViewsFromVoxel(view, voxel);
            });
        });

        // Evento Click simple (para posicionar sin arrastrar)
        wrapper.addEventListener('mousedown', (e) => {
            if (!viewState.inspectorMode) return;
            const mapped = cssToPngPixels(mainCanvas, e);
            if (!mapped) return;

            drawCrosshair(view, mapped.cssX, mapped.cssY);

            getVoxelCoordinates(view, mapped, (voxel) => {
                syncViewsFromVoxel(view, voxel);
            });
        });

        // Limpiar al soltar
        wrapper.addEventListener('mouseup', () => {
             if (viewState.inspectorMode) {
                 // Opcional: Si quieres que la cruz desaparezca al soltar, descomenta esto:
                 // clearOverlay(view);
             }
        });
    }

    // --- MULTI-SEGMENTATION MANAGEMENT FUNCTIONS ---

    function loadSegmentations() {
        fetch('/get_segmentations')
            .then(r => r.json())
            .then(data => {
                viewState.segmentations = data.segmentations;
                viewState.activeSegmentationId = data.active_id;
                // Rebuild segUndoState
                data.segmentations.forEach(entry => {
                    segUndoState[entry.id] = entry.has_undo;
                });
                renderSegmentationsList();
                // Update undo button
                const undoBtn = document.getElementById('undoLastPolygonBtn');
                if (undoBtn) {
                    if (viewState.activeSegmentationId !== null && segUndoState[viewState.activeSegmentationId]) {
                        undoBtn.disabled = false;
                        undoBtn.classList.remove('btn-outline-secondary');
                        undoBtn.classList.add('btn-outline-warning');
                    } else {
                        undoBtn.disabled = true;
                        undoBtn.classList.remove('btn-outline-warning');
                        undoBtn.classList.add('btn-outline-secondary');
                    }
                }
            })
            .catch(err => console.error('loadSegmentations error:', err));
    }

    function renderSegmentationsList() {
        const countDisplay = document.getElementById('segCountDisplay');
        if (countDisplay) countDisplay.textContent = `${viewState.segmentations.length}/5`;

        const newSegBtn = document.getElementById('newSegmentationBtn');
        if (newSegBtn) {
            newSegBtn.disabled = viewState.segmentations.length >= 5;
        }

        const container = document.getElementById('segmentationsListContainer');
        if (!container) return;

        if (viewState.segmentations.length === 0) {
            container.innerHTML = '<p class="text-muted small text-center mb-1">No hay segmentaciones. Crea una nueva.</p>';
            return;
        }

        container.innerHTML = '';
        viewState.segmentations.forEach(entry => {
            const row = document.createElement('div');
            row.className = 'seg-row' + (entry.id === viewState.activeSegmentationId ? ' seg-row-active' : '');
            row.dataset.segId = entry.id;

            const swatch = document.createElement('span');
            swatch.className = 'seg-color-swatch';
            swatch.style.backgroundColor = entry.color;

            const nameSpan = document.createElement('span');
            nameSpan.className = 'seg-row-name';
            nameSpan.textContent = entry.name;

            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'seg-row-actions';

            const visBtn = document.createElement('button');
            visBtn.className = 'btn btn-sm seg-visibility-btn';
            visBtn.dataset.segId = entry.id;
            visBtn.title = entry.visible ? 'Ocultar' : 'Mostrar';
            visBtn.innerHTML = `<i class="bi ${entry.visible ? 'bi-eye' : 'bi-eye-slash'}"></i>`;

            const delBtn = document.createElement('button');
            delBtn.className = 'btn btn-sm btn-outline-danger seg-delete-btn';
            delBtn.dataset.segId = entry.id;
            delBtn.title = 'Eliminar';
            delBtn.innerHTML = '<i class="bi bi-trash"></i>';

            actionsDiv.appendChild(visBtn);
            actionsDiv.appendChild(delBtn);

            row.appendChild(swatch);
            row.appendChild(nameSpan);
            row.appendChild(actionsDiv);

            row.addEventListener('click', () => setActiveSegmentation(parseInt(entry.id)));
            visBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleSegmentationVisibility(parseInt(entry.id));
            });
            delBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteSegmentation(parseInt(entry.id));
            });

            container.appendChild(row);
        });
    }

    function showCreateSegmentationForm() {
        const btn = document.getElementById('newSegmentationBtn');
        const form = document.getElementById('createSegmentationForm');
        const input = document.getElementById('newSegNameInput');
        if (btn) btn.style.display = 'none';
        if (form) form.style.display = 'block';
        if (input) { input.value = ''; input.focus(); }
    }

    function hideCreateSegmentationForm() {
        const btn = document.getElementById('newSegmentationBtn');
        const form = document.getElementById('createSegmentationForm');
        const input = document.getElementById('newSegNameInput');
        if (btn) btn.style.display = '';
        if (form) form.style.display = 'none';
        if (input) { input.value = ''; input.classList.remove('is-invalid'); }
    }

    function submitCreateSegmentation() {
        const input = document.getElementById('newSegNameInput');
        if (!input) return;
        const trimmedValue = input.value.trim();
        if (!trimmedValue) {
            input.classList.add('is-invalid');
            return;
        }
        input.classList.remove('is-invalid');
        const saveBtn = document.getElementById('saveNewSegBtn');
        if (saveBtn) saveBtn.disabled = true;
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        fetch('/create_segmentation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ name: trimmedValue })
        })
        .then(response => {
            if (!response.ok) return response.json().then(d => { throw new Error(d.message || 'Error al crear'); });
            return response.json();
        })
        .then(() => {
            loadSegmentations();
            hideCreateSegmentationForm();
        })
        .catch(err => { alert('Error: ' + err.message); })
        .finally(() => { if (saveBtn) saveBtn.disabled = false; });
    }

    function deleteSegmentation(id) {
        if (!confirm('¿Eliminar esta segmentación? Esta acción no se puede deshacer.')) return;
        if (polygonState.isDrawing) clearPolygon();
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        fetch('/delete_segmentation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ id: id })
        })
        .then(response => {
            if (!response.ok) return response.json().then(d => { throw new Error(d.message || 'Error al eliminar'); });
            return response.json();
        })
        .then(() => {
            loadSegmentations();
            VIEWS.forEach(view => {
                const slider = document.getElementById('slider_' + view);
                if (slider) updateImage(view, parseInt(slider.value), true, true);
            });
        })
        .catch(err => { alert('Error: ' + err.message); });
    }

    function setActiveSegmentation(id) {
        if (polygonState.isDrawing) clearPolygon();
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        fetch('/set_active_segmentation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ id: id })
        })
        .then(response => {
            if (!response.ok) return response.json().then(d => { throw new Error(d.message || 'Error'); });
            return response.json();
        })
        .then(data => {
            viewState.activeSegmentationId = data.id;
            segUndoState[data.id] = data.has_undo;
            renderSegmentationsList();
            const undoBtn = document.getElementById('undoLastPolygonBtn');
            if (undoBtn) {
                if (data.has_undo) {
                    undoBtn.disabled = false;
                    undoBtn.classList.remove('btn-outline-secondary');
                    undoBtn.classList.add('btn-outline-warning');
                } else {
                    undoBtn.disabled = true;
                    undoBtn.classList.remove('btn-outline-warning');
                    undoBtn.classList.add('btn-outline-secondary');
                }
            }
        })
        .catch(err => { alert('Error: ' + err.message); });
    }

    function toggleSegmentationVisibility(id) {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        fetch('/toggle_segmentation_visibility', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ id: id })
        })
        .then(response => {
            if (!response.ok) return response.json().then(d => { throw new Error(d.message || 'Error'); });
            return response.json();
        })
        .then(data => {
            const entry = viewState.segmentations.find(e => e.id === id);
            if (entry) entry.visible = data.visible;
            renderSegmentationsList();
            VIEWS.forEach(view => {
                const slider = document.getElementById('slider_' + view);
                if (slider) updateImage(view, parseInt(slider.value), true, true);
            });
        })
        .catch(err => { alert('Error: ' + err.message); });
    }

    // --- SEGMENTATION CLICK HANDLER ---
    function handleSegmentationClick(view, evt) {
        if (!viewState.segmentationMode) return;
        if (viewState.activeSegmentationId === null) {
            alert('Crea o selecciona una segmentación primero.');
            return;
        }

        const canvas = document.getElementById('canvas_' + view);
        if (!canvas) return;

        // Convert screen coordinates to pixel coordinates
        const coords = cssToPngPixels(canvas, evt);

        // Get current layer
        const slider = document.getElementById('slider_' + view);
        const layer = parseInt(slider.value);

        // Handle based on tool mode
        if (viewState.segmentationTool === 'brush') {
            // BRUSH MODE: Paint voxel immediately
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

            const payload = {
                view: view,
                xPix: coords.xPix,
                yPix: coords.yPix,
                layer: layer,
                brush_size: viewState.brushSize,
                mode: viewState.paintMode
            };

            fetch('/paint_voxel', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(payload)
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    updateImage(view, layer, true, true);
                }
            })
            .catch(error => {
                console.error('Paint error:', error);
            });

        } else if (viewState.segmentationTool === 'polygon') {
            // POLYGON MODE: Add vertex or close polygon

            // Check if starting new polygon on different view/layer
            if (polygonState.isDrawing &&
                (polygonState.currentView !== view || polygonState.currentLayer !== layer)) {
                alert('Termina el polígono actual antes de cambiar de vista o capa.');
                return;
            }

            // Check if clicking near first vertex to close
            if (isNearFirstVertex(coords.xPix, coords.yPix, view)) {
                closeAndFillPolygon(view);
                return;
            }

            // Add vertex
            polygonState.vertices.push({ x: coords.xPix, y: coords.yPix });
            polygonState.isDrawing = true;
            polygonState.currentView = view;
            polygonState.currentLayer = layer;

            // Update vertex count display
            const vertexCount = document.getElementById('vertexCount');
            if (vertexCount) vertexCount.textContent = polygonState.vertices.length;

            // Redraw polygon
            drawPolygon(view);
        }
    }

    // Attach click listeners to all canvas elements
    VIEWS.forEach(view => {
        const canvas = document.getElementById('canvas_' + view);
        if (canvas) {
            canvas.addEventListener('click', (evt) => {
                handleSegmentationClick(view, evt);
            });
        }
    });

    // --- POLYGON MOUSEMOVE HANDLER (Preview Line) ---
    VIEWS.forEach(view => {
        const canvas = document.getElementById('canvas_' + view);
        if (canvas) {
            canvas.addEventListener('mousemove', (evt) => {
                if (!viewState.segmentationMode || viewState.segmentationTool !== 'polygon') return;
                if (!polygonState.isDrawing || polygonState.currentView !== view) return;

                const coords = cssToPngPixels(canvas, evt);
                drawPolygon(view, coords.xPix, coords.yPix);
            });
        }
    });

    // --- KEYBOARD HANDLERS FOR POLYGON ---
    document.addEventListener('keydown', (evt) => {
        if (!viewState.segmentationMode || viewState.segmentationTool !== 'polygon') return;
        if (!polygonState.isDrawing) return;

        // ESC: Cancel polygon
        if (evt.key === 'Escape') {
            clearPolygon();
            evt.preventDefault();
        }

        // Backspace: Remove last vertex
        if (evt.key === 'Backspace') {
            if (polygonState.vertices.length > 0) {
                polygonState.vertices.pop();

                // Update vertex count
                const vertexCount = document.getElementById('vertexCount');
                if (vertexCount) vertexCount.textContent = polygonState.vertices.length;

                // Redraw
                if (polygonState.vertices.length === 0) {
                    clearPolygon();
                } else {
                    drawPolygon(polygonState.currentView);
                }
            }
            evt.preventDefault();
        }

        // Enter: Close polygon
        if (evt.key === 'Enter') {
            closeAndFillPolygon(polygonState.currentView);
            evt.preventDefault();
        }
    });

    // --- SEGMENTATION UI CONTROLS ---

    // Brush size radio buttons
    const brushRadios = document.querySelectorAll('input[name="brushSize"]');
    brushRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            viewState.brushSize = parseInt(this.value);
        });
    });

    // Paint/Erase toggle button
    const paintToggleBtn = document.getElementById('paintModeToggleBtn');
    if (paintToggleBtn) {
        paintToggleBtn.addEventListener('click', () => {
            if (viewState.paintMode === 'paint') {
                viewState.paintMode = 'erase';
                paintToggleBtn.className = 'btn btn-sm btn-danger w-100';
                paintToggleBtn.innerHTML = '<i class="bi bi-eraser-fill"></i> Modo: Borrar';
            } else {
                viewState.paintMode = 'paint';
                paintToggleBtn.className = 'btn btn-sm btn-success w-100';
                paintToggleBtn.innerHTML = '<i class="bi bi-brush-fill"></i> Modo: Pintar';
            }
        });
    }

    // Clear active segmentation button
    const clearSegBtn = document.getElementById('clearActiveSegmentationBtn');
    if (clearSegBtn) {
        clearSegBtn.addEventListener('click', () => {
            if (!confirm('¿Borrar la segmentación activa?')) return;

            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

            fetch('/clear_segmentation', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Reload all views
                    VIEWS.forEach(view => {
                        const slider = document.getElementById('slider_' + view);
                        const layer = parseInt(slider.value);
                        updateImage(view, layer, true, true);
                    });

                    // Clear undo state and disable button
                    polygonState.lastOperation = null;
                    segUndoState[viewState.activeSegmentationId] = false;
                    const undoBtn = document.getElementById('undoLastPolygonBtn');
                    if (undoBtn) {
                        undoBtn.disabled = true;
                        undoBtn.classList.remove('btn-outline-warning');
                        undoBtn.classList.add('btn-outline-secondary');
                    }
                }
            })
            .catch(error => {
                console.error('Clear error:', error);
            });
        });
    }

    // Export active segmentation button
    const exportActiveSegBtn = document.getElementById('exportActiveSegBtn');
    if (exportActiveSegBtn) {
        exportActiveSegBtn.addEventListener('click', () => {
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
            fetch('/export_segmentation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ mode: 'active' })
            })
            .then(response => {
                if (!response.ok) throw new Error('Export failed');
                return response.blob();
            })
            .then(blob => {
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = 'segmentacion.nrrd';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            })
            .catch(error => { alert('Error al exportar: ' + error); });
        });
    }

    // Export all segmentations button
    const exportAllSegBtn = document.getElementById('exportAllSegBtn');
    if (exportAllSegBtn) {
        exportAllSegBtn.addEventListener('click', () => {
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
            fetch('/export_segmentation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ mode: 'all' })
            })
            .then(response => {
                if (!response.ok) throw new Error('Export failed');
                return response.blob();
            })
            .then(blob => {
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = 'segmentaciones.zip';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            })
            .catch(error => { alert('Error al exportar: ' + error); });
        });
    }

    // Undo last polygon button
    const undoLastPolygonBtn = document.getElementById('undoLastPolygonBtn');
    if (undoLastPolygonBtn) {
        undoLastPolygonBtn.addEventListener('click', () => {
            if (!polygonState.lastOperation) {
                alert('No hay operación para deshacer.');
                return;
            }

            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

            fetch('/undo_last_polygon', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Reload all views to show updated segmentation
                    VIEWS.forEach(view => {
                        const slider = document.getElementById('slider_' + view);
                        if (slider) {
                            const layer = parseInt(slider.value);
                            updateImage(view, layer, true, true);
                        }
                    });

                    // Clear last operation and disable undo button
                    polygonState.lastOperation = null;
                    segUndoState[viewState.activeSegmentationId] = false;
                    undoLastPolygonBtn.disabled = true;
                    undoLastPolygonBtn.classList.remove('btn-outline-warning');
                    undoLastPolygonBtn.classList.add('btn-outline-secondary');

                    console.log('Undo successful');
                } else {
                    alert('Error al deshacer: ' + (data.message || 'Unknown error'));
                }
            })
            .catch(error => {
                console.error('Undo error:', error);
                alert('Error al deshacer: ' + error);
            });
        });
    }

    // --- POLYGON DRAWING FUNCTIONS ---

    function clearPolygon() {
        polygonState.vertices = [];
        polygonState.isDrawing = false;
        polygonState.currentView = null;
        polygonState.currentLayer = null;

        // Clear overlays on all views
        VIEWS.forEach(view => clearOverlay(view));

        // Update vertex count display
        const vertexCount = document.getElementById('vertexCount');
        if (vertexCount) vertexCount.textContent = '0';
    }

    function drawPolygon(view, previewX = null, previewY = null) {
        const overlay = document.getElementById(`overlay_${view}`);
        if (!overlay) return;

        const ctx = overlay.getContext('2d');
        const zs = zoomState[view];

        // Clear overlay
        ctx.clearRect(0, 0, overlay.width, overlay.height);

        if (polygonState.vertices.length === 0) return;

        // --- COLOR BASED ON PAINT/ERASE MODE AND ACTIVE SEGMENTATION ---
        const isEraseMode = viewState.paintMode === 'erase';
        const activeSeg = viewState.segmentations.find(s => s.id === viewState.activeSegmentationId);
        const segColor = activeSeg ? activeSeg.color : '#00FFFF';
        const drawColor = isEraseMode ? '#FF0000' : segColor;
        const hex = isEraseMode ? '#FF0000' : segColor;
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        const fillAlpha = `rgba(${r}, ${g}, ${b}, 0.3)`;

        // --- FILL PREVIEW (after 3+ vertices) ---
        if (polygonState.vertices.length >= 3) {
            ctx.fillStyle = fillAlpha; // Red or Cyan preview
            ctx.beginPath();
            ctx.moveTo(polygonState.vertices[0].x, polygonState.vertices[0].y);
            for (let i = 1; i < polygonState.vertices.length; i++) {
                ctx.lineTo(polygonState.vertices[i].x, polygonState.vertices[i].y);
            }
            ctx.closePath();
            ctx.fill();
        }

        // --- VERTICES AND LINES ---
        ctx.strokeStyle = drawColor; // Red or Cyan
        ctx.fillStyle = drawColor;
        ctx.lineWidth = 2 / zs.scale;

        // Draw vertices
        polygonState.vertices.forEach((vertex, index) => {
            ctx.beginPath();
            ctx.arc(vertex.x, vertex.y, 4 / zs.scale, 0, 2 * Math.PI);
            ctx.fill();

            // Draw connecting lines
            if (index > 0) {
                ctx.beginPath();
                ctx.moveTo(polygonState.vertices[index - 1].x, polygonState.vertices[index - 1].y);
                ctx.lineTo(vertex.x, vertex.y);
                ctx.stroke();
            }
        });

        // Draw preview line (from last vertex to mouse position)
        if (previewX !== null && previewY !== null && polygonState.vertices.length > 0) {
            const lastVertex = polygonState.vertices[polygonState.vertices.length - 1];
            ctx.strokeStyle = drawColor;
            ctx.setLineDash([5 / zs.scale, 3 / zs.scale]);
            ctx.beginPath();
            ctx.moveTo(lastVertex.x, lastVertex.y);
            ctx.lineTo(previewX, previewY);
            ctx.stroke();
            ctx.setLineDash([]); // Reset dash
        }
    }

    function isNearFirstVertex(x, y, view) {
        if (polygonState.vertices.length < 3) return false;

        const firstVertex = polygonState.vertices[0];
        const threshold = 10 / zoomState[view].scale; // 10 pixels in internal space

        const dx = x - firstVertex.x;
        const dy = y - firstVertex.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        return distance <= threshold;
    }

    function closeAndFillPolygon(view) {
        if (viewState.activeSegmentationId === null) {
            alert('Crea o selecciona una segmentación primero.');
            return;
        }
        if (polygonState.vertices.length < 3) {
            alert('Se necesitan al menos 3 vértices para crear un polígono.');
            clearPolygon();
            return;
        }

        // Get current layer
        const slider = document.getElementById('slider_' + view);
        const layer = parseInt(slider.value);

        // Get CSRF token
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

        // Prepare payload
        const payload = {
            view: view,
            layer: layer,
            vertices: polygonState.vertices.map(v => ({ xPix: v.x, yPix: v.y })),
            mode: viewState.paintMode
        };

        // --- STORE OPERATION FOR UNDO (before sending) ---
        polygonState.lastOperation = {
            view: view,
            layer: layer,
            vertices: JSON.parse(JSON.stringify(polygonState.vertices)), // Deep copy
            mode: viewState.paintMode
        };

        // Show loaders immediately — covers both backend processing and image re-render time
        VIEWS.forEach(v => showViewLoader(v));

        // Send to backend
        fetch('/fill_polygon', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(payload)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Reload ALL views to show filled polygon (fixes paint AND erase mode)
                VIEWS.forEach(v => {
                    const slider = document.getElementById('slider_' + v);
                    if (slider) {
                        updateImage(v, parseInt(slider.value), true, true);
                    }
                });

                // Update segUndoState and enable undo button
                segUndoState[viewState.activeSegmentationId] = true;
                const undoBtn = document.getElementById('undoLastPolygonBtn');
                if (undoBtn) {
                    undoBtn.disabled = false;
                    undoBtn.classList.remove('btn-outline-secondary');
                    undoBtn.classList.add('btn-outline-warning');
                }

                // Clear polygon state
                clearPolygon();
            } else {
                VIEWS.forEach(v => hideViewLoader(v));
                alert('Error: ' + (data.message || 'Unknown error'));
                // Don't store failed operation
                polygonState.lastOperation = null;
            }
        })
        .catch(error => {
            VIEWS.forEach(v => hideViewLoader(v));
            console.error('Polygon fill error:', error);
            alert('Error al rellenar polígono: ' + error);
            // Don't store failed operation
            polygonState.lastOperation = null;
        });
    }

    // --- TOOL SWITCHING (Brush vs Polygon) ---
    const toolRadios = document.querySelectorAll('input[name="segTool"]');
    const brushControls = document.getElementById('brushControls');
    const polygonControls = document.getElementById('polygonControls');
    const segToolInfo = document.getElementById('segToolInfo');

    toolRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            viewState.segmentationTool = this.value;

            if (this.value === 'brush') {
                brushControls.style.display = 'block';
                polygonControls.style.display = 'none';
                segToolInfo.innerHTML = '<i class="bi bi-info-circle"></i> Haz clic para pintar.';

                // Clear any polygon in progress
                clearPolygon();
            } else if (this.value === 'polygon') {
                brushControls.style.display = 'none';
                polygonControls.style.display = 'block';
                segToolInfo.innerHTML = '<i class="bi bi-info-circle"></i> Clic para agregar vértices.';

                // Clear overlays
                VIEWS.forEach(v => clearOverlay(v));
            }
        });
    });

    // --- LÓGICA DEL PLUGIN DE INTELIGENCIA ARTIFICIAL ---
    const runAiBtn = document.getElementById('runAiBtn');
    if (runAiBtn) {
        runAiBtn.addEventListener('click', () => {
            // Confirmación porque es un proceso pesado
            if (!confirm("Esto iniciará la red neuronal para segmentar la imagen. El proceso puede tardar entre 30 segundos y varios minutos dependiendo del hardware. ¿Deseas continuar?")) return;

            // 1. Mostrar pantalla de carga y bloquear botón
            const loader = document.getElementById('loader-wrapper');
            if (loader) { loader.style.display = 'flex'; loader.style.opacity = '1'; }
            runAiBtn.disabled = true;
            runAiBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Procesando IA...';

            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

            // 2. Hacer la petición al servidor web
            fetch('/api/run_ai_segmentation', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    alert("Segmentación inteligente completada con éxito.");
                    
                    // 3. Forzar recarga de las 3 vistas para que se dibuje la nueva segmentación
                    VIEWS.forEach(view => {
                        const slider = document.getElementById(`slider_${view}`);
                        if (slider) updateImage(view, slider.value, true);
                    });
                    
                    // Forzar recarga del modelo 3D
                    window.refresh3dImage?.();
                } else {
                    alert("⚠️ Error en IA: " + data.message);
                }
            })
            .catch(error => {
                console.error("Error de red con la IA:", error);
                alert("Ocurrió un error de conexión al procesar la IA.");
            })
            .finally(() => {
                // 4. Ocultar loader y restaurar botón, pase lo que pase
                if (loader) {
                    loader.style.opacity = '0';
                    setTimeout(() => { loader.style.display = 'none'; }, 500);
                }
                runAiBtn.disabled = false;
                runAiBtn.innerHTML = '<i class="bi bi-cpu"></i> Auto-Segmentar (Swin-UNETR)';
            });
        });
    }

    // --- CARGAR METADATA ---
    async function loadMetadata() {
        // Buscamos el cuerpo de la tabla del modal
        const tableBody = document.getElementById('metadataTableBody');
        if (!tableBody) return;

        try {
            const response = await fetch('/get_dicom_metadata');
            if (!response.ok) throw new Error('Error de red');
            
            const data = await response.json();
            
            // Limpiar tabla
            tableBody.innerHTML = '';
            
            // Crear filas de tabla
            for (const [key, value] of Object.entries(data)) {
                // Ocultamos datos técnicos que no deben verse en la tabla
                if (key === 'Spacing' || key === 'Origin') continue;
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td class="fw-bold text-secondary ps-4" style="width: 40%;">${key}</td>
                    <td class="text-light font-monospace">${value}</td>
                `;
                tableBody.appendChild(row);
            }
        } catch (error) {
            tableBody.innerHTML = '<tr><td colspan="2" class="text-center text-danger">Error cargando información.</td></tr>';
            console.error(error);
        }
    }

    // --- Conectar Inputs Numéricos (+/-) con la lógica ---
    function bindWindowLevelInput(inputId, type) {
        const input = document.getElementById(inputId);
        const btnMinus = document.getElementById(`${inputId}-minus`);
        const btnPlus = document.getElementById(`${inputId}-plus`);
        
        if (!input) return;

        const triggerUpdate = () => {
            let val = parseInt(input.value, 10);
            if (isNaN(val)) return;

            // Leemos los sliders para tener el otro valor
            const currentW = parseInt(document.getElementById('ww_slider').value, 10);
            const currentL = parseInt(document.getElementById('wc_slider').value, 10);

            if (type === 'ww') updateWWWC(val, currentL, 'fields');
            else updateWWWC(currentW, val, 'fields');
            
            highlightPreset(null); // Apagar presets si editamos manual
        };

        input.addEventListener('change', triggerUpdate); // Al dar Enter
        
        if (btnMinus) {
            btnMinus.onclick = () => {
                input.value = parseInt(input.value || 0) - 10;
                triggerUpdate();
            };
        }
        if (btnPlus) {
            btnPlus.onclick = () => {
                input.value = parseInt(input.value || 0) + 10;
                triggerUpdate();
            };
        }
    }

    // --- INICIALIZACIÓN ---
    
    // Usamos la nueva función para Ventana/Nivel
    bindWindowLevelInput('windowInput', 'ww'); 
    bindWindowLevelInput('levelInput', 'wc');
    
    // Para el histograma
    setupCustomSpinner('cutoffInput', 0.5, () => {
        contrastState.cutoff = parseFloat(cutoffInput.value) || 0;
        drawCurveAndHistogram();
    });

    setup3DRendererControls();
    loadMetadata();

    // --- MULTI-SEGMENTATION UI EVENT LISTENERS ---
    document.getElementById('newSegmentationBtn')?.addEventListener('click', showCreateSegmentationForm);
    document.getElementById('saveNewSegBtn')?.addEventListener('click', submitCreateSegmentation);
    document.getElementById('cancelNewSegBtn')?.addEventListener('click', hideCreateSegmentationForm);
    document.getElementById('newSegNameInput')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); submitCreateSegmentation(); }
    });

    loadSegmentations();

    // Inicializa los sliders de corte y carga las imágenes iniciales.

    VIEWS.forEach(view => {
        const slider = document.getElementById(`slider_${view}`);
        if (slider) {
            setupSliceSlider(view);
            setupZoomPan(view);
            bindInspector(view);
            updateImage(view, slider.value, true);

            // Set initial cursor to grab (for pan/zoom mode)
            const wrapper = document.getElementById(`card_${view}`).querySelector('.image-wrapper');
            const canvas = document.getElementById(`canvas_${view}`);
            const overlay = document.getElementById(`overlay_${view}`);

            if (wrapper) wrapper.style.cursor = 'grab';
            if (canvas) canvas.style.cursor = 'grab';
            if (overlay) overlay.style.cursor = 'grab';
        }
    });
    
    const curveEditorWrapper = document.getElementById('curve-editor-wrapper');
    if(curveEditorWrapper){
        const curveResizeObserver = new ResizeObserver(entries => {
            if(entries[0].contentRect.width > 0) {
                const newWidth = entries[0].contentRect.width;
                const newHeight = newWidth / 1.5;
                if (histogramCanvas) {
                    histogramCanvas.width = newWidth;
                    histogramCanvas.height = newHeight;
                }
                if (curveCanvas) {
                    curveCanvas.width = newWidth;
                    curveCanvas.height = newHeight;
                }
                drawCurveAndHistogram();
            }
        });
        curveResizeObserver.observe(curveEditorWrapper);
    }

    function updateMinimap(view) {
        const container = document.getElementById(`minimap_container_${view}`);
        const miniCanvas = document.getElementById(`minimap_canvas_${view}`);
        const viewport = document.getElementById(`minimap_viewport_${view}`);
        const mainCanvas = document.getElementById(`canvas_${view}`);
        const zs = zoomState[view];

        if (!mainCanvas || !miniCanvas || !viewport) return;

        // Solo mostrar si el zoom es significativo
        container.style.display = (zs.scale > 1.1) ? 'block' : 'none';
        if (zs.scale <= 1.1) return;

        const ctx = miniCanvas.getContext('2d');
        const wrapper = mainCanvas.parentElement;

        // 1. Ajustar miniatura (Mantenemos 120px de ancho para mejor visibilidad)
        const miniWidth = 120;
        miniCanvas.width = miniWidth;
        miniCanvas.height = miniWidth * (mainCanvas.height / mainCanvas.width);

        // Sincronizar el contenedor con el canvas para evitar desfases de margen
        container.style.width = miniCanvas.width + 'px';
        container.style.height = miniCanvas.height + 'px';

        // 2. Dibujar miniatura (hereda brillo/contraste)
        ctx.clearRect(0, 0, miniCanvas.width, miniCanvas.height);
        ctx.drawImage(mainCanvas, 0, 0, miniCanvas.width, miniCanvas.height);

        // 3. LÓGICA DE SINCRONIZACIÓN 100% (Basada en la "Ventana" de visión)
        // Calculamos cuánto de la imagen cabe en el wrapper (cuadrante negro)
        const totalScaledWidth = mainCanvas.width * zs.scale;
        const totalScaledHeight = mainCanvas.height * zs.scale;

        // Proporción del tamaño del visor respecto a la imagen con zoom
        const widthRatio = wrapper.clientWidth / totalScaledWidth;
        const heightRatio = wrapper.clientHeight / totalScaledHeight;

        // Posición del visor relativa al origen de la imagen (0 a 1)
        // Restamos el paneo y dividimos por el tamaño total escalado
        const leftOffset = (-zs.panX) / totalScaledWidth;
        const topOffset = (-zs.panY) / totalScaledHeight;

        // 4. Aplicar dimensiones al recuadro amarillo
        // Limitamos a 100% para que el recuadro no se salga de la miniatura
        viewport.style.width = Math.min(100, widthRatio * 100) + '%';
        viewport.style.height = Math.min(100, heightRatio * 100) + '%';
        viewport.style.left = Math.max(0, leftOffset * 100) + '%';
        viewport.style.top = Math.max(0, topOffset * 100) + '%';
    }

    function drawCrosshairFromVoxel(view) {
        const v = viewState.lastVoxel;
        const s = viewState.scales;
        if (v.x === null) return;

        let px, py;
        // Mapeo según la vista para posicionar la cruz correctamente en los 3 planos
        if (view === 'axial') { px = v.x; py = v.y * s.axial; }
        else if (view === 'coronal') { px = v.x; py = v.z * s.coronal; }
        else if (view === 'sagital') { px = v.y; py = v.z * s.sagittal; }

        drawCrosshair(view, px, py);
    }

    // --- MODO CROSSHAIR (VISTAS ENLAZADAS) ---
    function moveCrosshair(view, e) {
        const mainCanvas = document.getElementById(`canvas_${view}`);
        if (!mainCanvas) return;
        const mapped = cssToPngPixels(mainCanvas, e);
        if (!mapped) return;

        const slider = document.getElementById(`slider_${view}`);
        if (!slider) return;
        const idx = parseInt(slider.value, 10);

        fetch(`/hu_value?view=${view}&x=${mapped.xPix}&y=${mapped.yPix}&index=${idx}`)
            .then(r => r.json())
            .then(data => {
                if (!data.error && data.voxel) {
                    if (data.scales) viewState.scales = data.scales;
                    crosshairState.x = data.voxel.x;
                    crosshairState.y = data.voxel.y;
                    crosshairState.z = data.voxel.z;
                    syncViewsFromVoxel(view, data.voxel);
                }
            })
            .catch(err => console.warn('moveCrosshair error:', err));
    }

    // --- CINE PLAYBACK ---
    function cineTick() {
        const views = CINE.view === 'all' ? ['axial', 'sagital', 'coronal'] : [CINE.view];
        let anySliderExists = false;

        views.forEach(view => {
            const slider = document.getElementById(`slider_${view}`);
            const number = document.getElementById(`number_${view}`);
            if (!slider) return;
            anySliderExists = true;

            let val = parseInt(slider.value, 10) + 1;
            const max = parseInt(slider.max, 10);

            if (val > max) {
                val = CINE.loop ? 0 : max;
            }

            slider.value = val;
            if (number) number.value = val;
            updateImage(view, val, true);
        });

        if (!CINE.loop && anySliderExists) {
            const allAtEnd = views.every(view => {
                const s = document.getElementById(`slider_${view}`);
                return s && parseInt(s.value, 10) >= parseInt(s.max, 10);
            });
            if (allAtEnd) stopCine();
        }
    }

    function startCine() {
        if (CINE._id) clearInterval(CINE._id);
        CINE.active = true;
        CINE._id = setInterval(cineTick, Math.round(1000 / CINE.fps));
        const icon = document.getElementById('cinePlayIcon');
        if (icon) icon.className = 'bi bi-pause-fill';
    }

    function stopCine() {
        if (CINE._id) { clearInterval(CINE._id); CINE._id = null; }
        CINE.active = false;
        const icon = document.getElementById('cinePlayIcon');
        if (icon) icon.className = 'bi bi-play-fill';
    }

    function toggleCine() {
        if (CINE.active) stopCine(); else startCine();
    }

    // --- BOTÓN CROSSHAIR ---
    setupPluginButton('crosshairBtn', null, (isActive) => {
        viewState.crosshairMode = isActive;
        if (isActive) {
            updateCursorStyle('crosshair');
        } else {
            updateCursorStyle('grab');
            VIEWS.forEach(v => clearOverlay(v));
        }
    });

    // --- CONTROLES CINE ---
    document.getElementById('cineBtn')?.addEventListener('click', () => {
        const bar = document.getElementById('cine-bar');
        const btn = document.getElementById('cineBtn');
        if (!bar) return;
        if (bar.classList.contains('d-none')) {
            bar.classList.remove('d-none');
            btn?.classList.add('btn-udg-rojo');
        } else {
            bar.classList.add('d-none');
            btn?.classList.remove('btn-udg-rojo');
            stopCine();
        }
    });

    document.getElementById('cinePlayBtn')?.addEventListener('click', toggleCine);

    document.getElementById('cinePrevBtn')?.addEventListener('click', () => {
        stopCine();
        const targets = CINE.view === 'all' ? ['axial', 'sagital', 'coronal'] : [CINE.view];
        targets.forEach(v => {
            const slider = document.getElementById(`slider_${v}`);
            const number = document.getElementById(`number_${v}`);
            if (slider) { slider.value = 0; if (number) number.value = 0; updateImage(v, 0, true); }
        });
    });

    document.getElementById('cineNextBtn')?.addEventListener('click', () => {
        stopCine();
        const targets = CINE.view === 'all' ? ['axial', 'sagital', 'coronal'] : [CINE.view];
        targets.forEach(v => {
            const slider = document.getElementById(`slider_${v}`);
            const number = document.getElementById(`number_${v}`);
            if (slider) {
                const max = parseInt(slider.max, 10);
                slider.value = max; if (number) number.value = max; updateImage(v, max, true);
            }
        });
    });

    document.getElementById('cineViewSelect')?.addEventListener('change', (e) => {
        CINE.view = e.target.value;
        if (CINE.active) startCine();
    });

    document.getElementById('cineFpsSlider')?.addEventListener('input', (e) => {
        CINE.fps = parseInt(e.target.value, 10);
        const display = document.getElementById('cineFpsDisplay');
        if (display) display.textContent = CINE.fps;
        if (CINE.active) startCine();
    });

    document.getElementById('cineLoopCheck')?.addEventListener('change', (e) => {
        CINE.loop = e.target.checked;
    });

    // --- FLIP / INVERT ---
    function redrawAllViews() {
        VIEWS.forEach(v => {
            if (v !== '3D') applyLutAndDraw(v);
        });
    }

    document.getElementById('invertBtn')?.addEventListener('click', () => {
        viewTransforms.invert = !viewTransforms.invert;
        document.getElementById('invertBtn')?.classList.toggle('btn-udg-rojo', viewTransforms.invert);
        redrawAllViews();
    });

    document.getElementById('flipHBtn')?.addEventListener('click', () => {
        viewTransforms.flipH = !viewTransforms.flipH;
        document.getElementById('flipHBtn')?.classList.toggle('btn-udg-rojo', viewTransforms.flipH);
        redrawAllViews();
    });

    document.getElementById('flipVBtn')?.addEventListener('click', () => {
        viewTransforms.flipV = !viewTransforms.flipV;
        document.getElementById('flipVBtn')?.classList.toggle('btn-udg-rojo', viewTransforms.flipV);
        redrawAllViews();
    });

    // --- RESET VIEW ---
    document.getElementById('resetViewBtn')?.addEventListener('click', () => {
        VIEWS.forEach(v => {
            if (v === '3D') return;
            zoomState[v] = { scale: 1, panX: 0, panY: 0, isDragging: false };
            applyLutAndDraw(v);
        });
    });

    // --- SCREENSHOT (composite PNG de las 3 vistas) ---
    document.getElementById('screenshotBtn')?.addEventListener('click', () => {
        const gap = 8;
        const canvases = ['axial', 'sagital', 'coronal'].map(v => document.getElementById(`canvas_${v}`)).filter(Boolean);
        if (canvases.length === 0) return;

        const h = Math.max(...canvases.map(c => c.height));
        const totalW = canvases.reduce((acc, c) => acc + c.width, 0) + gap * (canvases.length - 1);

        const out = document.createElement('canvas');
        out.width = totalW;
        out.height = h;
        const ctx = out.getContext('2d');
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, totalW, h);

        let offsetX = 0;
        canvases.forEach(c => {
            const offsetY = Math.round((h - c.height) / 2);
            ctx.drawImage(c, offsetX, offsetY);
            offsetX += c.width + gap;
        });

        const a = document.createElement('a');
        a.download = `dicom_viewer_${Date.now()}.png`;
        a.href = out.toDataURL('image/png');
        a.click();
    });

    // --- REGLA (RULER) ---
    function _rulerMmPerPixel(view) {
        const sp = (typeof DICOM_SPACING !== 'undefined') ? DICOM_SPACING : { dx: 1, dy: 1, dz: 1 };
        if (view === 'axial')   return { px: sp.dx, py: sp.dy };
        if (view === 'coronal') return { px: sp.dx, py: sp.dx };
        return { px: sp.dy, py: sp.dx }; // sagital
    }

    function drawRulerPreview(view, ptA, ptB) {
        const ov = document.getElementById(`overlay_${view}`);
        const cv = document.getElementById(`canvas_${view}`);
        if (!ov || !cv) return;
        if (ov.width !== cv.width || ov.height !== cv.height) {
            ov.width = cv.width; ov.height = cv.height;
        }
        const ctx = ov.getContext('2d');
        ctx.clearRect(0, 0, ov.width, ov.height);

        const zs = zoomState[view];
        ctx.save();
        ctx.strokeStyle = '#FFD700';
        ctx.lineWidth = 1.5 / zs.scale;
        ctx.setLineDash([4 / zs.scale, 2 / zs.scale]);
        ctx.beginPath();
        ctx.moveTo(ptA.x, ptA.y);
        ctx.lineTo(ptB.x, ptB.y);
        ctx.stroke();
        ctx.restore();
    }

    function drawRulerFinal(view, ptA, ptB) {
        const ov = document.getElementById(`overlay_${view}`);
        const cv = document.getElementById(`canvas_${view}`);
        if (!ov || !cv) return;
        if (ov.width !== cv.width || ov.height !== cv.height) {
            ov.width = cv.width; ov.height = cv.height;
        }
        const ctx = ov.getContext('2d');
        ctx.clearRect(0, 0, ov.width, ov.height);

        const zs = zoomState[view];
        const mmp = _rulerMmPerPixel(view);
        const dx = ptB.x - ptA.x;
        const dy = ptB.y - ptA.y;
        const distMm = Math.sqrt((dx * mmp.px) ** 2 + (dy * mmp.py) ** 2);
        const label = `${distMm.toFixed(1)} mm`;

        ctx.save();
        ctx.strokeStyle = '#FFD700';
        ctx.lineWidth = 1.5 / zs.scale;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(ptA.x, ptA.y);
        ctx.lineTo(ptB.x, ptB.y);
        ctx.stroke();

        // Ticks en extremos
        const angle = Math.atan2(dy, dx);
        const tickLen = 5 / zs.scale;
        [ptA, ptB].forEach(pt => {
            ctx.beginPath();
            ctx.moveTo(pt.x + Math.sin(angle) * tickLen, pt.y - Math.cos(angle) * tickLen);
            ctx.lineTo(pt.x - Math.sin(angle) * tickLen, pt.y + Math.cos(angle) * tickLen);
            ctx.stroke();
        });

        // Etiqueta con fondo
        const midX = (ptA.x + ptB.x) / 2;
        const midY = (ptA.y + ptB.y) / 2 - 6 / zs.scale;
        const fontSize = Math.max(9, 13 / zs.scale);
        ctx.font = `bold ${fontSize}px monospace`;
        ctx.setLineDash([]);
        const tw = ctx.measureText(label).width;
        const pad = 3 / zs.scale;
        ctx.fillStyle = 'rgba(0,0,0,0.65)';
        ctx.fillRect(midX - tw / 2 - pad, midY - fontSize, tw + pad * 2, fontSize + pad * 2);
        ctx.fillStyle = '#FFD700';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'alphabetic';
        ctx.fillText(label, midX, midY);
        ctx.restore();
    }

    setupPluginButton('rulerBtn', null, (isActive) => {
        viewState.rulerMode = isActive;
        if (isActive) {
            updateCursorStyle('crosshair');
        } else {
            updateCursorStyle('grab');
            rulerState.ptA = null; rulerState.ptB = null; rulerState.drawing = false;
            VIEWS.forEach(v => { if (v !== '3D') clearOverlay(v); });
        }
    });

    // --- LÍNEAS DE REFERENCIA (se actualizan con cada cambio de slider o zoom) ---
    function setRefLine(view, pixelX, pixelY) {
        const zs = zoomState[view];
        const chH = document.getElementById(`ch_h_${view}`);
        const chV = document.getElementById(`ch_v_${view}`);
        if (chH) {
            chH.style.display = 'block';
            chH.style.top = (zs.panY + pixelY * zs.scale) + 'px';
        }
        if (chV) {
            chV.style.display = 'block';
            chV.style.left = (zs.panX + pixelX * zs.scale) + 'px';
        }
    }

    function drawReferenceLines() {
        const slVal = (id) => parseInt(document.getElementById(id)?.value  || 0, 10);
        const slMax = (id) => parseInt(document.getElementById(id)?.max    || 0, 10) + 1;

        const z    = slVal('slider_axial');
        const y    = slVal('slider_coronal');
        const x    = slVal('slider_sagital');
        const maxZ = slMax('slider_axial');
        const maxY = slMax('slider_coronal');
        const maxX = slMax('slider_sagital');

        // Guard: datos no cargados todavía
        if (maxZ <= 1 || maxY <= 1 || maxX <= 1) return;

        const cAx = document.getElementById('canvas_axial');
        const cCo = document.getElementById('canvas_coronal');
        const cSa = document.getElementById('canvas_sagital');

        // Axial (ancho≈X voxels, alto≈Y voxels)
        //   V = dónde está el corte sagital  →  col x
        //   H = dónde está el corte coronal  →  fila y
        if (cAx && cAx.width > 0 && cAx.height > 0)
            setRefLine('axial',
                Math.round(x * cAx.width  / maxX),
                Math.round(y * cAx.height / maxY));

        // Coronal (ancho≈X voxels, alto≈Z*escala)
        //   V = dónde está el corte sagital  →  col x
        //   H = dónde está el corte axial    →  fila z
        if (cCo && cCo.width > 0 && cCo.height > 0)
            setRefLine('coronal',
                Math.round(x * cCo.width  / maxX),
                Math.round(z * cCo.height / maxZ));

        // Sagital (ancho≈Y voxels, alto≈Z*escala)
        //   V = dónde está el corte coronal  →  col y
        //   H = dónde está el corte axial    →  fila z
        if (cSa && cSa.width > 0 && cSa.height > 0)
            setRefLine('sagital',
                Math.round(y * cSa.width  / maxY),
                Math.round(z * cSa.height / maxZ));
    }
});

// --- FUNCIONES GLOBALES ---
function toggleFullscreen(id) {
    const element = document.getElementById(id);
    if (!element) return;

    if (element.classList.contains('fullscreen-active')) {
        element.classList.remove('fullscreen-active');
    } else {
        element.classList.add('fullscreen-active');
    }
}
