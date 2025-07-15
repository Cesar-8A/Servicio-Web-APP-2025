# dicom_export.py
import os
import zipfile
import pydicom
from flask import current_app as app

def export_dicom_series(unique_id: str, output_folder: str) -> str:
    """
    Anonimiza y exporta una serie DICOM especificada por unique_id al folder de salida.
    Devuelve la ruta al archivo ZIP generado.
    """
    if not unique_id:
        raise ValueError("ID de serie inválido")

    dicom_series = app.config.get('dicom_series', {})
    if unique_id not in dicom_series:
        raise ValueError("Serie DICOM no encontrada")

    archivosDicom = dicom_series[unique_id]["ruta_archivos"]
    anon_values = dicom_series[unique_id]["Anonimize"]

    os.makedirs(output_folder, exist_ok=True)

    for archivo in archivosDicom:
        try:
            dicom_data = pydicom.dcmread(archivo)

            for campo, valor in anon_values.items():
                if campo in dicom_data:
                    try:
                        dicom_data[campo].value = str(valor)
                    except:
                        dicom_data[campo].value = 0

            nombre_archivo = os.path.basename(archivo)
            nombre_anonimizado = f"anonimo_{nombre_archivo}"
            ruta_destino = os.path.join(output_folder, nombre_anonimizado)

            dicom_data.save_as(ruta_destino)

        except Exception as e:
            print(f"Error al procesar el archivo {archivo}: {e}")
            continue

    # Crear el ZIP
    zip_path = os.path.join(output_folder, 'archivos_anonimizados.zip')
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, _, files in os.walk(output_folder):
            for file in files:
                if file.endswith('.dcm'):
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.basename(file_path))

    return zip_path
