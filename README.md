# DeepSight - Entrenador Visual Inteligente

DeepSight es una aplicación de escritorio intuitiva diseñada para que estudiantes y entusiastas de la inteligencia artificial puedan entrenar modelos de clasificación de imágenes utilizando la tecnología YOLO, sin necesidad de escribir código.

Inspirada en herramientas como Teachable Machine, DeepSight automatiza todo el proceso complejo de preparación de datos y ajuste de parámetros de IA.

## Caracteristicas Principales

* **Interfaz Drag & Drop**: Arrastra carpetas o imágenes directamente a la aplicación para definir tus clases.
* **Entrenamiento Inteligente**: El sistema detecta el tamaño de tu dataset y el hardware disponible para optimizar el rendimiento:
  * **Modo Rapido (Few-Shot)**: Optimizado para datasets pequeños (ideal para prototipos rápidos).
  * **Modo Alta Precision**: Se activa automáticamente al detectar 50+ imágenes por clase para mayor robustez.
  * **Seleccion Inteligente de Modelo**: Usa YOLO26 Nano en CPU para evitar sobrecalentamiento o lentitud extrema, y sube automáticamente a YOLO26 Small en sistemas con GPU dedicada (CUDA) en el modo de alta precisión.
* **Auto-Split 80/20**: Organiza automáticamente tus archivos en datos de entrenamiento y validación.
* **Inferencia en Tiempo Real**: Prueba tu modelo inmediatamente arrastrando una imagen al panel de pruebas.
* **Exportacion Lista para Usar**: Guarda tu modelo entrenado en formato .pt para integrarlo en cualquier otro proyecto de Python o Edge AI.
* **Proteccion contra Ejecucion Incorrecta**: Valida en el arranque si la aplicación se está ejecutando desde un archivo comprimido ZIP sin extraer, evitando fallos silenciosos y errores de escritura comunes en entornos de estudiantes.

## Tecnologias Utilizadas

* **Lenguaje**: Python 3.x
* **Motor de IA**: Ultralytics YOLO
* **Interfaz Grafica**: CustomTkinter
* **Backend de Entrenamiento**: Procesamiento en hilos (threading) para mantener la interfaz fluida.
* **Procesamiento de Imagenes**: PIL (Pillow) y gestión de archivos asíncrona.

## Estructura del Codigo

* `main.py`: Lógica de la interfaz de usuario, gestión de eventos y paneles laterales. Contiene el detector de ejecución en carpetas temporales de ZIP.
* `trainer.py`: Motor de entrenamiento que interactúa con YOLO, aplica lógica inteligente de hardware y gestiona los hiperparámetros.
* `utils.py`: Funciones auxiliares para la organización y división (split) del dataset.
* `download_weights.py`: Script para pre-descargar localmente los modelos YOLO26 Nano y Small para habilitar el funcionamiento offline.
* `DeepSight.spec`: Archivo de configuración para empaquetado como ejecutable en carpeta utilizando PyInstaller.
* `installer.iss`: Script de configuración de Inno Setup para compilar el instalador de Windows con estilo visual moderno y sin requerir privilegios de administrador.
* `favicon.ico`: Identidad visual de la aplicación.

## Como Empezar (Modo Desarrollo)

1. **Clona el repositorio** o descarga los archivos.
2. **Instala las dependencias**:
   ```bash
   pip install ultralytics customtkinter tkinterdnd2 pillow
   ```
3. **Descarga los modelos base localmente**:
   ```bash
   python download_weights.py
   ```
4. **Ejecuta la aplicacion**:
   ```bash
   python main.py
   ```
5. **Entrena tu IA**:
   - Crea al menos 2 clases.
   - Sube 5+ imágenes por clase.
   - Presiona entrenar y exporta tu modelo cuando termine.

## Compilacion y Creacion del Instalador (Windows)

Para empaquetar la aplicación y generar el archivo autoinstalable:

1. Asegúrate de haber ejecutado el script para descargar los pesos de los modelos:
   ```bash
   python download_weights.py
   ```
2. Compila el ejecutable con PyInstaller usando la especificación del proyecto:
   ```bash
   pyinstaller DeepSight.spec --clean
   ```
   Esto generará los binarios compilados en la carpeta `dist/DeepSight`.
3. Compila el instalador utilizando Inno Setup:
   - Abre Inno Setup Compiler.
   - Carga el archivo `installer.iss`.
   - Compila el instalador presionando `Ctrl + F9` o seleccionando la opción en el menú.
   - El archivo autoinstalable `DeepSight_Setup.exe` se creará en la carpeta `Output` del proyecto.
