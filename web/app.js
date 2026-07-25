// ==========================================================================
// DEEPSIGHT - JETBRAINS IDE FRONTEND INTERACTIVE LOGIC
// Drag & Drop 100% Robusto para WebView2 (sin pérdida de archivos)
// ==========================================================================

let appState = {
  classes: [],
  classCounter: 0,
  isTraining: false,
  trainedModelPath: null,
  inferenceReady: false
};

document.addEventListener('DOMContentLoaded', () => {
  initApp();
});

// ==========================================================================
// HELPERS: Lectura de archivos SIN dependencia de e.dataTransfer después de await
// ==========================================================================

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    try {
      const reader = new FileReader();
      reader.onload = () => resolve({
        b64_data: reader.result,
        filename: file.name || 'image.jpg',
        size: file.size
      });
      reader.onerror = () => {
        console.warn('FileReader error para archivo:', file.name);
        resolve(null);
      };
      reader.readAsDataURL(file);
    } catch (err) {
      console.warn('Excepción en fileToDataUrl:', err);
      resolve(null);
    }
  });
}

/**
 * Extrae TODOS los File objects del evento drop ANTES de cualquier await.
 * WebView2 invalida parcialmente e.dataTransfer después de la primera espera,
 * así que copiamos todo a un arreglo JavaScript de inmediato.
 */
function extractAllFilesFromDropEvent(e) {
  const files = [];

  // 1) Intentar desde e.dataTransfer.files (API clásica)
  try {
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      for (let i = 0; i < e.dataTransfer.files.length; i++) {
        const f = e.dataTransfer.files[i];
        if (f && f.type && f.type.startsWith('image/')) {
          files.push({ file: f, path: f.path || null });
        } else if (f && /\.(png|jpe?g|webp)$/i.test(f.name || '')) {
          files.push({ file: f, path: f.path || null });
        }
      }
    }
  } catch (err) {
    console.warn('Error leyendo e.dataTransfer.files:', err);
  }

  // 2) Intentar desde e.dataTransfer.items (API moderna, más fiable en WebView2)
  try {
    if (e.dataTransfer && e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      for (let i = 0; i < e.dataTransfer.items.length; i++) {
        const item = e.dataTransfer.items[i];
        if (!item) continue;
        // Tipo File
        if (item.kind === 'file') {
          const f = item.getAsFile ? item.getAsFile() : null;
          if (f) {
            const isImage = (f.type && f.type.startsWith('image/')) ||
                            /\.(png|jpe?g|webp)$/i.test(f.name || '');
            if (isImage) {
              // Evitar duplicados del paso 1
              const already = files.some(x =>
                x.file && x.file.name === f.name && x.file.size === f.size
              );
              if (!already) {
                files.push({ file: f, path: f.path || null });
              }
            }
          }
        }
      }
    }
  } catch (err) {
    console.warn('Error leyendo e.dataTransfer.items:', err);
  }

  return files;
}

/**
 * Procesa archivos arrastrados y soltados.
 * PASO IMPORTANTE: Primero extrae TODOS los File del evento (síncrono),
 * luego lee TODOS a DataUrl en paralelo (Promise.all),
 * y finalmente hace UNA SOLA LLAMADA BATCH a Python.
 * Así evitamos que e.dataTransfer se invalide entre awaits.
 */
