import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES
from PIL import Image
from ultralytics import YOLO

from trainer import DeepSightTrainer

# ==========================================
# WRAPPER DND
# ==========================================
class TkDnDCTk(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)

ctk.set_appearance_mode("light") 
ctk.set_default_color_theme("blue")

# ==========================================
# WIDGET CLASE (TARJETA)
# ==========================================
class ClassCard(ctk.CTkFrame):
    def __init__(self, master, class_id, name, on_delete, *args, **kwargs):
        super().__init__(master, fg_color="white", corner_radius=10, border_width=1, border_color="#e0e0e0", *args, **kwargs)
        self.class_id = class_id
        self.image_paths = set()
        
        # --- Header ---
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        self.name_entry = ctk.CTkEntry(self.header_frame, font=ctk.CTkFont(size=16, weight="bold"), 
                                       fg_color="transparent", border_width=0, text_color="#333333")
        self.name_entry.insert(0, name)
        self.name_entry.pack(side="left", fill="x", expand=True)
        
        self.delete_btn = ctk.CTkButton(self.header_frame, text="X", width=28, height=28, 
                                        fg_color="#ff4d4d", hover_color="#cc0000", text_color="white",
                                        command=lambda: on_delete(self.class_id))
        self.delete_btn.pack(side="right")
        
        # --- Body (Drag & Drop area) ---
        self.drop_area = ctk.CTkFrame(self, height=120, fg_color="#f5f7fa", corner_radius=8, border_width=2, border_color="#d0d7e5")
        self.drop_area.pack(fill="x", padx=10, pady=(0, 5), expand=True)
        self.drop_area.pack_propagate(False)
        
        self.drop_label = ctk.CTkLabel(self.drop_area, text="Arrastra imágenes aquí\nó haz clic para buscar", 
                                       text_color="#888888", font=ctk.CTkFont(size=12))
        self.drop_label.pack(expand=True)
        
        # Bindings click
        self.drop_area.bind("<Button-1>", self.browse_files)
        self.drop_label.bind("<Button-1>", self.browse_files)
        
        # TkinterDnD
        self.drop_area.drop_target_register(DND_FILES)
        self.drop_area.dnd_bind('<<Drop>>', self.on_drop)
        
        # --- Footer (Contador) ---
        self.count_label = ctk.CTkLabel(self, text="0 imágenes", font=ctk.CTkFont(size=12, weight="bold"), text_color="#555555")
        self.count_label.pack(anchor="w", padx=15, pady=(0, 10))

    def on_drop(self, event):
        files = self.winfo_toplevel().tk.splitlist(event.data)
        self.add_images(files)
        
    def browse_files(self, event=None):
        files = filedialog.askopenfilenames(title="Seleccionar imágenes", filetypes=[("Imágenes", "*.png;*.jpg;*.jpeg;*.webp")])
        if files:
            self.add_images(files)
            
    def add_images(self, files):
        count = 0
        for f in files:
            clean_path = f.strip('{}')
            if os.path.isfile(clean_path) and clean_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                self.image_paths.add(clean_path)
                count += 1
        self.update_count()
        
    def update_count(self):
        n = len(self.image_paths)
        if n < 5:
            self.count_label.configure(text=f"{n} imágenes (⚠️ Mín. 5)", text_color="#ff9900")
        else:
            self.count_label.configure(text=f"{n} imágenes ✔️", text_color="#00aa00")
            
    def get_class_name(self):
        return self.name_entry.get().strip()

