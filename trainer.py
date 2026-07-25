import os
import sys
os.environ["ULTRALYTICS_AUTO_INSTALL"] = "0"
os.environ["YOLO_VERBOSE"] = "False"

import threading
import torch
import gc
from ultralytics import YOLO

# Importamos las herramientas de nuestro nuevo utils.py
from utils import prepare_dataset_split

def get_ram_gb():
    try:
        import psutil
        return psutil.virtual_memory().total / (1024 ** 3)
    except Exception:
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ('dwLength', ctypes.c_ulong),
                    ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong),
                    ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong),
                    ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('sullAvailExtendedVirtual', ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return stat.ullTotalPhys / (1024 ** 3)
        except Exception:
            return 8.0

class PrintLogger:
    def __init__(self, callback):
        self.callback = callback
        self.terminal = sys.stdout

    def write(self, message):
        msg = message.replace('\r', '') 
        if msg.strip():
            self.callback(msg)
        if self.terminal:
            try:
                self.terminal.write(message)
            except AttributeError:
                pass

    def flush(self):
        if self.terminal:
            try:
                self.terminal.flush()
            except AttributeError:
                pass


class DeepSightTrainer:
    def __init__(self, data_dict, epochs=50, on_log=None, on_finish=None, is_deep_mode=True):
        self.data_dict = data_dict
        self.epochs = epochs
        self.on_log = on_log
        self.on_finish = on_finish
        self.is_deep_mode = is_deep_mode
        
        # Guardar workspace en %LOCALAPPDATA% para garantizar permisos de escritura sin requerir Administrador
        local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        self.tmp_dir = os.path.join(local_appdata, "DeepSight", "_deepsight_workspace")
        self.runs_dir = os.path.join(self.tmp_dir, "runs")
        self.is_running = False
        
        # Guarda estado de consola
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

    def start(self):
        if self.is_running: return
        self.is_running = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        # Redirigir consola a la GUI para mostrar progreso en vivo
        sys.stdout = PrintLogger(self.on_log)
        sys.stderr = sys.stdout
        best_pt_path = None
        
        try:
            self.on_log("Preparando imágenes y aplicando auto-split 80/20...")
            dataset_dir = prepare_dataset_split(self.data_dict, self.tmp_dir)
            
            self.on_log("¡Imágenes listas!")
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            cpus = os.cpu_count() or 2
            ram_gb = get_ram_gb()
            self.on_log(f"🧠 Acelerador detectado: {device.upper()} | CPUs: {cpus} | RAM: ~{ram_gb:.1f} GB")
            
            # --- Configuración inteligente de hilos CPU ---
            if device == "cpu":
                # Limitar hilos CPU a máximo 4 para evitar estrangulamiento térmico en laptops y dejar hilos a la UI
                num_threads = min(4, max(1, cpus - 1))
                torch.set_num_threads(num_threads)
                self.on_log(f"⚙️ Asignados {num_threads} hilos de CPU a PyTorch (optimizado para mantener la interfaz ultra fluida).")

            # --- Selección Inteligente de Modelo, Lote y Resolución según Hardware y Modo ---
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))

            if device == "cuda":
                if self.is_deep_mode:
                    model_filename = "yolo26s-cls.pt"
                    self.on_log("🎮 GPU dedicada detectada + Modo Alta Precisión -> Cargando YOLO26 Small offline.")
                else:
                    model_filename = "yolo26n-cls.pt"
                    self.on_log("🎮 GPU dedicada detectada + Modo Rápido -> Cargando YOLO26 Nano offline.")
                batch_size = 8
                img_size = 224
            else:
                # En CPU priorizamos estabilidad y velocidad para evitar congelar la laptop del alumno
                model_filename = "yolo26n-cls.pt"
                if self.is_deep_mode:
                    self.on_log("💻 Ejecutando en CPU -> Cargando YOLO26 Nano offline para evitar lentitud extrema.")
                else:
                    self.on_log("💻 Ejecutando en CPU + Modo Rápido -> Cargando YOLO26 Nano offline.")
                
                # Ajuste ligero de lote y resolución adaptativa para velocidad extrema en CPU
                if ram_gb <= 8.0 or cpus <= 2:
                    batch_size = 4
                    img_size = 160
                    self.on_log("⚡ Perfil Ultra-Ligero activado (RAM <= 8GB / CPU Modesto): Lote = 4, Res = 160px.")
                else:
                    batch_size = 8
                    img_size = 224

            model_path = os.path.join(base_path, model_filename)
            if not os.path.exists(model_path):
                self.on_log(f"⚠️ Alerta: Modelo local no encontrado en {model_path}. Se intentará descargar automáticamente.")
                model_path = model_filename

            self.on_log("Iniciando entrenamiento...")
            
            # --- Ajuste Inteligente de Hiperparámetros ---
            if not self.is_deep_mode:
                # Modo Rápido (Few-Shot): pocas imágenes por clase (<50)
                epochs  = 100
                freeze  = 10
                dropout = 0.5
                lr0     = 0.0005
            else:
                # Modo Alta Precisión (Full Training): 50+ imágenes por clase
                epochs  = 50
                freeze  = 3
                dropout = 0.2
                lr0     = 0.001

            # workers=0 y amp=False son VITALES en Windows empaquetado con PyInstaller para evitar subprocesos e IPC deadlocks
            model = YOLO(model_path)
            model.train(
                data=dataset_dir,
                epochs=epochs,
                imgsz=img_size,
                batch=batch_size,
                workers=0,
                amp=False,
                patience=15,
                device=device,
                project=self.runs_dir,
                name="deepsight_model",
                freeze=freeze,
                degrees=30,
                flipud=0.5,
                fliplr=0.5,
                hsv_s=0.8,
                hsv_v=0.5,
                translate=0.2,
                scale=0.5,
                lr0=lr0,
                weight_decay=0.001,
                dropout=dropout,
                exist_ok=True,
                plots=False
            )
            
            check_path = os.path.join(self.runs_dir, "deepsight_model", "weights", "best.pt")
            if os.path.exists(check_path):
                best_pt_path = check_path
                self.on_log("\n✅ ¡Entrenamiento completado exitosamente!")
            else:
                self.on_log("\n❌ Error: No se generó el modelo final (best.pt).")
                
        except Exception as e:
            self.on_log(f"\n❌ Se produjo un error crítico: {e}")
        finally:
            # Siempre restaurar la consola y realizar limpieza de memoria
            sys.stdout = self.original_stdout
            sys.stderr = self.original_stderr
            self.is_running = False
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.on_finish(best_pt_path)