async function processDroppedFiles(e) {
  let directPaths = [];
  const filesToConvert = [];

  // --- PASO 1: Extraer todos los File SIN await ---
  const allFiles = extractAllFilesFromDropEvent(e);
  console.log(`[Drop] Detectados ${allFiles.length} archivos vía HTML5 API`);

  for (const entry of allFiles) {
    const filePath = entry.path;
    // Si WebView2 nos dio la ruta absoluta directamente (configuración de confianza total)
    if (filePath && (filePath.includes('/') || filePath.includes('\\') || filePath.includes(':'))) {
      directPaths.push(filePath);
    } else {
      filesToConvert.push(entry.file);
    }
  }

  // --- PASO 2: Fallback text/uri-list (arrastrar desde navegador externo) ---
  if (directPaths.length === 0 && e.dataTransfer) {
    try {
      const rawData = e.dataTransfer.getData('text/uri-list') ||
                      e.dataTransfer.getData('text/plain') ||
                      e.dataTransfer.getData('URL');
      if (rawData) {
        const lines = rawData.split(/[\r\n]+/);
        for (let line of lines) {
          line = line.trim();
          if (!line) continue;
          if (line.startsWith('file:///')) {
            const p = decodeURIComponent(line.substring(8));
            if (p) directPaths.push(p);
          } else if (line.startsWith('file://')) {
            const p = decodeURIComponent(line.substring(7));
            if (p) directPaths.push(p);
          } else if (line.match(/^[a-zA-Z]:[\\/]/)) {
            directPaths.push(line);
          }
        }
      }
    } catch (err) {
      console.warn('Error en fallback text/uri-list:', err);
    }
  }

  // --- PASO 3: Convertir los archivos sin ruta a Base64 en PARALELO (Promise.all) ---
  if (filesToConvert.length > 0 && window.pywebview && window.pywebview.api) {
    try {
      // Leer TODOS a Base64 en paralelo (solo trabajo en JS, sin IPC aún)
      const conversionPromises = filesToConvert.map(f => fileToDataUrl(f));
      const convertedItems = await Promise.all(conversionPromises);
      const validItems = convertedItems.filter(x => x !== null);

      console.log(`[Drop] Convertidos ${validItems.length}/${filesToConvert.length} archivos a Base64`);

      // Si hay API BATCH disponible, usarla (1 sola llamada IPC para todos)
      if (validItems.length > 0 && window.pywebview.api.save_dropped_images_batch) {
        try {
          const batchResults = await window.pywebview.api.save_dropped_images_batch(validItems);
          if (batchResults && Array.isArray(batchResults)) {
            for (const r of batchResults) {
              if (r) directPaths.push(r);
            }
          }
        } catch (batchErr) {
          console.error('[Drop] Error en API batch, fallback a llamadas individuales:', batchErr);
          // Fallback secuencial por si el lote falla
          for (const it of validItems) {
            try {
              const absPath = await window.pywebview.api.save_dropped_image(it.b64_data, it.filename);
              if (absPath) directPaths.push(absPath);
            } catch (indErr) {
              console.error('[Drop] Error guardando archivo individual:', indErr);
            }
          }
        }
      } else if (validItems.length > 0 && window.pywebview.api.save_dropped_image) {
        // API individual como último recurso
        for (const it of validItems) {
          try {
            const absPath = await window.pywebview.api.save_dropped_image(it.b64_data, it.filename);
            if (absPath) directPaths.push(absPath);
          } catch (indErr) {
            console.error('[Drop] Error guardando archivo individual:', indErr);
          }
        }
      }
    } catch (convErr) {
      console.error('[Drop] Error en proceso de conversión:', convErr);
    }
  }

  return directPaths;
}

// ==========================================================================
// INICIALIZACIÓN
// ==========================================================================

function initApp() {
  // CRÍTICO: Cancelar comportamiento por defecto de drag/drop en TODO el documento
  // Sin esto, WebView2 a veces captura el drop y navega hacia el archivo (pérdida total)
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    document.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
    }, false);
  });
  window.addEventListener('dragover', (e) => e.preventDefault(), false);
  window.addEventListener('drop', (e) => e.preventDefault(), false);

  setupEventListeners();

  // Agregar 2 clases por defecto
  addClass('Clase 1');
  addClass('Clase 2');

  const splashProgressBar = document.getElementById('splash-progress-bar');
  if (splashProgressBar) splashProgressBar.style.width = '35%';

  const hideSplash = () => {
    const splash = document.getElementById('splash-screen');
    if (splash && !splash.classList.contains('fade-out')) {
      splash.classList.add('fade-out');
    }
  };

  let hwChecked = false;

  const fetchHw = () => {
    if (hwChecked) return;
    if (window.pywebview && window.pywebview.api && window.pywebview.api.get_system_info) {
      hwChecked = true;
      if (splashProgressBar) splashProgressBar.style.width = '70%';
      window.pywebview.api.get_system_info().then(info => {
        if (splashProgressBar) splashProgressBar.style.width = '100%';
        updateHwInfo(info);
        setTimeout(hideSplash, 600);
      }).catch(err => {
        console.error("Error obteniendo info de sistema:", err);
        hideSplash();
      });
    } else {
      setTimeout(fetchHw, 200);
    }
  };

  window.addEventListener('pywebviewready', fetchHw);
  setTimeout(fetchHw, 500);
  setTimeout(hideSplash, 15000);
}

function setupEventListeners() {
  document.getElementById('btn-add-class').addEventListener('click', () => {
    addClass();
  });

  document.getElementById('btn-train').addEventListener('click', () => {
    startTraining();
  });

  document.getElementById('btn-export').addEventListener('click', () => {
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.export_model();
    }
  });

  document.getElementById('btn-clear-log').addEventListener('click', () => {
    document.getElementById('terminal-output').innerHTML = '<div class="log-line info">[SYS] Consola limpiada.</div>';
  });

  document.getElementById('btn-theme-toggle').addEventListener('click', toggleTheme);

  setupTestDropzone();
}

