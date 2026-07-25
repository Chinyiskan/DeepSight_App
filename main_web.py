import os
import sys
import shutil
import ctypes
import multiprocessing
import urllib.parse
import uuid
import time
import threading
import webview
from ultralytics import YOLO

import base64
from trainer import DeepSightTrainer, get_ram_gb

# ------------------------------------------------------------------------------
# MUY CRÍTICO: freeze_support() DEBE ejecutarse LO ANTES POSIBLE a nivel módulo
# (antes de cualquier otro código) para que multiprocessing en modo "spawn"
# (Windows/macOS) funcione correctamente en builds congelados (PyInstaller, etc).
# Si va DENTRO de main(), los procesos hijo NO lo ejecutan a tiempo y crashean.
# ------------------------------------------------------------------------------
multiprocessing.freeze_support()


def _resolve_web_base_dir():
    """
    Resuelve de forma ROBUSTA el directorio donde está la carpeta 'web'
    (index.html, app.js, styles.css). Encadena múltiples estrategias de fallback
    para ser compatible con PyInstaller (onefile + onedir), cx_Freeze, Nuitka,
    ejecución directa desde fuente, y casos borde.

    NUNCA lanza una excepción: retorna la ruta o None.
    """
    candidates = []

    try:
        # 1) PyInstaller oficial: atributo sys._MEIPASS. Debe EXISTIR el atributo Y ser no-None/no-vacío.
        if hasattr(sys, "_MEIPASS"):
            mp = getattr(sys, "_MEIPASS", None)
            if mp:
                candidates.append(os.path.join(str(mp), "web"))
    except Exception:
        pass

    try:
        # 2) Builds alternativos (cx_Freeze, Nuitka, PyInstaller onedir):
        #    la carpeta web está junto al ejecutable.
        exe = getattr(sys, "executable", None) or ""
        if exe:
            exe_abs = os.path.abspath(str(exe))
            exe_dir = os.path.dirname(exe_abs)
            if exe_dir:
                candidates.append(os.path.join(exe_dir, "web"))
    except Exception:
        pass

    try:
        # 3) Ejecución desde fuente (python main_web.py): usar __file__
        if "__file__" in globals() or "__file__" in dir():
            this_file = globals().get("__file__")
            if this_file:
                file_abs = os.path.abspath(str(this_file))
                file_dir = os.path.dirname(file_abs)
                if file_dir:
                    candidates.append(os.path.join(file_dir, "web"))
    except (NameError, AttributeError, OSError, TypeError):
        pass

    try:
        # 4) CWD como último recurso (debug / launcher)
        cwd = os.getcwd()
        if cwd:
            candidates.append(os.path.join(cwd, "web"))
    except Exception:
        pass

    # Evaluar cada candidato (también protegido)
    for path in candidates:
        try:
            if not path:
                continue
            idx_candidate = os.path.join(str(path), "index.html")
            if os.path.isdir(str(path)) and os.path.isfile(str(idx_candidate)):
                return str(path)
        except (OSError, TypeError, ValueError):
            continue

    return None  # Ningún candidato funcionó, error manejable arriba


def _list_web_base_dir_candidates():
    """
    Retorna una LISTA DE STRINGS con las rutas que se buscaron (para mensajes de error).
    IGUAL que _resolve_web_base_dir pero NO evalúa si existen.
    NUNCA lanza excepción.
    """
    tried = []
    try:
        if hasattr(sys, "_MEIPASS"):
            mp = getattr(sys, "_MEIPASS", None)
            if mp:
                tried.append(os.path.join(str(mp), "web"))
            else:
                tried.append("<sys._MEIPASS estaba vacío/None>")
    except Exception:
        pass
    try:
        exe = getattr(sys, "executable", None) or ""
        if exe:
            tried.append(os.path.join(os.path.dirname(os.path.abspath(str(exe))), "web"))
        else:
            tried.append("<sys.executable estaba vacío/None>")
    except Exception:
        tried.append("<sys.executable lanzó error>")
    try:
        this_file = globals().get("__file__")
        if this_file:
            tried.append(os.path.join(os.path.dirname(os.path.abspath(str(this_file))), "web"))
        else:
            tried.append("<__file__ no disponible>")
    except Exception:
        tried.append("<__file__ lanzó error>")
    try:
        tried.append(os.path.join(os.getcwd(), "web"))
    except Exception:
        tried.append("<os.getcwd() lanzó error>")
    return tried


