import os
import sys
import shutil
import ctypes
import webview
from ultralytics import YOLO

import base64
from io import BytesIO
from PIL import Image

from trainer import DeepSightTrainer, get_ram_gb

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

def load_image_as_data_url(file_path, max_dim=120):
    try:
        clean_path = str(file_path).strip().strip('{}')
        if not os.path.exists(clean_path):
            return ""
        with Image.open(clean_path) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            w, h = img.size
            if w > max_dim or h > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            buffered = BytesIO()
            img.save(buffered, format="JPEG", quality=80)
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            return f"data:image/jpeg;base64,{img_str}"
    except Exception:
        return ""

class DeepSightAPI:
    def __init__(self):
        self.window = None
        self.trainer = None
        self.trained_model_path = None
        self.inference_model = None

    def set_window(self, window):
        self.window = window

    def get_system_info(self):
        return {
            "device": "cuda" if torch_cuda_available() else "cpu",
            "cpus": os.cpu_count() or 2,
            "ram_gb": get_ram_gb(),
            "is_admin": is_running_as_admin()
        }

    def get_thumbnail(self, file_path):
        return load_image_as_data_url(file_path, max_dim=120)

    def get_preview(self, file_path):
        return load_image_as_data_url(file_path, max_dim=400)

    def select_files(self):
        if not self.window:
            return []
        file_types = ('Imágenes (*.png;*.jpg;*.jpeg;*.webp)', 'Todos los archivos (*.*)')
        result = self.window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True, file_types=file_types)
        return list(result) if result else []

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
        min_images = min(len(paths) for paths in data_dict.values())
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
    if getattr(sys, 'frozen', False):
        exe_path_normalized = os.path.abspath(sys.executable).lower()
        temp_dir = os.environ.get("TEMP", "").lower()
        if temp_dir and temp_dir in exe_path_normalized:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Error de ejecución - ZIP detectado",
                "¡Atención!\n\n"
                "Estás intentando ejecutar la aplicación directamente desde un archivo ZIP sin extraer.\n\n"
                "Por favor, extrae el archivo ZIP en una carpeta y vuelve a abrir la aplicación."
            )
            root.destroy()
            sys.exit(1)


def main():
    check_zip_execution()

    if getattr(sys, 'frozen', False):
        base_dir = os.path.join(sys._MEIPASS, 'web')
    else:
        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')

    html_path = os.path.join(base_dir, 'index.html')

    api = DeepSightAPI()
    window = webview.create_window(
        title='DeepSight - Entrenador Visual',
        url=html_path,
        width=1150,
        height=740,
        min_size=(900, 600),
        resizable=True,
        js_api=api
    )
    api.set_window(window)
    webview.start(debug=False)

if __name__ == '__main__':
    main()
