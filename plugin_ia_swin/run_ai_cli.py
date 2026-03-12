# -*- coding: utf-8 -*-
"""
Microservicio CLI para Segmentación de Imagen Cerebral (NIfTI o DICOM).
Adaptado para ser llamado por un servidor web.
"""

import os
import time
import json
import argparse
import ants
import torch
import torchio as tio
import nibabel as nib
import warnings

from monai.networks.nets import SwinUNETR
from monai.inferers import sliding_window_inference
from torch.amp import autocast

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
#  CONFIGURACION DEL MODELO
# ─────────────────────────────────────────────
PATCH_SIZE    = (96, 96, 96)
FEATURE_SIZE  = 24

T1_KEYWORDS = [
    "t1", "mprage", "spgr", "bravo", "tfe", "flash",
    "3dfspgr", "ir-fspgr", "mp-rage", "t1w", "t1-weighted",
    "sagittal 3d", "t1_mpr", "t1_se", "t1_fl", "t1mprage"
]

def check_if_t1_nifti(filepath):
    name_lower = os.path.basename(filepath).lower()
    if any(k in name_lower for k in T1_KEYWORDS):
        return True, "nombre de archivo"
    try:
        img = nib.load(filepath)
        hdr = img.header
        desc = ""
        for field in ['descrip', 'aux_file', 'intent_name']:
            try:
                desc += str(hdr[field]).lower()
            except Exception:
                pass
        if any(k in desc for k in T1_KEYWORDS):
            return True, "header NIfTI"
    except Exception:
        pass
    return False, None

def check_if_t1_dicom(ds):
    fields_to_check = [
        getattr(ds, 'SeriesDescription', ''),
        getattr(ds, 'ProtocolName', ''),
        getattr(ds, 'SequenceName', ''),
        getattr(ds, 'ScanningSequence', ''),
        getattr(ds, 'ImageType', []),
        getattr(ds, 'ContrastBolusAgent', ''),
        getattr(ds, 'StudyDescription', ''),
    ]
    combined = " ".join(
        " ".join(f) if isinstance(f, (list, tuple)) else str(f)
        for f in fields_to_check
    ).lower()
    if any(k in combined for k in T1_KEYWORDS):
        return True, "tags DICOM"
    return False, None

def load_nifti(filepath):
    img = nib.load(filepath)
    shape = img.shape
    if len(shape) == 4 and shape[3] == 1:
        pass # Aceptable
    elif len(shape) != 3:
        raise ValueError(f"El archivo NIfTI tiene forma {shape}. Se requiere un volumen 3D.")
    is_t1, source = check_if_t1_nifti(filepath)
    return filepath, is_t1, source

def load_dicom_series(dcm_path, out_dir):
    import pydicom
    import SimpleITK as sitk

    folder = os.path.dirname(dcm_path)
    try:
        ref_ds = pydicom.dcmread(dcm_path, stop_before_pixels=True)
        ref_series_uid = getattr(ref_ds, 'SeriesInstanceUID', None)
        ref_study_uid  = getattr(ref_ds, 'StudyInstanceUID', None)
    except Exception as e:
        raise ValueError(f"No se pudo leer el archivo DICOM: {e}")

    all_dcm = [f for f in os.listdir(folder) if f.lower().endswith('.dcm') or f.lower().endswith('.ima')]
    if len(all_dcm) < 2:
        raise ValueError("Se necesitan múltiples cortes DICOM para reconstruir un volumen 3D.")

    series_files = []
    for fname in all_dcm:
        fpath = os.path.join(folder, fname)
        try:
            ds = pydicom.dcmread(fpath, stop_before_pixels=True)
            series_uid = getattr(ds, 'SeriesInstanceUID', None)
            study_uid  = getattr(ds, 'StudyInstanceUID', None)
            if ref_series_uid and series_uid == ref_series_uid:
                series_files.append(fpath)
            elif ref_study_uid and study_uid == ref_study_uid and not ref_series_uid:
                series_files.append(fpath)
        except Exception:
            continue

    if len(series_files) < 2:
        raise ValueError("Solo se encontraron 1 archivo de esta serie DICOM.")

    is_t1, source = check_if_t1_dicom(ref_ds)

    reader = sitk.ImageSeriesReader()
    reader.SetFileNames(sorted(series_files))
    sitk_img = reader.Execute()

    vol_shape = sitk_img.GetSize()
    if len(vol_shape) != 3 or vol_shape[2] < 2:
        raise ValueError("El volumen reconstruido no es 3D válido.")

    tmp_path = os.path.join(out_dir, f"_tmp_dicom_vol_{int(time.time())}.nii.gz")
    sitk.WriteImage(sitk_img, tmp_path)
    return tmp_path, is_t1, source