// --- GESTIÓN DE TEMAS ---
function toggleTheme() {
  const body = document.body;
  const isDark = body.classList.contains('theme-dark');
  const sunIcon = document.getElementById('theme-icon-sun');
  const moonIcon = document.getElementById('theme-icon-moon');
  const themeLabel = document.getElementById('theme-label');

  if (isDark) {
    body.classList.remove('theme-dark');
    body.classList.add('theme-light');
    sunIcon.classList.add('hidden');
    moonIcon.classList.remove('hidden');
    themeLabel.textContent = 'Light UI';
  } else {
    body.classList.remove('theme-light');
    body.classList.add('theme-dark');
    moonIcon.classList.add('hidden');
    sunIcon.classList.remove('hidden');
    themeLabel.textContent = 'Darcula';
  }
}

// --- GESTIÓN DE HARDWARE Y AVISO DE ADMIN ---
function updateHwInfo(info) {
  const textEl = document.getElementById('hw-info-text');
  const adminBanner = document.getElementById('admin-warning-banner');

  if (info) {
    textEl.textContent = `${info.device.toUpperCase()} | CPU: ${info.cpus} Cores | RAM: ~${info.ram_gb.toFixed(1)}GB`;
    if (info.is_admin) {
      adminBanner.classList.remove('hidden');
    }
  }
}

// --- CLASES Y TARJETAS DINÁMICAS ---
function addClass(defaultName = null) {
  appState.classCounter++;
  const cid = appState.classCounter;
  const name = defaultName ? defaultName : `Clase ${cid}`;

  const classObj = {
    id: cid,
    name: name,
    imagePaths: []
  };
  appState.classes.push(classObj);

  renderClassCard(classObj);
}

function renderClassCard(classObj) {
  const container = document.getElementById('classes-container');
  const card = document.createElement('div');
  card.className = 'class-card';
  card.id = `class-card-${classObj.id}`;

  card.innerHTML = `
    <div class="card-header">
      <input type="text" class="card-title-input" id="class-title-${classObj.id}" value="${escapeHtml(classObj.name)}">
      <button class="btn-delete-class" title="Eliminar clase" onclick="deleteClass(${classObj.id})">×</button>
    </div>
    
    <div class="dropzone" id="dropzone-${classObj.id}">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
        <polyline points="17 8 12 3 7 8"></polyline>
        <line x1="12" y1="3" x2="12" y2="15"></line>
      </svg>
      <div class="dropzone-text">Arrastra imágenes aquí</div>
      <div class="dropzone-subtext">o haz clic para explorar</div>
    </div>

    <div class="file-list" id="file-list-${classObj.id}"></div>

    <div class="card-footer-info">
      <span class="count-badge warning" id="count-badge-${classObj.id}">0 imágenes (⚠️ Mín 5)</span>
    </div>
  `;

  container.appendChild(card);

  // Vincular cambio de nombre
  const inputEl = document.getElementById(`class-title-${classObj.id}`);
  inputEl.addEventListener('input', (e) => {
    classObj.name = e.target.value.trim();
  });

  // Vincular eventos de Dropzone
  const dropzoneEl = document.getElementById(`dropzone-${classObj.id}`);

  // Click para examinar archivos con ventana nativa
  dropzoneEl.addEventListener('click', () => {
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.select_files().then(files => {
        if (files && files.length > 0) {
          addImagesToClass(classObj.id, files);
        }
      });
    }
  });

  // HTML5 Drag & Drop - cancelar siempre por defecto y marcar zona activa
  dropzoneEl.addEventListener('dragenter', (e) => {
    e.preventDefault();
    e.stopPropagation();
    window.lastActiveDropzone = { type: 'class', id: classObj.id };
    dropzoneEl.classList.add('dragover');
  });
  dropzoneEl.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = 'copy'; // Indicar que es copia (ayuda a WebView2)
    window.lastActiveDropzone = { type: 'class', id: classObj.id };
    dropzoneEl.classList.add('dragover');
    return false;
  });
  dropzoneEl.addEventListener('dragleave', (e) => {
    // Solo quitar dragover si realmente abandonamos la zona
    const rect = dropzoneEl.getBoundingClientRect();
    const x = e.clientX;
    const y = e.clientY;
    if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
      dropzoneEl.classList.remove('dragover');
    }
  });
  dropzoneEl.addEventListener('drop', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropzoneEl.classList.remove('dragover');

    // Feedback visual inmediato
    const textEl = dropzoneEl.querySelector('.dropzone-text');
    const originalText = textEl ? textEl.textContent : null;
    const subtextEl = dropzoneEl.querySelector('.dropzone-subtext');
    const originalSubtext = subtextEl ? subtextEl.textContent : null;

    if (textEl) textEl.textContent = 'Procesando archivos...';
    if (subtextEl) subtextEl.textContent = 'Por favor espera';

    try {
      const paths = await processDroppedFiles(e);
      console.log(`[Drop Clase ${classObj.id}] Rutas finales recibidas: ${paths.length}`);

      if (paths && paths.length > 0) {
        addImagesToClass(classObj.id, paths);
      } else if (window.pywebview && window.pywebview.api) {
        // Fallback: si no se pudo extraer ninguna ruta, abrir diálogo nativo
        console.warn('[Drop] No se obtuvieron rutas, abriendo diálogo nativo como fallback');
        window.pywebview.api.select_files().then(files => {
          if (files && files.length > 0) {
            addImagesToClass(classObj.id, files);
          }
        });
      }
    } catch (dropErr) {
      console.error('[Drop] Error crítico en handler de drop:', dropErr);
      appendLog(`[WARN] Error procesando archivos arrastrados: ${dropErr.message}`, 'info');
    } finally {
      if (textEl && originalText) textEl.textContent = originalText;
      if (subtextEl && originalSubtext) subtextEl.textContent = originalSubtext;
    }
  });
}

