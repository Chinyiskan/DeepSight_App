import os
import shutil
import random
import sys
import urllib.parse
from PIL import Image

def clean_file_path(path_str):
    if not path_str:
        return ""
    s = str(path_str).strip().strip('\'"{}')
    if s.startswith("file:///"):
        s = s[8:]
    elif s.startswith("file://"):
        s = s[7:]
    s = urllib.parse.unquote(s)
    s = os.path.normpath(s)
    return s

def process_and_copy_image(src_path, dst_path, max_dim=640):
    """
    Copia y optimiza la imagen ajustando su tamaño máximo a max_dim
    para reducir la carga de RAM y el tiempo de lectura en disco.
    """
    clean_src = clean_file_path(src_path)
    if not clean_src or not os.path.exists(clean_src):
        sys.stderr.write(f"[WARN] No existe la imagen de origen: '{clean_src}' (recibido: '{src_path}')\n")
        return False

    try:
        with Image.open(clean_src) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            w, h = img.size
            if w > max_dim or h > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            img.save(dst_path, format="JPEG", quality=85, optimize=True)
            return True
    except Exception as e:
        sys.stderr.write(f"[WARN] Falló optimización PIL en {clean_src}: {e}. Ejecutando copia directa.\n")
        try:
            shutil.copy(clean_src, dst_path)
            return True
        except Exception as e2:
            sys.stderr.write(f"[ERR] Error copiando imagen {clean_src} -> {dst_path}: {e2}\n")
            return False

def prepare_dataset_split(data_dict, tmp_dir):
    """
    Toma un diccionario de {clase: [rutas_imagenes]} y crea un dataset
    con split automático 80/20 listos para YOLO.
    """
    dataset_dir = os.path.join(tmp_dir, "dataset")
    
    # IMPORTANTE: Limpiar SOLO el subdirectorio 'dataset/' del entrenamiento anterior.
    # NO borrar tmp_dir completo porque contiene drop_cache/ con imágenes
    # que el usuario acaba de arrastrar y que aún no fueron copiadas al dataset.
    if os.path.exists(dataset_dir):
        try: shutil.rmtree(dataset_dir)
        except Exception: pass
    
    train_dir = os.path.join(dataset_dir, "train")
    val_dir = os.path.join(dataset_dir, "val")
    
    total_copied_train = 0
    total_copied_val = 0

    for cls_name, files in data_dict.items():
        c_train = os.path.join(train_dir, cls_name)
        c_val = os.path.join(val_dir, cls_name)
        os.makedirs(c_train, exist_ok=True)
        os.makedirs(c_val, exist_ok=True)
        
        # Copia para no alterar la lista original
        file_list = list(files)
        random.shuffle(file_list)
        
        n_val = max(1, int(len(file_list) * 0.2)) 
        if len(file_list) <= 2: 
            n_val = 1 
        
        val_files = file_list[:n_val]
        train_files = file_list[n_val:]
        
        if not train_files: train_files = file_list 
        if not val_files: val_files = file_list 
        
        # Copiar y optimizar imágenes para train/
        for i, f in enumerate(train_files):
            clean_f = clean_file_path(f)
            ext = os.path.splitext(clean_f)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
                ext = '.jpg'
            success = process_and_copy_image(f, os.path.join(c_train, f"img_{i}{ext}"))
            if success:
                total_copied_train += 1
            
        # Copiar y optimizar imágenes para val/    
        for i, f in enumerate(val_files):
            clean_f = clean_file_path(f)
            ext = os.path.splitext(clean_f)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
                ext = '.jpg'
            success = process_and_copy_image(f, os.path.join(c_val, f"img_{i}{ext}"))
            if success:
                total_copied_val += 1
            
    if total_copied_train == 0:
        raise ValueError("No se pudieron procesar ni copiar las imágenes de entrenamiento. Verifica que las rutas de los archivos existan.")

    return dataset_dir
