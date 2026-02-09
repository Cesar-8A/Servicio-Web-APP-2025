import numpy as np

def predict(volume_hu):
    """
    Realiza la predicción sobre un volumen en Unidades Hounsfield (HU).

    Args:
        volume_hu (np.ndarray): Volumen 3D con valores en Unidades Hounsfield.

    Returns:
        np.ndarray: Máscara binaria 3D (uint8) con los valores 0 (fondo) y 255 (objeto).
    """
    # Cargar el modelo entrenado (ejemplo: modelo guardado en formato .joblib)
    # from joblib import load
    # model = load("modelo_entrenado.joblib")

    # Aquí iría la lógica de inferencia del modelo
    # Por ahora, devolvemos una máscara binaria de ejemplo con las mismas dimensiones
    mask = np.zeros_like(volume_hu, dtype=np.uint8)

    # Ejemplo: Asignar 255 a todos los valores mayores a un umbral arbitrario
    threshold = 100  # Umbral de ejemplo
    mask[volume_hu > threshold] = 255

    return mask