function deleteClass(cid) {
  if (appState.classes.length <= 2) {
    alert("Debes mantener al menos 2 clases para poder entrenar.");
    return;
  }

  appState.classes = appState.classes.filter(c => c.id !== cid);
  const card = document.getElementById(`class-card-${cid}`);
  if (card) card.remove();
}

function addImagesToClass(cid, filePaths) {
  const classObj = appState.classes.find(c => c.id === cid);
  if (!classObj) return;

  const validExts = ['.png', '.jpg', '.jpeg', '.webp'];
  let added = 0;
  let skipped = 0;

  filePaths.forEach(path => {
    if (!path) { skipped++; return; }
    const cleanPath = String(path).trim().replace(/^[\{\}]|[\{\}]$/g, '');

    const lower = cleanPath.toLowerCase();
    if (validExts.some(ext => lower.endsWith(ext))) {
      if (!classObj.imagePaths.includes(cleanPath)) {
        classObj.imagePaths.push(cleanPath);
        added++;
      } else {
        skipped++;
      }
    } else {
      skipped++;
    }
  });

  if (added > 0 || skipped > 0) {
    console.log(`[Clase ${classObj.id}] Añadidas: ${added}, Ignoradas: ${skipped}`);
  }

  updateClassUI(classObj);
}

function updateClassUI(classObj) {
  const countBadge = document.getElementById(`count-badge-${classObj.id}`);
  const fileList = document.getElementById(`file-list-${classObj.id}`);
  const count = classObj.imagePaths.length;

  if (count < 5) {
    countBadge.textContent = `${count} imágenes (⚠️ Mín 5)`;
    countBadge.className = 'count-badge warning';
  } else {
    countBadge.textContent = `${count} imágenes ✔️`;
    countBadge.className = 'count-badge valid';
  }

  // Renderizar lista limpia de archivos
  fileList.innerHTML = '';
  classObj.imagePaths.forEach((path, idx) => {
    const item = document.createElement('div');
    item.className = 'file-item';

    const fileName = path.split(/[\\/]/).pop();

    item.innerHTML = `
      <div class="file-item-main" title="${escapeHtml(path)}">
        <svg class="file-item-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
          <circle cx="8.5" cy="8.5" r="1.5"></circle>
          <polyline points="21 15 16 10 5 21"></polyline>
        </svg>
        <span class="file-item-name">${escapeHtml(fileName)}</span>
      </div>
      <button class="file-item-remove" title="Eliminar archivo" onclick="removeImageFromClass(${classObj.id}, ${idx})">×</button>
    `;

    fileList.appendChild(item);
  });
}

function removeImageFromClass(cid, index) {
  const classObj = appState.classes.find(c => c.id === cid);
  if (!classObj) return;

  classObj.imagePaths.splice(index, 1);
  updateClassUI(classObj);
}

