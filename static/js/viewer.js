// Se asegura de que todo el código se ejecute solo después de que la página HTML se haya cargado por completo.
document.addEventListener('DOMContentLoaded', function() {

  // --- ESTADO Y FUNCIONES AUXILIARES ---
  let isRtStructLoaded = false; // Rastrea si un RT Struct ha sido cargado en la sesión
  const loader = document.getElementById('loader-wrapper');

  // Muestra la pantalla de carga con una transición suave
  function showLoader() {
    if (loader) {
      loader.style.display = 'flex';
      setTimeout(() => { loader.style.opacity = '1'; }, 10);
    }
  }

  // Oculta la pantalla de carga con una transición suave
  function hideLoader() {
    if (loader) {
      loader.style.opacity = '0';
      setTimeout(() => { loader.style.display = 'none'; }, 500);
    }
  }

  // --- INICIALIZACIÓN DE TOOLTIPS ---
  // Activa las descripciones emergentes de Bootstrap en los botones que las tengan.
  const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

  // --- LÓGICA DE PLUGINS ---
  // Función genérica para manejar el estado y estilo de los botones de los plugins.
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

  // --- LÓGICA DE HU PICKER ---
  const huInfo = document.getElementById("huInfo");
  const huResult = document.getElementById("huResult");
  let huMode = false;
  const dpr = window.devicePixelRatio || 1;
  const huToggle_hiddenButton = document.getElementById('huToggle');
  
  function syncCanvasToImage(imgEl, canvasEl) { const rect = imgEl.getBoundingClientRect(); canvasEl.width = Math.max(1, Math.round(rect.width * dpr)); canvasEl.height = Math.max(1, Math.round(rect.height * dpr)); const ctx = canvasEl.getContext("2d"); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.scale(dpr, dpr); ctx.clearRect(0, 0, canvasEl.width, canvasEl.height); return ctx; }
  function drawMarker(ctx, xCss, yCss) { ctx.fillStyle = "red"; ctx.beginPath(); ctx.arc(xCss, yCss, 5 / dpr, 0, 2 * Math.PI); ctx.fill(); }
  function cssToPngPixels(imgEl, evt) { const rect = imgEl.getBoundingClientRect(); const nW = imgEl.naturalWidth; const nH = imgEl.naturalHeight; const dispW = rect.width; const dispH = rect.height; const scaleX = nW / dispW; const scaleY = nH / dispH; const xCss = evt.clientX - rect.left; const yCss = evt.clientY - rect.top; if (xCss < 0 || yCss < 0 || xCss > dispW || yCss > dispH) return null; return { xPix: Math.floor(xCss * scaleX), yPix: Math.floor(yCss * scaleY), xCss, yCss }; }
  function bindHU(view) { const img = document.getElementById(`image_${view}`); const canvas = document.getElementById(`overlay_${view}`); if (!img || !canvas) return; let ctx = null; function resetCanvas() { ctx = syncCanvasToImage(img, canvas); } img.addEventListener("load", resetCanvas); new ResizeObserver(resetCanvas).observe(img); img.addEventListener("click", (evt) => { if (!huMode) return; resetCanvas(); const mapped = cssToPngPixels(img, evt); if (!mapped) { huResult.textContent = "Click fuera de la imagen."; return; } const slider = document.getElementById(`slider_${view}`); const idx = parseInt(slider.value, 10); fetch(`/hu_value?view=${view}&x=${mapped.xPix}&y=${mapped.yPix}&index=${idx}`).then(r => r.json()).then(data => { if (data.error) { huResult.textContent = "Error: " + data.error; return; } huResult.innerHTML = `Voxel (X,Y,Z): ${data.voxel.x},${data.voxel.y},${data.voxel.z}<br>Valor HU: ${data.hu}`; drawMarker(ctx, mapped.xCss, mapped.yCss); }).catch(() => { huResult.textContent = "Error al obtener valor HU."; }); }); }
  if (huToggle_hiddenButton) { huToggle_hiddenButton.addEventListener("click", () => { huMode = !huMode; if(huInfo) huInfo.textContent = huMode ? "Haz click en una imagen para obtener el valor HU." : ""; if (!huMode) { ["axial", "sagital", "coronal"].forEach(v => { const img = document.getElementById(`image_${v}`); if(img) { const canvas = document.getElementById(`overlay_${v}`); syncCanvasToImage(img, canvas); } }); } }); }

  // --- LÓGICA DE AJUSTE DE VENTANA (WW/WC) ---
  const viewState = { ww: 400, wc: 40 };
  const wwSlider = document.getElementById('ww_slider');
  const wcSlider = document.getElementById('wc_slider');
  const wwValueSpan = document.getElementById('ww_value');
  const wcValueSpan = document.getElementById('wc_value');
  function applyPreset(ww, wc) {
    viewState.ww = ww; viewState.wc = wc;
    if (wwSlider) wwSlider.value = ww; if (wcSlider) wcSlider.value = wc;
    if (wwValueSpan) wwValueSpan.textContent = ww; if (wcValueSpan) wcValueSpan.textContent = wc;
    updateAllViews();
  }
  if (wwSlider) { wwSlider.addEventListener('input', () => { applyPreset(parseInt(wwSlider.value, 10), viewState.wc); }); }
  if (wcSlider) { wcSlider.addEventListener('input', () => { applyPreset(viewState.ww, parseInt(wcSlider.value, 10)); }); }
  
  const presetBtnLung = document.getElementById('presetBtnLung');
  const presetBtnBone = document.getElementById('presetBtnBone');
  const presetBtnSoftTissue = document.getElementById('presetBtnSoftTissue');
  if(presetBtnLung) presetBtnLung.addEventListener('click', () => applyPreset(1500, -600));
  if(presetBtnBone) presetBtnBone.addEventListener('click', () => applyPreset(2500, 480));
  if(presetBtnSoftTissue) presetBtnSoftTissue.addEventListener('click', () => applyPreset(400, 40));

  // --- LÓGICA CENTRAL DE ACTUALIZACIÓN DE IMÁGENES ---
  function updateAllViews() { ["axial", "sagital", "coronal"].forEach(view => { const slider = document.getElementById(`slider_${view}`); if (slider) updateImage(view, slider.value); }); }
  function updateImage(view, layer) { const image = document.getElementById(`image_${view}`); if (!image) return; const { ww, wc } = viewState; image.src = `/image/${view}/${layer}?ww=${ww}&wc=${wc}&t=${new Date().getTime()}`; }
  
  // --- LÓGICA DE SLIDERS DE PROFUNDIDAD ---
  function setupSliceSlider(view) { const slider = document.getElementById(`slider_${view}`); const number = document.getElementById(`number_${view}`); if (!slider || !number) return; slider.addEventListener('input', () => { number.value = slider.value; updateImage(view, slider.value); }); number.addEventListener('input', () => { let val = Number(number.value); const max = parseInt(slider.max, 10); const min = parseInt(slider.min, 10); if (val < min) val = min; if (val > max) val = max; slider.value = val; updateImage(view, val); }); }
  
  // --- LÓGICA DEL FORMULARIO RT STRUCT ---
  const rtStructForm = document.getElementById('rtStructForm');
  if (rtStructForm) {
    rtStructForm.addEventListener("submit", function (event) {
      event.preventDefault();
      let formData = new FormData(this);
      const token = document.querySelector('meta[name="csrf-token"]').content;
      const submitButton = this.querySelector('button[type="submit"]');
      const dicomRenderFrame = document.getElementById('DicomRender');

      showLoader();
      submitButton.innerHTML = '<i class="bi bi-hourglass-split"></i> Cargando...';
      submitButton.disabled = true;

      fetch("/upload_RT", { method: "POST", headers: { 'X-CSRFToken': token }, body: formData })
      .then(response => {
        if (response.ok) {
          isRtStructLoaded = true;
          if (dicomRenderFrame) {
            dicomRenderFrame.addEventListener('load', hideLoader, { once: true });
            dicomRenderFrame.src = dicomRenderFrame.src;
          } else {
            hideLoader();
          }
        } else {
          alert('Hubo un error al cargar el archivo.');
          hideLoader();
        }
      })
      .finally(() => {
          submitButton.innerHTML = '<i class="bi bi-upload"></i> Subir';
          submitButton.disabled = false;
      });
    });
  }

  // --- INICIALIZACIÓN DE PLUGINS Y FUNCIONALIDADES ---
  setupPluginButton('rtStructPluginBtn', 'rtStructPluginContainer', (isActive) => {
    if (isRtStructLoaded) {
      showLoader();
      const token = document.querySelector('meta[name="csrf-token"]').content;
      const dicomRenderFrame = document.getElementById('DicomRender');
      fetch('/toggle_rt_visibility', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
        body: JSON.stringify({ visible: isActive })
      }).then(() => {
        if (dicomRenderFrame) {
          dicomRenderFrame.addEventListener('load', hideLoader, { once: true });
          dicomRenderFrame.src = dicomRenderFrame.src;
        } else {
          hideLoader();
        }
      });
    }
  });
  setupPluginButton('huPickerPluginBtn', 'huPickerPluginContainer', () => { if (huToggle_hiddenButton) huToggle_hiddenButton.click(); });
  setupPluginButton('windowLevelBtn', 'windowLevelControls');
  
  // Inicialización de los sliders de profundidad y el selector HU para cada vista
  setupSliceSlider('axial');
  setupSliceSlider('sagital');
  setupSliceSlider('coronal');
  bindHU('axial');
  bindHU('sagital');
  bindHU('coronal');
});

// --- FUNCIONES GLOBALES (necesitan estar fuera para ser accesibles por 'onclick') ---
function toggleFullscreen(id) {
  const element = document.getElementById(id);
  if (!document.fullscreenElement) {
    element.requestFullscreen().catch(err => {
      alert(`Error: ${err.message}`);
    });
  } else {
    document.exitFullscreen();
  }
}