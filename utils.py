import os
import shutil
import random
from PIL import Image

def process_and_copy_image(src_path, dst_path, max_dim=640):
    """
    Copia y optimiza la imagen ajustando su tamaño máximo a max_dim
    para reducir drásticamente la carga de RAM y el tiempo de lectura en disco.
    """
    try:
        with Image.open(src_path) as img:
            # Convertir a RGB si está en RGBA/Palette
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Redimensionar solo si supera la dimensión máxima
            w, h = img.size
            if w > max_dim or h > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            
            img.save(dst_path, quality=85, optimize=True)
    except Exception:
        # Fallback de copia directa en caso de formato no soportado por PIL
        try: shutil.copy(src_path, dst_path)
        except Exception: pass

def prepare_dataset_split(data_dict, tmp_dir):
    """
    Toma un diccionario de {clase: [rutas_imagenes]} y crea un dataset
    con split automático 80/20 listos para YOLO con pre-escalado de alto rendimiento.
    """
    dataset_dir = os.path.join(tmp_dir, "dataset")
    
    # Limpiamos el espacio temporal si existe de un entrenamiento anterior
    if os.path.exists(tmp_dir):
        try: shutil.rmtree(tmp_dir)
        except Exception: pass
    
    train_dir = os.path.join(dataset_dir, "train")
    val_dir = os.path.join(dataset_dir, "val")
    
    for cls_name, files in data_dict.items():
        c_train = os.path.join(train_dir, cls_name)
        c_val = os.path.join(val_dir, cls_name)
        os.makedirs(c_train, exist_ok=True)
        os.makedirs(c_val, exist_ok=True)
        
        # Mezclar para evitar sesgo en el entrenamiento
        random.shuffle(files)
        
        # Separar 20% para validación, asegurando al menos 1 imagen
        n_val = max(1, int(len(files) * 0.2)) 
        if len(files) == 1: 
            n_val = 0 
        
        val_files = files[:n_val]
        train_files = files[n_val:]
        
        # Fallback de seguridad
        if not train_files: train_files = files 
        if not val_files: val_files = files 
        
        # Copiar y optimizar imágenes para train/
        for i, f in enumerate(train_files):
            ext = os.path.splitext(f)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
                ext = '.jpg'
            process_and_copy_image(f, os.path.join(c_train, f"img_{i}{ext}"))
            
        # Copiar y optimizar imágenes para val/    
        for i, f in enumerate(val_files):
            ext = os.path.splitext(f)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
                ext = '.jpg'
            process_and_copy_image(f, os.path.join(c_val, f"img_{i}{ext}"))
            
    return dataset_dir
