document.addEventListener('DOMContentLoaded', function() {
    // --- ESTADO GLOBAL Y CONFIGURACIÓN ---
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

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

    // --- LÓGICA DE PLUGINS DE LA BARRA LATERAL ---
    function setupPluginButton(btnId, containerId, onToggleCallback) {
        const btn = document.getElementById(btnId);
        const container = document.getElementById(containerId);
        if (!btn || !container) return;
        btn.addEventListener('click', () => {
            const isActive = container.style.display === 'block';
            container.style.display = isActive ? 'none' : 'block';
            btn.classList.toggle('btn-udg-rojo', !isActive);
            if (onToggleCallback) onToggleCallback(!isActive);
        });
    }

    setupPluginButton('rtStructPluginBtn', 'rtStructPluginContainer');
    setupPluginButton('huPickerPluginBtn', 'huPickerPluginContainer', (isActive) => {
        document.getElementById('huToggle').click();
    });
    setupPluginButton('windowLevelBtn', 'windowLevelControls');
    setupPluginButton('contrastEditorBtn', 'contrastEditorContainer', (isActive) => {
        if (isActive && !contrastState.histogramData) {
            fetchHistogram();
        } else {
            drawCurveAndHistogram();
        }
    });

    // --- LÓGICA DE AJUSTE DE VENTANA (WW/WC) ---
    const wwSlider = document.getElementById('ww_slider');
    const wcSlider = document.getElementById('wc_slider');
    const minInput = document.getElementById('minInput');
    const maxInput = document.getElementById('maxInput');
    const levelInput = document.getElementById('levelInput');
    const windowInput = document.getElementById('windowInput');

    function updateWWWC(ww, wc, updateSource = null) {
        viewState.ww = Math.max(1, ww);
        viewState.wc = wc;
        const min = viewState.wc - viewState.ww / 2;
        const max = viewState.wc + viewState.ww / 2;
        if (updateSource !== 'sliders') {
            if(wwSlider) wwSlider.value = viewState.ww;
            if(wcSlider) wcSlider.value = viewState.wc;
        }
        if (updateSource !== 'fields') {
            if(minInput) minInput.value = Math.round(min);
            if(maxInput) maxInput.value = Math.round(max);
            if(levelInput) levelInput.value = Math.round(viewState.wc);
            if(windowInput) windowInput.value = Math.round(viewState.ww);
        }
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
    
    document.getElementById('presetBtnLung')?.addEventListener('click', () => updateWWWC(1500, -600));
    document.getElementById('presetBtnBone')?.addEventListener('click', () => updateWWWC(2500, 480));
    document.getElementById('presetBtnSoftTissue')?.addEventListener('click', () => updateWWWC(400, 40));


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
        if (!baseImage || !canvas || !baseImage.complete || baseImage.naturalWidth === 0) return;
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        canvas.width = baseImage.naturalWidth;
        canvas.height = baseImage.naturalHeight;
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
        const rect = canvasEl.getBoundingClientRect();
        const scaleX = canvasEl.width / rect.width;
        const scaleY = canvasEl.height / rect.height;
        const cssX = evt.clientX - rect.left;
        const cssY = evt.clientY - rect.top;
        if (cssX < 0 || cssY < 0 || cssX > rect.width || cssY > rect.height) return null;
        return {
            xPix: Math.floor(cssX * scaleX),
            yPix: Math.floor(cssY * scaleY),
            cssX: cssX,
            cssY: cssY,
        };
    }

    function drawMarker(view, cssX, cssY) {
        const overlay = document.getElementById(`overlay_${view}`);
        const mainCanvas = document.getElementById(`canvas_${view}`);
        if (!overlay || !mainCanvas) return;
        overlay.width = mainCanvas.clientWidth;
        overlay.height = mainCanvas.clientHeight;
        const ctx = overlay.getContext("2d");
        ctx.clearRect(0, 0, overlay.width, overlay.height);
        ctx.fillStyle = "red";
        ctx.beginPath();
        ctx.arc(cssX, cssY, 5, 0, 2 * Math.PI);
        ctx.fill();
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
        if (!mainCanvas) return;
        mainCanvas.addEventListener("click", (evt) => {
            if (!viewState.huMode) return;
            VIEWS.forEach(clearOverlay);
            const mapped = cssToPngPixels(mainCanvas, evt);
            if (!mapped) {
                huResult.textContent = "Clic fuera de la imagen.";
                return;
            }
            const slider = document.getElementById(`slider_${view}`);
            const idx = parseInt(slider.value, 10);
            fetch(`/hu_value?view=${view}&x=${mapped.xPix}&y=${mapped.yPix}&index=${idx}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        huResult.textContent = "Error: " + data.error;
                        return;
                    }
                    huResult.innerHTML = `Voxel (X, Y, Z): ${data.voxel.x}, ${data.voxel.y}, ${data.voxel.z}<br>Valor HU: ${data.hu}`;
                    drawMarker(view, mapped.cssX, mapped.cssY);
                })
                .catch(() => {
                    huResult.textContent = "Error al obtener valor HU.";
                });
        });
    }

    // --- LÓGICA DEL FORMULARIO RT STRUCT ---
    const rtStructForm = document.getElementById('rtStructForm');
  if (rtStructForm) { 
    rtStructForm.addEventListener("submit", function (event) { 
        event.preventDefault(); 
        let formData = new FormData(this); 
        const token = document.querySelector('meta[name="csrf-token"]').content;
        const loader = document.getElementById('loader-wrapper');

        // 1. Muestra la pantalla de carga
        if (loader) {
            loader.style.display = 'flex';
            loader.style.opacity = '1';
        }
        
        fetch("/upload_RT", { 
            method: "POST", 
            headers: { 'X-CSRFToken': token }, 
            body: formData 
        })
        .then(response => {
            if (!response.ok) {
                // Si el servidor responde con un error, lo mostramos
                throw new Error('Error en la respuesta del servidor al subir el archivo.');
            }
            return response.json();
        })
        .then(data => {
            console.log("Respuesta del servidor:", data.mensaje);
            // 2. NO HACEMOS NADA para recargar el iframe.
            // Confiamos en que el backend envíe la actualización a través de WebSocket.
        })
        .catch(error => {
            console.error("Error al cargar el archivo RT Struct:", error);
            alert("Hubo un error al cargar el archivo.");
        })
        .finally(() => {
            // 3. Oculta la pantalla de carga después de un momento.
            // Le damos tiempo al backend para que envíe la actualización visual.
            if (loader) {
                setTimeout(() => {
                    loader.style.opacity = '0';
                    setTimeout(() => {
                        loader.style.display = 'none';
                    }, 500);
                }, 1000); // Espera 1 segundo antes de ocultar
            }
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

    // --- INICIALIZACIÓN ---
    // Configura los spinners personalizados con sus funciones de actualización inmediata.
    setupCustomSpinner('minInput', 1, () => {
        const min = parseInt(minInput.value);
        const max = parseInt(maxInput.value);
        updateWWWC(max - min, (max + min) / 2, 'fields');
    });
    setupCustomSpinner('maxInput', 1, () => {
        const min = parseInt(minInput.value);
        const max = parseInt(maxInput.value);
        updateWWWC(max - min, (max + min) / 2, 'fields');
    });
    setupCustomSpinner('levelInput', 1, () => {
        updateWWWC(parseInt(windowInput.value), parseInt(levelInput.value), 'fields');
    });
    setupCustomSpinner('windowInput', 10, () => {
        updateWWWC(parseInt(windowInput.value), parseInt(levelInput.value), 'fields');
    });
    setupCustomSpinner('cutoffInput', 0.5, () => {
        contrastState.cutoff = parseFloat(cutoffInput.value) || 0;
        drawCurveAndHistogram();
    });
    setup3DRendererControls();

    // Inicializa los sliders de corte y carga las imágenes iniciales.

    VIEWS.forEach(view => {
        const slider = document.getElementById(`slider_${view}`);
        if (slider) {
            setupSliceSlider(view);
            bindHU(view);
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

    // --- PUNTO CLAVE 4: Usa una clase CSS en lugar de la API nativa ---
    if (element.classList.contains('fullscreen-active')) {
        element.classList.remove('fullscreen-active');
    } else {
        element.classList.add('fullscreen-active');
    }
}