// --- ENTRENAMIENTO ---
function startTraining() {
  if (appState.isTraining) return;

  const payload = {};
  for (let c of appState.classes) {
    const name = c.name.trim();
    if (!name) {
      alert("Todas las clases deben tener un nombre.");
      return;
    }
    if (c.imagePaths.length < 5) {
      alert(`La clase "${name}" tiene menos de 5 imágenes.`);
      return;
    }
    if (payload[name]) {
      alert("No puedes tener clases con nombres duplicados.");
      return;
    }
    payload[name] = c.imagePaths;
  }

  if (Object.keys(payload).length < 2) {
    alert("Necesitas al menos 2 clases válidas.");
    return;
  }

  appState.isTraining = true;
  document.getElementById('btn-train').disabled = true;
  document.getElementById('btn-add-class').disabled = true;
  document.getElementById('btn-export').disabled = true;
  document.getElementById('train-mode-text').textContent = 'Entrenando modelo...';

  appendLog('[SYS] Iniciando proceso de entrenamiento...', 'info');

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.start_training(payload);
  } else {
    appendLog('[ERR] PyWebView API no disponible.', 'error');
  }
}

function appendLog(text, type = 'info') {
  const terminal = document.getElementById('terminal-output');
  const line = document.createElement('div');
  line.className = `log-line ${type}`;
  line.textContent = text;
  terminal.appendChild(line);
  terminal.scrollTop = terminal.scrollHeight;
}

function onTrainingFinished(bestPtPath, success) {
  appState.isTraining = false;
  document.getElementById('btn-train').disabled = false;
  document.getElementById('btn-add-class').disabled = false;

  if (success && bestPtPath) {
    appState.trainedModelPath = bestPtPath;
    appState.inferenceReady = true;
    document.getElementById('btn-export').disabled = false;
    document.getElementById('train-mode-text').textContent = 'Modelo entrenado y listo para probar';
    appendLog('[SUCCESS] ✅ Entrenamiento finalizado con éxito. Modelo cargado para pruebas.', 'success');
  } else {
    document.getElementById('train-mode-text').textContent = 'Falló el entrenamiento';
    appendLog('[ERROR] ❌ Ocurrió un error en el entrenamiento.', 'error');
  }
}

// --- PRUEBA E INFERENCIA ---
function setupTestDropzone() {
  const dropzone = document.getElementById('test-dropzone');

  dropzone.addEventListener('click', () => {
    if (!appState.inferenceReady) {
      alert("Primero debes entrenar un modelo para poder probarlo.");
      return;
    }
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.select_files().then(files => {
        if (files && files.length > 0) {
          processTestImage(files[0]);
        }
      });
    }
  });

  dropzone.addEventListener('dragenter', (e) => {
    e.preventDefault();
    e.stopPropagation();
    window.lastActiveDropzone = { type: 'test' };
    dropzone.classList.add('dragover');
  });
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = 'copy';
    window.lastActiveDropzone = { type: 'test' };
    dropzone.classList.add('dragover');
    return false;
  });
  dropzone.addEventListener('dragleave', (e) => {
    const rect = dropzone.getBoundingClientRect();
    const x = e.clientX;
    const y = e.clientY;
    if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
      dropzone.classList.remove('dragover');
    }
  });
  dropzone.addEventListener('drop', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.remove('dragover');

    if (!appState.inferenceReady) {
      alert("Primero debes entrenar un modelo para poder probarlo.");
      return;
    }

    try {
      const paths = await processDroppedFiles(e);
      if (paths && paths.length > 0) {
        processTestImage(paths[0]);
      } else if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.select_files().then(files => {
          if (files && files.length > 0) {
            processTestImage(files[0]);
          }
        });
      }
    } catch (dropErr) {
      console.error('[Drop Test] Error:', dropErr);
    }
  });
}

function processTestImage(filePath) {
  const cleanPath = filePath.trim().replace(/^[\{\}]|[\{\}]$/g, '');
  const fileName = cleanPath.split(/[\\/]/).pop();
  const testFileBadge = document.getElementById('test-file-badge');
  const testFileNameEl = document.getElementById('test-file-name');

  if (testFileNameEl) testFileNameEl.textContent = fileName;
  if (testFileBadge) testFileBadge.classList.remove('hidden');

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.predict(cleanPath);
  }
}

function onPredictionResult(className, confidence) {
  document.getElementById('res-class-name').textContent = className;
  document.getElementById('res-confidence-text').textContent = `${confidence.toFixed(1)}%`;
  document.getElementById('confidence-bar-fill').style.width = `${confidence}%`;
}

// Escuchadores globales expuestos para Python
window.appendLog = appendLog;
window.onTrainingFinished = onTrainingFinished;
window.onPredictionResult = onPredictionResult;
window.deleteClass = deleteClass;
window.removeImageFromClass = removeImageFromClass;

function escapeHtml(str) {
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