# ==========================================
# MAIN APP
# ==========================================
class DeepSightApp(TkDnDCTk):
    def __init__(self):
        super().__init__()
        self.title("DeepSight - Entrenador Visual")
        self.geometry("1100x700")
        self.minsize(900, 600)
        
        import sys
        
        # Buscar el icono en la misma carpeta que el .exe o el script
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        icon_path = os.path.join(base_dir, "favicon.ico")
        try: self.iconbitmap(icon_path)
        except Exception: pass
            
        self.grid_columnconfigure(0, weight=1, uniform="col") 
        self.grid_columnconfigure(1, weight=1, uniform="col") 
        self.grid_columnconfigure(2, weight=1, uniform="col") 
        self.grid_rowconfigure(0, weight=1)
        
        # Estado
        self.class_cards = {}
        self.class_counter = 0
        self.trainer_active = False
        self.trained_model_path = None
        self.inference_model = None
        
        self.setup_panel_classes()
        self.setup_panel_train()
        self.setup_panel_test()
        
        # Inicializar con 2 clases
        self.add_class("Clase 1")
        self.add_class("Clase 2")

    def setup_panel_classes(self):
        self.panel_classes = ctk.CTkFrame(self, fg_color="#f0f2f5", corner_radius=0)
        self.panel_classes.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
        
        lbl = ctk.CTkLabel(self.panel_classes, text="1. Define tus Clases", font=ctk.CTkFont(size=20, weight="bold"))
        lbl.pack(pady=(20, 10))
        
        self.scroll_classes = ctk.CTkScrollableFrame(self.panel_classes, fg_color="transparent")
        self.scroll_classes.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.btn_add_class = ctk.CTkButton(self.panel_classes, text="➕ Añadir Clase", font=ctk.CTkFont(weight="bold"), 
                                           command=self.add_class, fg_color="white", text_color="#1f538d", border_width=2)
        self.btn_add_class.pack(pady=20, padx=20, fill="x")

    def setup_panel_train(self):
        self.panel_train = ctk.CTkFrame(self, fg_color="#ffffff", corner_radius=0)
        self.panel_train.grid(row=0, column=1, sticky="nsew", padx=2)
        
        lbl = ctk.CTkLabel(self.panel_train, text="2. Entrenamiento", font=ctk.CTkFont(size=20, weight="bold"))
        lbl.pack(pady=(20, 10))
        
        self.btn_train = ctk.CTkButton(self.panel_train, text="🚀 Entrenar Modelo", height=45, 
                                       font=ctk.CTkFont(size=16, weight="bold"), command=self.start_training)
        self.btn_train.pack(fill="x", padx=20, pady=10)
        
        self.lbl_status = ctk.CTkLabel(self.panel_train, text="Añade imágenes y haz clic en Entrenar", text_color="#666666")
        self.lbl_status.pack(pady=5)
        
        self.lbl_tip = ctk.CTkLabel(
            self.panel_train,
            text="💡 Tip Pro: Usa 50+ imágenes por clase para activar el motor de alta precisión.\nMenos de 50 activará el modo rápido.",
            text_color="#999999",
            font=ctk.CTkFont(size=10),
            wraplength=280,
            justify="center"
        )
        self.lbl_tip.pack(pady=(0, 6))
        
        self.txt_log = ctk.CTkTextbox(self.panel_train, font=ctk.CTkFont(family="Consolas", size=11), 
                                      fg_color="#1e1e1e", text_color="#d4d4d4", state="disabled")
        self.txt_log.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    def setup_panel_test(self):
        self.panel_test = ctk.CTkFrame(self, fg_color="#f0f2f5", corner_radius=0)
        self.panel_test.grid(row=0, column=2, sticky="nsew", padx=(2, 0))
        
        lbl = ctk.CTkLabel(self.panel_test, text="3. Prueba y Exporta", font=ctk.CTkFont(size=20, weight="bold"))
        lbl.pack(pady=(20, 10))
        
        self.frame_test_drop = ctk.CTkFrame(self.panel_test, fg_color="white", corner_radius=15, border_width=2, border_color="#d0d7e5")
        self.frame_test_drop.pack(fill="x", padx=20, pady=10)
        
        self.lbl_test_drop = ctk.CTkLabel(self.frame_test_drop, text="Arrastra una imagen\npara probar el modelo", text_color="#888888")
        self.lbl_test_drop.pack(pady=40)
        
        self.frame_test_drop.drop_target_register(DND_FILES)
        self.frame_test_drop.dnd_bind('<<Drop>>', self.on_test_image_drop)
        
        self.lbl_result_img = ctk.CTkLabel(self.panel_test, text="")
        self.lbl_result_img.pack(pady=10)
        
        self.lbl_prediction = ctk.CTkLabel(self.panel_test, text="Predicción: ---", font=ctk.CTkFont(size=18, weight="bold"))
        self.lbl_prediction.pack(pady=5)
        self.lbl_confidence = ctk.CTkLabel(self.panel_test, text="Confianza: ---", font=ctk.CTkFont(size=14))
        self.lbl_confidence.pack(pady=0)
        
        self.btn_export = ctk.CTkButton(self.panel_test, text="💾 Exportar best.pt", height=45, 
                                        font=ctk.CTkFont(size=14, weight="bold"), fg_color="#00aa00", hover_color="#008800",
                                        command=self.export_model, state="disabled")
        self.btn_export.pack(side="bottom", fill="x", padx=20, pady=20)

    # --- Lógica ---
    def add_class(self, default_name=None):
        self.class_counter += 1
        cid = self.class_counter
        name = default_name if default_name else f"Clase {cid}"
        
        card = ClassCard(self.scroll_classes, class_id=cid, name=name, on_delete=self.delete_class)
        card.pack(fill="x", pady=(0, 15))
        self.class_cards[cid] = card
        
    def delete_class(self, class_id):
        if len(self.class_cards) <= 2:
            messagebox.showwarning("Aviso", "Debes tener al menos 2 clases para entrenar.")
            return
        if class_id in self.class_cards:
            self.class_cards[class_id].destroy()
            del self.class_cards[class_id]

    def start_training(self):
        if self.trainer_active: return
        
        data_dict = {}
        for cid, card in self.class_cards.items():
            name = card.get_class_name()
            if not name:
                messagebox.showerror("Error", "Todas las clases deben tener un nombre.")
                return
            if len(card.image_paths) < 5:
                messagebox.showerror("Error", f"La clase '{name}' tiene menos de 5 imágenes.")
                return
            if name in data_dict:
                messagebox.showerror("Error", "Hay clases con nombres duplicados.")
                return
            data_dict[name] = list(card.image_paths)
            
        if len(data_dict) < 2:
            messagebox.showerror("Error", "Necesitas al menos 2 clases válidas.")
            return
            
        # --- Calcular modo de entrenamiento ---
        min_images = min(len(paths) for paths in data_dict.values())
        is_deep_mode = min_images >= 50
        
        self.trainer_active = True
        self.btn_train.configure(state="disabled", text="Entrenando...")
        self.btn_add_class.configure(state="disabled")
        self.btn_export.configure(state="disabled")
        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", tk.END)
        self.txt_log.configure(state="disabled")
        self.inference_model = None
        self.lbl_prediction.configure(text="Predicción: ---")
        self.lbl_confidence.configure(text="Confianza: ---")
        self.lbl_result_img.configure(image="")
        self.lbl_test_drop.configure(text="Arrastra una imagen\npara probar el modelo")
        
        if is_deep_mode:
            self.append_log("🧠 Modo ALTA PRECISIÓN activado (50+ imágenes por clase). Épocas: 50, LR: 0.001")
        else:
            self.append_log(f"⚡ Modo RÁPIDO (Few-Shot) activado ({min_images} imágenes en la clase más pequeña). Épocas: 100, LR: 0.0005")
        
        self.trainer = DeepSightTrainer(data_dict, on_log=self.append_log, on_finish=self.training_finished, is_deep_mode=is_deep_mode)
        self.trainer.start()
        
    def append_log(self, text):
        def update():
            self.txt_log.configure(state="normal")
            self.txt_log.insert(tk.END, text + "\n")
            self.txt_log.see(tk.END)
            self.txt_log.configure(state="disabled")
        self.after(0, update)
        
    def training_finished(self, best_pt_path):
        def finish():
            self.trainer_active = False
            self.btn_train.configure(state="normal", text="🚀 Entrenar Modelo")
            self.btn_add_class.configure(state="normal")
            
            if best_pt_path and os.path.exists(best_pt_path):
                self.trained_model_path = best_pt_path
                self.btn_export.configure(state="normal")
                self.lbl_status.configure(text="✅ Modelo entrenado y listo para probar", text_color="#00aa00")
                try:
                    self.inference_model = YOLO(self.trained_model_path)
                except Exception as e:
                    self.append_log(f"Error cargando modelo para inferencia: {e}")
            else:
                self.lbl_status.configure(text="❌ Error en el entrenamiento", text_color="#ff4d4d")
                messagebox.showerror("Error", "El entrenamiento falló. Revisa el registro.")
        self.after(0, finish)

    def on_test_image_drop(self, event):
        if not self.inference_model:
            messagebox.showinfo("Aviso", "Primero debes entrenar un modelo.")
            return
            
        files = self.tk.splitlist(event.data)
        if not files: return
        file_path = files[0].strip('{}')
        
        if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            try:
                img = Image.open(file_path)
                # Resize for display maintaining aspect ratio
                img.thumbnail((250, 250)) 
                ctk_img = ctk.CTkImage(img, size=img.size)
                self.lbl_result_img.configure(image=ctk_img)
                self.lbl_test_drop.configure(text="")
                
                results = self.inference_model(file_path, verbose=False)
                if results and len(results) > 0:
                    r = results[0]
                    top1_idx = r.probs.top1
                    conf = r.probs.top1conf.item() * 100
                    class_name = r.names[top1_idx]
                    
                    self.lbl_prediction.configure(text=f"Predicción: {class_name}")
                    self.lbl_confidence.configure(text=f"Confianza: {conf:.1f}%")
                    
            except Exception as e:
                messagebox.showerror("Error", f"Error al probar imagen:\n{e}")

    def export_model(self):
        if not self.trained_model_path or not os.path.exists(self.trained_model_path):
            return
            
        target = filedialog.asksaveasfilename(
            defaultextension=".pt", 
            filetypes=[("PyTorch Model", "*.pt")],
            initialfile="best.pt",
            title="Guardar modelo entrenado"
        )
        if target:
            try:
                shutil.copy(self.trained_model_path, target)
                messagebox.showinfo("Éxito", f"Modelo exportado a:\n{target}")
            except Exception as e:
                messagebox.showerror("Error", f"Error al exportar:\n{e}")

def check_zip_execution():
    import sys
    if getattr(sys, 'frozen', False):
        exe_path_normalized = os.path.abspath(sys.executable).lower()
        temp_dir = os.environ.get("TEMP", "").lower()
        if temp_dir and temp_dir in exe_path_normalized:
            # Crear una pequeña ventana temporal oculta para que se pueda mostrar el messagebox sin la UI principal
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Error de ejecución - ZIP detectado",
                "¡Atención!\n\n"
                "Estás intentando ejecutar la aplicación directamente desde el interior de un archivo ZIP sin extraer.\n\n"
                "Por favor, cierra esta ventana, haz clic derecho sobre el archivo ZIP y selecciona \"Extraer todo...\". "
                "Luego, abre la aplicación desde la carpeta extraída para evitar fallos de permisos y escrituras."
            )
            root.destroy()
            sys.exit(1)

if __name__ == "__main__":
    check_zip_execution()
    app = DeepSightApp()
    app.mainloop()
