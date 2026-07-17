import os
import sys
from ultralytics import YOLO

def main():
    print("Iniciando la descarga de los modelos YOLO26...")
    
    # Asegurar que estamos en el directorio del script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"Directorio de trabajo establecido en: {script_dir}")
    
    models = ["yolo26n-cls.pt", "yolo26s-cls.pt"]
    
    for model_name in models:
        dest_path = os.path.join(script_dir, model_name)
        if os.path.exists(dest_path):
            print(f"El modelo {model_name} ya existe localmente. Omitiendo descarga.")
        else:
            print(f"Descargando {model_name} desde los servidores de Ultralytics/GitHub...")
            try:
                # Al inicializar, Ultralytics lo descargará automáticamente
                # en el directorio de trabajo si no existe.
                YOLO(model_name)
                print(f"✅ {model_name} descargado correctamente.")
            except Exception as e:
                print(f"❌ Error al descargar {model_name}: {e}")
                sys.exit(1)
                
    print("\n🎉 Todos los modelos necesarios han sido preparados localmente.")

if __name__ == "__main__":
    main()