def _fatal_exit_error(message):
    """Muestra error de forma robusta (tkinter si existe, si no stderr)."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error Crítico de DeepSight", message)
        root.destroy()
    except Exception:
        sys.stderr.write("\n*** ERROR CRÍTICO DEEPSIGHT ***\n" + message + "\n\n")
    sys.exit(1)

def is_running_as_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def torch_cuda_available():
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False

class DeepSightAPI:
    def __init__(self):
        self.window = None
        self.trainer = None
        self.trained_model_path = None
        self.inference_model = None
        self._drop_lock = threading.Lock()
        self._drop_counter = 0
        local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        self._drop_cache_dir = os.path.join(local_appdata, "DeepSight", "_deepsight_workspace", "drop_cache")

    def set_window(self, window):
        self.window = window

    def get_system_info(self):
        return {
            "device": "cuda" if torch_cuda_available() else "cpu",
            "cpus": os.cpu_count() or 2,
            "ram_gb": get_ram_gb(),
            "is_admin": is_running_as_admin()
        }

    def select_files(self):
        if not self.window:
            return []
        file_types = ('Imágenes (*.png;*.jpg;*.jpeg;*.webp)', 'Todos los archivos (*.*)')
        result = self.window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True, file_types=file_types)
        return list(result) if result else []

    def _save_single_image(self, b64_data, filename):
        """Método interno: guarda UNA imagen Base64 en caché y retorna ruta absoluta."""
        try:
            os.makedirs(self._drop_cache_dir, exist_ok=True)

            if "," in b64_data:
                b64_data = b64_data.split(",", 1)[1]

            image_data = base64.b64decode(b64_data)

            clean_name = "".join(c for c in filename if c.isalnum() or c in ".-_ ")
            if not clean_name:
                clean_name = "dropped_img.jpg"

            _, ext = os.path.splitext(clean_name)
            if not ext:
                ext = ".png" if b64_data.startswith("iVBOR") else ".jpg"

            unique_id = uuid.uuid4().hex[:12]
            nano_ts = time.time_ns()
            with self._drop_lock:
                self._drop_counter += 1
                counter = self._drop_counter

            final_name = f"{nano_ts}_{unique_id}_{counter}{ext}"
            file_path = os.path.abspath(os.path.join(self._drop_cache_dir, final_name))

            with open(file_path, "wb") as f:
                f.write(image_data)

            return file_path
        except Exception as e:
            sys.stderr.write(f"[ERR] Error guardando imagen soltada {filename}: {e}\n")
            return None

    def save_dropped_image(self, b64_data, filename):
        """
        Guarda una imagen arrastrada desde la interfaz web (Base64) a una caché temporal.
        Esto esquiva el bloqueo de seguridad de Chromium que oculta las rutas absolutas al hacer drag-and-drop.
        Usa UUID + timestamp nanosegundos + contador atómico para GARANTIZAR nombres únicos.
        """
        return self._save_single_image(b64_data, filename)

    def save_dropped_images_batch(self, items):
        """
        Versión BATCH (lote) de save_dropped_image.
        Recibe una lista de diccionarios [{b64_data, filename}, ...] y retorna lista de rutas.
        Reduce drásticamente las llamadas IPC entre JS y Python (1 sola llamada para N archivos).
        """
        results = []
        if not items:
            return results
        try:
            os.makedirs(self._drop_cache_dir, exist_ok=True)
            for item in items:
                b64_data = item.get("b64_data", "")
                filename = item.get("filename", "image.jpg")
                results.append(self._save_single_image(b64_data, filename))
        except Exception as e:
            sys.stderr.write(f"[ERR] Error en save_dropped_images_batch: {e}\n")
        return results

    def export_model(self):
        if not self.window or not self.trained_model_path or not os.path.exists(self.trained_model_path):
            return False
        
        target = self.window.create_file_dialog(
            webview.SAVE_DIALOG, 
            save_filename='best.pt', 
            file_types=('Modelo PyTorch (*.pt)',)
        )
        if target:
            try:
                # Normalizar ruta retornado por webview (puede ser tupla o string)
                if isinstance(target, (list, tuple)):
                    target = target[0]
                shutil.copy(self.trained_model_path, target)
                self.log(f"[SYS] Modelo exportado correctamente a: {target}", "success")
                return True
            except Exception as e:
                self.log(f"[ERR] Error exportando modelo: {e}", "error")
                return False
        return False

    def start_training(self, data_dict):
        if not data_dict:
            self.log("[ERR] No hay clases definidas para entrenar.", "error")
            self.eval_js("window.onTrainingFinished(null, false)")
            return
        try:
            min_images = min(len(paths) for paths in data_dict.values())
        except ValueError:
            self.log("[ERR] Datos inválidos para entrenar (clases sin imágenes).", "error")
            self.eval_js("window.onTrainingFinished(null, false)")
            return
        is_deep_mode = min_images >= 50

        def on_log(msg):
            self.log(msg, "info")

        def on_finish(best_pt_path):
            if best_pt_path and os.path.exists(best_pt_path):
                self.trained_model_path = best_pt_path
                try:
                    self.inference_model = YOLO(self.trained_model_path)
                    escaped = self.escape_js(best_pt_path)
                    self.eval_js(f"window.onTrainingFinished('{escaped}', true)")
                except Exception as e:
                    self.log(f"[ERR] Error cargando modelo de inferencia: {e}", "error")
                    self.eval_js("window.onTrainingFinished(null, false)")
            else:
                self.eval_js("window.onTrainingFinished(null, false)")

        self.trainer = DeepSightTrainer(data_dict, on_log=on_log, on_finish=on_finish, is_deep_mode=is_deep_mode)
        self.trainer.start()

    def predict(self, image_path):
        if not self.inference_model:
            return
        try:
            results = self.inference_model(image_path, verbose=False)
            if results and len(results) > 0:
                r = results[0]
                top1_idx = r.probs.top1
                conf = float(r.probs.top1conf.item() * 100)
                class_name = str(r.names[top1_idx])
                
                escaped_class = self.escape_js(class_name)
                self.eval_js(f"window.onPredictionResult('{escaped_class}', {conf})")
        except Exception as e:
            self.log(f"[ERR] Error en inferencia: {e}", "error")

    def log(self, text, log_type="info"):
        escaped = self.escape_js(text)
        self.eval_js(f"window.appendLog('{escaped}', '{log_type}')")

    def eval_js(self, js_code):
        if self.window:
            try:
                self.window.evaluate_js(js_code)
            except Exception:
                pass

    def escape_js(self, text):
        return str(text).replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '')


def check_zip_execution():
    if not getattr(sys, 'frozen', False):
        return
    try:
        exe = getattr(sys, "executable", None) or ""
        if not exe:
            return
        exe_path_normalized = os.path.abspath(str(exe)).lower()
    except Exception:
        return
    try:
        temp_dir = (os.environ.get("TEMP", "") or "").lower()
        if temp_dir and temp_dir in exe_path_normalized:
            _fatal_exit_error(
                "¡Atención!\n\n"
                "Estás intentando ejecutar la aplicación directamente desde un archivo ZIP sin extraer.\n\n"
                "Por favor, extrae el archivo ZIP en una carpeta y vuelve a abrir la aplicación."
            )
    except Exception:
        pass


def main():
    # freeze_support() ya se ejecutó a nivel módulo (mucho antes, aquí no hace falta repetirlo)
    try:
        check_zip_execution()
    except SystemExit:
        raise
    except Exception:
        # No permitir fallo total por ZIP check
        pass

    # --- RESOLUCIÓN ROBUSTA DEL DIRECTORIO WEB ---
    base_dir = _resolve_web_base_dir()

    if not base_dir or not isinstance(base_dir, str) or not base_dir.strip():
        # Usar la función auxiliar que NUNCA falla y construye la lista exacta
        tried_paths = _list_web_base_dir_candidates()
        try:
            tried_desc = "\n".join("  • " + str(p) for p in tried_paths)
        except Exception:
            tried_desc = "  (no se pudieron listar las rutas)"
        _fatal_exit_error(
            "No se encontró la carpeta 'web/' con los archivos de la interfaz.\n\n"
            "Rutas buscadas:\n" + tried_desc + "\n\n"
            "Reinstala o extrae correctamente la aplicación."
        )

    # --- RESOLUCIÓN DEL index.html ---
    html_path = None
    try:
        html_path = os.path.join(str(base_dir), 'index.html')
        if not os.path.isfile(str(html_path)):
            _fatal_exit_error(
                f"No se encontró index.html en la ruta:\n  {html_path}\n\n"
                "La carpeta web/ está incompleta o dañada."
            )
    except SystemExit:
        raise
    except Exception as e:
        _fatal_exit_error(
            "Error al localizar index.html dentro de:\n"
            f"  {base_dir}\n\nDetalle: {type(e).__name__}: {e}"
        )

    api = DeepSightAPI()
    try:
        window = webview.create_window(
            title='DeepSight - Entrenador Visual',
            url=str(html_path),
            width=1150,
            height=740,
            min_size=(900, 600),
            resizable=True,
            js_api=api,
            text_select=True,
            background_color='#1e1f22'
        )
    except TypeError as te:
        # Si algún parámetro no es compatible con la versión instalada de pywebview,
        # reintentar SOLO con los parámetros que sabemos que existen.
        sys.stderr.write(f"[WARN] pywebview rechazó parámetros ({te}), reintentando con modo compatible...\n")
        window = webview.create_window(
            title='DeepSight - Entrenador Visual',
            url=str(html_path),
            width=1150,
            height=740,
            min_size=(900, 600),
            resizable=True,
            js_api=api
        )

    api.set_window(window)
    webview.start(debug=False)


if __name__ == '__main__':
    # Doble guardia de freeze_support (estándar PyInstaller): módulo y aquí.
    try:
        multiprocessing.freeze_support()
    except Exception:
        pass
    main()