def pipeline_ants_single(img_path, mni_template, mni_mask):
    img = ants.image_read(img_path)
    img = ants.reorient_image2(img, orientation="RPI")
    img_n4 = ants.n4_bias_field_correction(img, shrink_factor=3)
    tx = ants.registration(fixed=mni_template, moving=img_n4, type_of_transform='AffineFast')
    mask_solid_patient = ants.apply_transforms(
        fixed=img_n4, moving=mni_mask, transformlist=tx['fwdtransforms'],
        whichtoinvert=[True], interpolator='nearestNeighbor'
    )
    img_stripped = img_n4 * mask_solid_patient
    img_cropped = ants.crop_image(img_stripped, mask_solid_patient)
    return ants.n4_bias_field_correction(img_cropped, shrink_factor=2)

dl_formatter = tio.Compose([
    tio.Resample(1.0),
    tio.RescaleIntensity(out_min_max=(0, 1), percentiles=(0.1, 99.9), masking_method=lambda x: x > 0),
    tio.CropOrPad((160, 192, 160), padding_mode=0)
])

def load_model(weights_path, device):
    model = SwinUNETR(in_channels=1, out_channels=8, feature_size=FEATURE_SIZE, use_checkpoint=False).to(device)
    model.load_state_dict(torch.load(weights_path, map_location=device))
    model.eval()
    return model

def run_inference(preprocessed_path, model, device, out_dir):
    filename = os.path.basename(preprocessed_path)
    mask_out_path = os.path.join(out_dir, filename.replace("DL_INF_", "MASK_"))

    subject = tio.Subject(mri=tio.ScalarImage(preprocessed_path))
    input_tensor = subject.mri.data.unsqueeze(0).to(device)

    with torch.no_grad():
        with autocast('cuda'):
            logits = sliding_window_inference(
                inputs=input_tensor, roi_size=PATCH_SIZE, sw_batch_size=4,
                predictor=model, overlap=0.5, mode="gaussian"
            )

    mask_tensor = torch.argmax(logits, dim=1, keepdim=True).cpu()
    mask_image  = tio.LabelMap(tensor=mask_tensor[0], affine=subject.mri.affine)
    mask_image.save(mask_out_path)
    return mask_out_path

def main():
    parser = argparse.ArgumentParser(description="Microservicio de Segmentacion IA SWIN-UNETR")
    parser.add_argument("--input", required=True, help="Ruta al archivo NIfTI o un archivo DICOM de la serie")
    parser.add_argument("--out_dir", required=True, help="Carpeta donde guardar la mascara resultante")
    parser.add_argument("--weights", required=True, help="Ruta al archivo best_swin_unetr_model.pth")
    args = parser.parse_args()

    # Silenciar prints estandar para asegurar que el output final JSON sea limpio
    import sys
    sys.stdout = open(os.devnull, 'w')

    result = {"status": "error", "message": "Unknown error", "mask_path": None}
    tmp_dicom_path = None
    temp_img_path = None

    try:
        if not os.path.exists(args.out_dir):
            os.makedirs(args.out_dir, exist_ok=True)

        ext = args.input.lower()
        if ext.endswith('.nii') or ext.endswith('.nii.gz'):
            nifti_path, is_t1, t1_source = load_nifti(args.input)
        elif ext.endswith('.dcm') or ext.endswith('.ima'):
            nifti_path, is_t1, t1_source = load_dicom_series(args.input, args.out_dir)
            tmp_dicom_path = nifti_path
        else:
            raise ValueError("Formato no soportado.")

        from nilearn import datasets
        mni_dataset  = datasets.fetch_icbm152_2009()
        mni_template = ants.image_read(mni_dataset['t1'])
        mni_mask     = ants.image_read(mni_dataset['mask'])

        base_name = f"study_{int(time.time())}"
        prep_out_path = os.path.join(args.out_dir, f"DL_INF_{base_name}.nii.gz")
        temp_img_path = os.path.join(args.out_dir, f"_temp_img_{base_name}.nii.gz")

        # ANTs
        img_ants = pipeline_ants_single(nifti_path, mni_template, mni_mask)
        ants.image_write(img_ants, temp_img_path)

        # TorchIO
        subject = tio.Subject(mri=tio.ScalarImage(temp_img_path))
        subject_dl = dl_formatter(subject)
        subject_dl.mri.save(prep_out_path)

        # Modelo
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = load_model(args.weights, device)

        # Inferencia
        mask_path = run_inference(prep_out_path, model, device, args.out_dir)

        # Exito
        result["status"] = "success"
        result["message"] = "Segmentacion completada"
        result["mask_path"] = mask_path

    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)

    finally:
        # Limpieza de temporales
        for tmp in [tmp_dicom_path, temp_img_path, prep_out_path]:
            if tmp and os.path.exists(tmp):
                try: os.remove(tmp)
                except: pass

        # Restaurar stdout y enviar el JSON al servidor web
        sys.stdout = sys.__stdout__
        print(json.dumps(result))

if __name__ == '__main__':
    main()