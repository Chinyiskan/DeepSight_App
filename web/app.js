// ==========================================================================
// DEEPSIGHT - JETBRAINS IDE FRONTEND INTERACTIVE LOGIC
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

function initApp() {
  setupEventListeners();
  
  // Agregar 2 clases por defecto
  addClass('Clase 1');
  addClass('Clase 2');

  // Inicializar comunicación con PyWebView cuando esté listo
  window.addEventListener('pywebviewready', () => {
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.get_system_info().then(info => {
        updateHwInfo(info);
      }).catch(err => console.error("Error obteniendo info de sistema:", err));
    }
  });
}

function setupEventListeners() {
  // Botón añadir clase
  document.getElementById('btn-add-class').addEventListener('click', () => {
    addClass();
  });

  // Botón entrenar
  document.getElementById('btn-train').addEventListener('click', () => {
    startTraining();
  });

  // Botón exportar
  document.getElementById('btn-export').addEventListener('click', () => {
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.export_model();
    }
  });

  // Botón limpiar consola
  document.getElementById('btn-clear-log').addEventListener('click', () => {
    document.getElementById('terminal-output').innerHTML = '<div class="log-line info">[SYS] Consola limpiada.</div>';
  });

  // Toggle de Tema (Darcula / Light)
  document.getElementById('btn-theme-toggle').addEventListener('click', toggleTheme);

  // Dropzone de Pruebas
  setupTestDropzone();
}

// --- GESTIÓN DE TEMAS (DARCULA / NEW UI LIGHT) ---
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

    <div class="thumb-grid" id="thumb-grid-${classObj.id}"></div>

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

  // HTML5 Drag & Drop
  dropzoneEl.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzoneEl.classList.add('dragover');
  });
  dropzoneEl.addEventListener('dragleave', () => {
    dropzoneEl.classList.remove('dragover');
  });
  dropzoneEl.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzoneEl.classList.remove('dragover');
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const paths = Array.from(e.dataTransfer.files).map(f => f.path || f.name).filter(Boolean);
      if (paths.length > 0) {
        addImagesToClass(classObj.id, paths);
      }
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

  filePaths.forEach(path => {
    const cleanPath = path.trim().replace(/^[\{\}]|[\{\}]$/g, '');
    const lower = cleanPath.toLowerCase();
    if (validExts.some(ext => lower.endsWith(ext))) {
      if (!classObj.imagePaths.includes(cleanPath)) {
        classObj.imagePaths.push(cleanPath);
      }
    }
  });

  updateClassUI(classObj);
}

function updateClassUI(classObj) {
  const countBadge = document.getElementById(`count-badge-${classObj.id}`);
  const thumbGrid = document.getElementById(`thumb-grid-${classObj.id}`);
  const count = classObj.imagePaths.length;

  if (count < 5) {
    countBadge.textContent = `${count} imágenes (⚠️ Mín 5)`;
    countBadge.className = 'count-badge warning';
  } else {
    countBadge.textContent = `${count} imágenes ✔️`;
    countBadge.className = 'count-badge valid';
  }

  // Renderizar minigrid de thumbnails
  thumbGrid.innerHTML = '';
  classObj.imagePaths.slice(0, 12).forEach((path, idx) => {
    const item = document.createElement('div');
    item.className = 'thumb-item';

    const img = document.createElement('img');
    img.alt = 'preview';

    const removeBtn = document.createElement('span');
    removeBtn.className = 'thumb-remove';
    removeBtn.textContent = '×';
    removeBtn.onclick = () => removeImageFromClass(classObj.id, idx);

    item.appendChild(img);
    item.appendChild(removeBtn);
    thumbGrid.appendChild(item);

    // Solicitar base64 data URL a la API de Python para evitar restricciones de protocolo file://
    if (window.pywebview && window.pywebview.api && window.pywebview.api.get_thumbnail) {
      window.pywebview.api.get_thumbnail(path).then(dataUrl => {
        if (dataUrl) {
          img.src = dataUrl;
        }
      }).catch(err => console.error("Error cargando miniatura:", err));
    }
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

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });
  dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('dragover');
  });
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    
    if (!appState.inferenceReady) {
      alert("Primero debes entrenar un modelo para poder probarlo.");
      return;
    }

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const path = e.dataTransfer.files[0].path || e.dataTransfer.files[0].name;
      if (path) processTestImage(path);
    }
  });
}

function processTestImage(filePath) {
  const cleanPath = filePath.trim().replace(/^[\{\}]|[\{\}]$/g, '');
  const previewContainer = document.getElementById('test-preview-container');
  const previewImg = document.getElementById('test-img-preview');

  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_preview) {
    window.pywebview.api.get_preview(cleanPath).then(dataUrl => {
      if (dataUrl) {
        previewImg.src = dataUrl;
      }
    }).catch(err => console.error("Error cargando vista previa de prueba:", err));
  }

  previewContainer.classList.remove('hidden');

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

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
