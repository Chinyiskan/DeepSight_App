import os
import shutil
import random

def prepare_dataset_split(data_dict, tmp_dir):
    """
    Toma un diccionario de {clase: [rutas_imagenes]} y crea un dataset
    con split automático 80/20 listos para YOLO.
    
    Retorna la ruta de la carpeta principal del dataset.
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
        
        # Copiar imágenes a train/ y renombrarlas secuencialmente
        for i, f in enumerate(train_files):
            ext = os.path.splitext(f)[1] or '.jpg'
            shutil.copy(f, os.path.join(c_train, f"img_{i}{ext}"))
            
        # Copiar imágenes a val/ y renombrarlas secuencialmente    
        for i, f in enumerate(val_files):
            ext = os.path.splitext(f)[1] or '.jpg'
            shutil.copy(f, os.path.join(c_val, f"img_{i}{ext}"))
            
    return dataset_dir
