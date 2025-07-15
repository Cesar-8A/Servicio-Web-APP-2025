# dicom_metadata.py
import numpy as np
import pydicom
from flask import current_app as app

def load_metadata_and_slices(unique_id):
    """
    Carga metadatos y slices de la serie DICOM correspondiente al unique_id.
    Guarda los slices y el Modality en app.config.
    Devuelve un diccionario con los metadatos principales.
    """
    dicom_series = app.config.get('dicom_series', {})
    if unique_id not in dicom_series:
        raise ValueError("Serie DICOM no encontrada")

    dicom_files = dicom_series[unique_id]["ruta_archivos"]
    if not dicom_files:
        raise ValueError("La serie no contiene archivos DICOM")

    # Leer metadatos del primer archivo
    dicom_data = pydicom.dcmread(dicom_files[0], stop_before_pixels=False, force=True)
    # Se pueden expandir los datos devueltos si se quieren usar más después
    metadata = {
        "PatientName": str(dicom_data.get("PatientName", "Desconocido")),
        "StudyDate": str(dicom_data.get("StudyDate", "Desconocido")),
        "Modality": str(dicom_data.get("Modality", "Desconocido")),
    }

    # Cargar slices ordenados por InstanceNumber
    slices = []
    for file in dicom_files:
        dcm = pydicom.dcmread(file, stop_before_pixels=False)
        instance = int(dcm.get("InstanceNumber", 0))
        slices.append((instance, dcm.pixel_array))

    slices.sort(key=lambda x: x[0])
    sorted_pixel_arrays = np.array([s[1] for s in slices])

    # Guardar en app.config
    dicom_series[unique_id]["slices"] = sorted_pixel_arrays
    dicom_series[unique_id]["Modality"] = metadata["Modality"]

    return metadata
