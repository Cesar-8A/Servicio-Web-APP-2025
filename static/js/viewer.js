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
        huMode: false,
        inspectorMode: false,
        scales: { axial: 1.0, coronal: 1.0, sagittal: 1.0 } // Aspect ratio scaling factors
    };
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
    
    setupPluginButton('huPickerPluginBtn', 'huPickerPluginContainer', (isActive) => {
        // Lógica específica para HU
        const huToggle = document.getElementById('huToggle');
        if (huToggle) huToggle.click(); // Mantener compatibilidad con tu lógica vieja
        
        // Si activamos HU, apagamos Inspector para evitar conflictos
        if (isActive) {
            viewState.inspectorMode = false;
            const inspectorBtn = document.getElementById('inspectorPluginBtn');
            if (inspectorBtn) inspectorBtn.classList.remove('btn-udg-rojo');
            VIEWS.forEach(clearOverlay);
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
    setupPluginButton('inspectorPluginBtn', null, (isActive) => {
        viewState.inspectorMode = isActive;
        
        if (isActive) {
            // --- AL ACTIVAR ---
            viewState.huMode = false; // Apagar HU para evitar conflictos
            
            // Apagar visualmente el botón HU si estaba prendido
            const huBtn = document.getElementById('huPickerPluginBtn');
            if (huBtn) huBtn.classList.remove('btn-udg-rojo');
            
        } else {
            // Limpiamos los canvas de todas las vistas para borrar las líneas
            VIEWS.forEach(view => clearOverlay(view));
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
    
    // Función para resaltar el botón activo
    function highlightPreset(activeId) {
        // Lista de IDs de los botones
        const presets = ['presetBtnLung', 'presetBtnBone', 'presetBtnSoftTissue'];
        
        presets.forEach(id => {
            const btn = document.getElementById(id);
            if (btn) {
                // 1. Limpiamos el estilo activo de TODOS
                btn.classList.remove('preset-active');
                // 2. Volvemos al estilo gris por defecto
                btn.classList.add('btn-outline-secondary');
            }
        });

        // 3. Activamos SOLO el que se clickeó (si hay alguno)
        if (activeId) {
            const activeBtn = document.getElementById(activeId);
            if (activeBtn) {
                activeBtn.classList.remove('btn-outline-secondary'); // Quitar gris
                activeBtn.classList.add('preset-active'); // Poner azul médico
            }
        }
    }

    // Listeners para Presets
    document.getElementById('presetBtnLung')?.addEventListener('click', () => {
        updateWWWC(1500, -600);
        highlightPreset('presetBtnLung');
    });
    
    document.getElementById('presetBtnBone')?.addEventListener('click', () => {
        updateWWWC(2500, 480);
        highlightPreset('presetBtnBone');
    });
    
    document.getElementById('presetBtnSoftTissue')?.addEventListener('click', () => {
        updateWWWC(400, 40);
        highlightPreset('presetBtnSoftTissue');
    });
    
    wwSlider?.addEventListener('input', () => {
        updateWWWC(parseInt(wwSlider.value), parseInt(wcSlider.value), 'sliders');
        highlightPreset(null); // Apagar botones
    });
    
    wcSlider?.addEventListener('input', () => {
        updateWWWC(parseInt(wwSlider.value), parseInt(wcSlider.value), 'sliders');
        highlightPreset(null); // Apagar botones
    });


    // --- LÓGICA DE SLIDERS DE CORTE ---
    function setupSliceSlider(view) {
        const slider = document.getElementById(`slider_${view}`);
        const number = document.getElementById(`number_${view}`);
        if (!slider || !number) return;
        const update = (value) => {
            slider.value = value;
            number.value = value;
            updateImage(view, value, true);
        };
        slider.addEventListener('input', () => update(slider.value));
        number.addEventListener('input', () => update(number.value));
    }

    // --- LÓGICA DE IMAGEN Y CANVAS ---
    function updateImage(view, layer, forceReloadFromServer) {
        const slider = document.getElementById(`slider_${view}`);
        if (!slider) return;
        const currentLayer = layer ?? slider.value;
        if (forceReloadFromServer) {
            const img = new Image();
            img.crossOrigin = "Anonymous";
            img.onload = () => {
                viewState.baseImages[view] = img;
                applyLutAndDraw(view);
            };
            img.src = `/image/${view}/${currentLayer}?ww=${viewState.ww}&wc=${viewState.wc}&t=${new Date().getTime()}`;
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

        // Set canvas INTERNAL dimensions to match PNG (preserves aspect ratio)
        canvas.width = baseImage.naturalWidth;
        canvas.height = baseImage.naturalHeight;

        console.log(`DEBUG applyLutAndDraw [${view}]: PNG naturalWidth=${baseImage.naturalWidth}, naturalHeight=${baseImage.naturalHeight}`);

        // Let CSS max-width/max-height determine actual display size
        // Don't set explicit style.width/height - let it scale naturally

        ctx.drawImage(baseImage, 0, 0);
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const data = imageData.data;
        for (let i = 0; i < data.length; i += 4) {
            const grayValue = data[i];
            const mappedValue = contrastState.lut[grayValue];
            data[i] = mappedValue;
            data[i + 1] = mappedValue;
            data[i + 2] = mappedValue;
        }
        ctx.putImageData(imageData, 0, 0);

        // Sync overlay canvas to match main canvas
        if (overlay) {
            // Only resize if dimensions changed (resizing clears the canvas!)
            if (overlay.width !== canvas.width || overlay.height !== canvas.height) {
                overlay.width = canvas.width;
                overlay.height = canvas.height;
            }

            // Position overlay to cover the main canvas
            const canvasRect = canvas.getBoundingClientRect();
            const wrapperRect = canvas.parentElement.getBoundingClientRect();
            overlay.style.left = (canvasRect.left - wrapperRect.left) + 'px';
            overlay.style.top = (canvasRect.top - wrapperRect.top) + 'px';
            overlay.style.width = canvasRect.width + 'px';
            overlay.style.height = canvasRect.height + 'px';
        }
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
            drawCurveAndHistogram();
        } catch (error) {
            console.error(error);
        }
    }

    function drawHistogram() {
        if (!contrastState.histogramData) return;
        const { width, height } = histogramCanvas;
        histCtx.clearRect(0, 0, width, height);
        const { counts, bin_edges } = contrastState.histogramData;
        const sortedCounts = [...counts].sort((a, b) => a - b);
        const cutoffIndex = Math.floor(sortedCounts.length * (1 - contrastState.cutoff / 100));
        const maxCount = sortedCounts[cutoffIndex] || 1;
        const minHU = contrastState.minHU;
        const maxHU = contrastState.maxHU;
        histCtx.fillStyle = 'rgba(120, 150, 200, 0.6)';
        for (let i = 0; i < counts.length; i++) {
            const count = counts[i];
            if (count === 0) continue;
            const xStart = ((bin_edges[i] - minHU) / (maxHU - minHU)) * width;
            const xEnd = ((bin_edges[i+1] - minHU) / (maxHU - minHU)) * width;
            const barWidth = Math.max(1, xEnd - xStart);
            let barHeight;
            if (contrastState.logScale) {
                barHeight = (Math.log1p(count) / Math.log1p(maxCount)) * height;
            } else {
                barHeight = (count / maxCount) * height;
            }
            if (barHeight > 0) {
                 histCtx.fillRect(xStart, height - barHeight, barWidth, barHeight);
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

    // --- LÓGICA DEL SELECTOR HU ---
    const huToggleBtn = document.getElementById('huToggle');
    const huInfo = document.getElementById("huInfo");
    const huResult = document.getElementById("huResult");

    huToggleBtn?.addEventListener('click', () => {
        viewState.huMode = !viewState.huMode;
        if (huInfo) huInfo.textContent = viewState.huMode ? "Haz clic en una imagen para obtener el valor HU." : "";
        if (!viewState.huMode) {
            VIEWS.forEach(clearOverlay);
        }
    });

    function cssToPngPixels(canvasEl, evt) {
        // Get the canvas bounding rectangle
        const canvasRect = canvasEl.getBoundingClientRect();

        // Get click position relative to canvas
        const cssX = evt.clientX - canvasRect.left;
        const cssY = evt.clientY - canvasRect.top;

        // Get canvas internal dimensions
        const internalW = canvasEl.width;
        const internalH = canvasEl.height;

        // Get canvas CSS display dimensions
        const displayW = canvasRect.width;
        const displayH = canvasRect.height;

        // Calculate the scaling factor between display and internal
        const scaleX = internalW / displayW;
        const scaleY = internalH / displayH;

        // Convert CSS coordinates to internal pixel coordinates
        const xPix = Math.floor(cssX * scaleX);
        const yPix = Math.floor(cssY * scaleY);

        console.log('Debug cssToPngPixels:', {
            internalW: internalW,
            internalH: internalH,
            displayW: displayW,
            displayH: displayH,
            scaleX: scaleX,
            scaleY: scaleY,
            cssX: cssX,
            cssY: cssY,
            xPix: xPix,
            yPix: yPix
        });

        // Validate bounds
        if (xPix < 0 || yPix < 0 || xPix >= internalW || yPix >= internalH) {
            return null;
        }

        return {
            xPix: xPix,
            yPix: yPix,
            cssX: xPix,
            cssY: yPix
        };
    }

    function drawMarker(view, cssX, cssY) {
        const overlay = document.getElementById(`overlay_${view}`);
        const mainCanvas = document.getElementById(`canvas_${view}`);
        if (!overlay || !mainCanvas) return;

        const ctx = overlay.getContext("2d");
        ctx.clearRect(0, 0, overlay.width, overlay.height);

        // Marker styling
        ctx.fillStyle = "#FFD700";
        ctx.strokeStyle = "red";
        ctx.lineWidth = 2;

        ctx.beginPath();
        ctx.arc(cssX, cssY, 5, 0, 2 * Math.PI);
        ctx.fill();
        ctx.stroke();
    }
    
    function clearOverlay(view) {
        const overlay = document.getElementById(`overlay_${view}`);
        if (overlay) {
             const ctx = overlay.getContext("2d");
             ctx.clearRect(0, 0, overlay.width, overlay.height);
        }
    }

    function bindHU(view) {
        const mainCanvas = document.getElementById(`canvas_${view}`);
        const wrapper = document.getElementById(`card_${view}`).querySelector('.image-wrapper');
        
        if (!wrapper) return;
        
        wrapper.addEventListener("click", (evt) => {
            if (zoomState[view] && zoomState[view].isDragging) {
                return; // Fue un arrastre, no un clic de selección
            }

            // Si estábamos arrastrando (pan), no dispares el HU
            if (!viewState.huMode || (zoomState[view] && zoomState[view].isDragging)) return;
            
            VIEWS.forEach(clearOverlay);
            
            // --- AQUÍ ESTÁ EL CAMBIO: Pasamos 'view' como tercer argumento ---
            const mapped = cssToPngPixels(mainCanvas, evt); 
            
            if (!mapped) return; // Clic fuera

            const slider = document.getElementById(`slider_${view}`);
            const idx = parseInt(slider.value, 10);
            
            fetch(`/hu_value?view=${view}&x=${mapped.xPix}&y=${mapped.yPix}&index=${idx}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        huResult.textContent = "Error: " + data.error;
                        return;
                    }
                    // --- MEJORA DE FORMATO HU ---
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
                            <span style="color: #bbbbbb; font-size: 0.7rem; letter-spacing: 1px; text-transform: uppercase;">Densidad:</span>
                            <span style="color: #0dcaf0; font-weight: bold; font-size: 1rem;">${data.hu} HU</span>
                        </div>
                    `;
                    drawMarker(view, mapped.cssX, mapped.cssY);
                })
                .catch(() => {
                    huResult.textContent = "Error al obtener valor HU.";
                });
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
            const iframe = document.getElementById('DicomRender');

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
                    // ÉXITO: Forzamos actualización del iframe 3D
                    console.log("RT cargado:", data.message);
                    if (iframe) {
                        // Truco del timestamp para obligar al navegador a redibujar
                        const currentSrc = iframe.src.split('?')[0];
                        iframe.src = currentSrc + '?t=' + new Date().getTime();
                    }
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

    // --- LÓGICA DE CAMBIO DE RENDERIZADO 3D  ---
    function setup3DRendererControls() {
        const renderModeRadios = document.querySelectorAll('input[name="renderMode"]');
        const iframe = document.getElementById('DicomRender');
        if (!iframe || renderModeRadios.length === 0) return;

        renderModeRadios.forEach(radio => {
            radio.addEventListener('change', function() {
                // Efecto visual de carga
                iframe.style.opacity = '0.5'; 
                const token = document.querySelector('meta[name="csrf-token"]').content;
                
                fetch('/update_render_mode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
                    body: JSON.stringify({ mode: this.value })
                })
                .then(response => response.json())
                .then(data => {
                    if(data.status === 'success') { 
                        // Truco para recargar el iframe forzando actualización
                        iframe.src = iframe.src.split('?')[0] + '?t=' + new Date().getTime(); 
                    } else { 
                        alert('Error al cambiar el modo.'); 
                    }
                })
                .catch(error => console.error("Error:", error))
                .finally(() => {
                     // Restaurar opacidad cuando termine (o cuando cargue el iframe)
                     setTimeout(() => { iframe.style.opacity = '1'; }, 1000);
                });
            });
        });
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
        };

        // ZOOM (Rueda del mouse)
        wrapper.addEventListener('wheel', (e) => {
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

        wrapper.addEventListener('mousedown', (e) => {
            // Permitimos mover siempre (excepto si quisieras bloquearlo en algún modo)
            isDown = true;
            zoomState[view].isDragging = false; 
            
            startX = e.clientX;
            startY = e.clientY;
            
            initialPanX = zoomState[view].panX;
            initialPanY = zoomState[view].panY;
            
            wrapper.style.cursor = 'grabbing';
        });

        window.addEventListener('mousemove', (e) => {
            if (!isDown) return;
            e.preventDefault();
            
            // Calculamos cuánto se movió el mouse
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;

            if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
                zoomState[view].isDragging = true;
            }

            zoomState[view].panX = initialPanX + dx;
            zoomState[view].panY = initialPanY + dy;
            
            updateTransform();
        });

        window.addEventListener('mouseup', () => {
            isDown = false;
            wrapper.style.cursor = 'grab';
            
            setTimeout(() => {
                zoomState[view].isDragging = false;
            }, 50);
        });

        // Reset con doble clic
        wrapper.addEventListener('dblclick', () => {
            zoomState[view] = { scale: 1, panX: 0, panY: 0, isDragging: false };
            updateTransform();
        });
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

        // Dibujar Cruz (Azul cian muy visible)
        ctx.strokeStyle = "#00FFFF"; 
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 3]); // Línea punteada

        // Línea Vertical
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, overlay.height);
        ctx.stroke();

        // Línea Horizontal
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

        // Helper function to get voxel coordinates from backend (same as HU Picker)
        function getVoxelCoordinates(view, mapped, callback) {
            const slider = document.getElementById(`slider_${view}`);
            const idx = parseInt(slider.value, 10);

            fetch(`/hu_value?view=${view}&x=${mapped.xPix}&y=${mapped.yPix}&index=${idx}`)
                .then(r => r.json())
                .then(data => {
                    if (!data.error && data.voxel) {
                        // Store the scaling factors for crosshair drawing
                        if (data.scales) {
                            viewState.scales = data.scales;
                        }
                        callback(data.voxel);
                    }
                })
                .catch(err => console.error("Inspector coordinate fetch error:", err));
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

    // --- Lógica para iluminar botones de presets ---
    function highlightPreset(activeId) {
        ['presetBtnLung', 'presetBtnBone', 'presetBtnSoftTissue'].forEach(id => {
            const btn = document.getElementById(id);
            if (btn) {
                btn.classList.remove('preset-active');
                btn.classList.add('btn-outline-secondary');
            }
        });
        if (activeId) {
            const btn = document.getElementById(activeId);
            if (btn) {
                btn.classList.remove('btn-outline-secondary');
                btn.classList.add('preset-active');
            }
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

    // Inicializa los sliders de corte y carga las imágenes iniciales.

    VIEWS.forEach(view => {
        const slider = document.getElementById(`slider_${view}`);
        if (slider) {
            setupSliceSlider(view);
            setupZoomPan(view); 
            bindHU(view);
            bindInspector(view);
            updateImage(view, slider.value, true);
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
