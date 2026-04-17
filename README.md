# 👁️ DeepSight - Entrenador Visual Inteligente

DeepSight es una aplicación de escritorio intuitiva diseñada para que estudiantes y entusiastas de la inteligencia artificial puedan entrenar modelos de clasificación de imágenes utilizando la tecnología **YOLO**, sin necesidad de escribir código.

Inspirada en herramientas como *Teachable Machine*, DeepSight automatiza todo el proceso complejo de preparación de datos y ajuste de parámetros de IA.

## ✨ Características Principales

- **Interfaz Drag & Drop**: Arrastra carpetas o imágenes directamente a la aplicación para definir tus clases.
- **Entrenamiento Inteligente**: El sistema detecta el tamaño de tu dataset y elige el mejor modo:
  - **⚡ Modo Rápido (Few-Shot)**: Optimizado para datasets pequeños (ideal para prototipos rápidos).
  - **🧠 Modo Alta Precisión**: Se activa automáticamente al detectar 50+ imágenes por clase para mayor robustez.
- **Auto-Split 80/20**: Organiza automáticamente tus archivos en datos de entrenamiento y validación.
- **Inferencia en Tiempo Real**: Prueba tu modelo inmediatamente arrastrando una imagen al panel de pruebas.
- **Exportación Lista para Usar**: Guarda tu modelo entrenado en formato `.pt` para integrarlo en cualquier otro proyecto de Python o Edge AI.

## 🛠️ Tecnologías Utilizadas

- **Lenguaje**: Python 3.x
- **Motor de IA**: [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) (Visión artificial de vanguardia).
- **Interfaz Gráfica**: `CustomTkinter` (Diseño moderno y profesional).
- **Backend de Entrenamiento**: Procesamiento en hilos (threading) para mantener la interfaz fluida.
- **Utils**: Procesamiento de imágenes con `PIL` y gestión de archivos asíncrona.

## 📁 Estructura del Código

- `main.py`: Lógica de la interfaz de usuario, gestión de eventos y paneles laterales.
- `trainer.py`: Motor de entrenamiento que interactúa con YOLO y gestiona los hiperparámetros inteligentes.
- `utils.py`: Funciones auxiliares para la limpieza, organización y división (split) del dataset.
- `favicon.ico`: Identidad visual de la aplicación.
- `DeepSight.spec`: Archivo de configuración para empaquetado como ejecutable (.exe).

## 🚀 Cómo Empezar

1. **Clona el repositorio** o descarga los archivos.
2. **Instala las dependencias**:
   ```bash
   pip install ultralytics customtkinter tkinterdnd2 pillow
   ```
3. **Ejecuta la aplicación**:
   ```bash
   python main.py
   ```
4. **Entrena tu IA**:
   - Crea al menos 2 clases.
   - Sube 5+ imágenes por clase.
   - Presiona **🚀 Entrenar** y exporta tu modelo cuando termine.

---
*Desarrollado para facilitar el aprendizaje de la visión artificial de una manera visual y práctica.*
