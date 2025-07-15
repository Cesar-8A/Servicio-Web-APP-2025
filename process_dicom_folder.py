# process_dicom_folder.py
import pydicom
from collections import defaultdict
from flask import current_app as app  # Use current_app instead of importing app directly

def process_dicom_folder(directory):
    """Procesa un directorio de archivos DICOM y devuelve un diccionario con la información."""
    dicom_series = defaultdict(lambda: {
        "ruta_archivos": [],
        "paciente": None,
        "tipo": None,
        "dimensiones": None,
        "RescaleSlope": 1,
        "RescaleIntercept": 1,
        "ImagePositionPatient": 1,
        "ImageOrientationPatient": [],
        "PixelSpacing": 0,
        "SliceThickness": 0,
        "slices": [],
        "Anonimize": {
            'PatientName': 'Nombre del paciente',
            'PatientID': 'ID del paciente',
            'PatientBirthDate': 'Fecha de nacimiento del paciente',
            'PatientSex': 'Sexo del paciente',
            'PatientAge': 'Edad del paciente',
            'StudyDate': 'Fecha del estudio',
            'StudyTime': 'Hora del estudio',
            'AccessionNumber': 'Número de acceso',
            'ReferringPhysicianName': 'Nombre del médico derivador',
            'MedicalRecordLocator': 'Número de historia clínica',
            'InstitutionName': 'Nombre de la institución',
            'InstitutionAddress': 'Dirección de la institución',
            'StudyDescription': 'Descripción del estudio',
            'SeriesDescription': 'Descripción de la serie',
            'OperatorName': 'Nombre del operador',
            'SeriesNumber': 'Número de la serie',
            'InstanceNumber': 'Número de la instancia',
        }
    })

    for file in directory:
        try:
            dicom_data = pydicom.dcmread(file, stop_before_pixels=False, force=True)
            study_id = dicom_data.StudyInstanceUID
            series_id = dicom_data.SeriesInstanceUID
            unique_id = f"{study_id}-{series_id}"

            paciente_nombre = dicom_data.PatientName if 'PatientName' in dicom_data else "Desconocido"
            
            series = dicom_series[unique_id]
            series["ruta_archivos"].append(file)
            series["paciente"] = paciente_nombre
            series["dimensiones"] = (len(series["ruta_archivos"]), dicom_data.Rows, dicom_data.Columns)
            series["RescaleSlope"] = dicom_data.RescaleSlope
            series["RescaleIntercept"] = dicom_data.RescaleIntercept
            series["ImagePositionPatient"] = dicom_data.ImagePositionPatient
            series["PixelSpacing"] = dicom_data.PixelSpacing  
            series["SliceThickness"] = dicom_data.get("SliceThickness", 1)

            anon = series["Anonimize"]
            anon['PatientName'] = dicom_data.PatientName
            anon['PatientID'] = dicom_data.PatientID 
            anon['PatientBirthDate'] = dicom_data.PatientBirthDate 
            anon['PatientSex'] = dicom_data.PatientSex 
            anon['PatientAge'] = dicom_data.PatientAge 
            anon['StudyDate'] = dicom_data.StudyDate 
            anon['StudyTime'] = dicom_data.StudyTime 
            anon['AccessionNumber'] = dicom_data.AccessionNumber 
            anon['ReferringPhysicianName'] = dicom_data.ReferringPhysicianName 
            anon['MedicalRecordLocator'] = dicom_data.MedicalRecordLocator 
            anon['InstitutionName'] = dicom_data.InstitutionName 
            anon['InstitutionAddress'] = dicom_data.InstitutionAddress 
            anon['StudyDescription'] = dicom_data.StudyDescription 
            anon['SeriesDescription'] = dicom_data.SeriesDescription 
            anon['OperatorName'] = dicom_data.OperatorName 
            anon['SeriesNumber'] = dicom_data.SeriesNumber 
            anon['InstanceNumber'] = dicom_data.InstanceNumber 

            series["tipo"] = "3D" if len(series["ruta_archivos"]) > 1 else "2D"
        
        except Exception:
            continue

    app.config['dicom_series'] = dicom_series.copy()
    return dicom_series
