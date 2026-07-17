import os
import threading
import torch
import sys
from ultralytics import YOLO

# Importamos las herramientas de nuestro nuevo utils.py
from utils import prepare_dataset_split

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
        
        # Rutas de trabajo limitadas
        self.tmp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_deepsight_workspace")
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
            # Aquí usamos utils.py, dejando trainer.py mucho más limpio
            dataset_dir = prepare_dataset_split(self.data_dict, self.tmp_dir)
            
            self.on_log("¡Imágenes listas!")
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.on_log(f"🧠 Acelerador detectado: {device.upper()}")
            
            # --- Selección Inteligente de Modelo según Hardware y Modo ---
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
            else:
                # En CPU priorizamos estabilidad y velocidad para evitar congelar la laptop del alumno
                model_filename = "yolo26n-cls.pt"
                if self.is_deep_mode:
                    self.on_log("💻 Ejecutando en CPU -> Cargando YOLO26 Nano offline para evitar lentitud extrema.")
                else:
                    self.on_log("💻 Ejecutando en CPU + Modo Rápido -> Cargando YOLO26 Nano offline.")

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

            model = YOLO(model_path)  # Carga el modelo seleccionado localmente
            model.train(
                data=dataset_dir,
                epochs=epochs,
                imgsz=224,
                batch=8,
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
            # Siempre se debe restaurar la consola al final
            sys.stdout = self.original_stdout
            sys.stderr = self.original_stderr
            self.is_running = False
            self.on_finish(best_pt_path)
