# -*- coding: utf-8 -*-
import os, sys, time, json, argparse, warnings
import torch
import torchio as tio
import numpy as np
import SimpleITK as sitk
import nibabel as nib
from monai.networks.nets import SwinUNETR
from monai.inferers import sliding_window_inference

warnings.filterwarnings("ignore")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--weights", required=True)
    args = parser.parse_args()

    sys.stdout = open(os.devnull, 'w')
    result = {"status": "error", "message": "Unknown error", "mask_path": None}

    try:
        os.makedirs(args.out_dir, exist_ok=True)

        # 1. LECTURA NATIVA ESTRICTA
        # Obtenemos el "molde" original del paciente
        dicom_dir = args.input if os.path.isdir(args.input) else os.path.dirname(args.input)
        reader = sitk.ImageSeriesReader()
        dicom_names = reader.GetGDCMSeriesFileNames(dicom_dir)
        reader.SetFileNames(dicom_names)
        native_sitk = reader.Execute()

        nifti_in_path = os.path.join(args.out_dir, "input_vol_native.nii.gz")
        sitk.WriteImage(native_sitk, nifti_in_path)

        # 2. PREPARACIÓN PARA LA IA (TorchIO)
        subject = tio.Subject(mri=tio.ScalarImage(nifti_in_path))
        spatial_transform = tio.Compose([
            tio.Resample(1.0),
            tio.CropOrPad((160, 192, 160))
        ])
        subj_spat = spatial_transform(subject)
        
        intensity_transform = tio.RescaleIntensity(out_min_max=(0, 1), percentiles=(0.1, 99.9))
        subj_full = intensity_transform(subj_spat)

        # 3. INFERENCIA RED NEURONAL
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = SwinUNETR(in_channels=1, out_channels=8, feature_size=24, use_checkpoint=False).to(device)
        model.load_state_dict(torch.load(args.weights, map_location=device))
        model.eval()

        input_tensor = subj_full.mri.data.unsqueeze(0).to(device)
        with torch.no_grad():
            logits = sliding_window_inference(input_tensor, roi_size=(96,96,96), sw_batch_size=4, predictor=model, overlap=0.5, mode="gaussian")

        # Obtenemos el array limpio
        mask_array = torch.argmax(logits, dim=1, keepdim=True).to(torch.uint8)[0, 0].cpu().numpy()

        # 4. SOLUCIÓN AL BUG: PROYECCIÓN MATEMÁTICA AL ESPACIO NATIVO
        # Pegamos el array a las coordenadas distorsionadas que dejó TorchIO
        pred_nifti = nib.Nifti1Image(mask_array, subj_spat.mri.affine)
        temp_mask_path = os.path.join(args.out_dir, "temp_mask.nii.gz")
        nib.save(pred_nifti, temp_mask_path)

        # Usamos SimpleITK para estirar y acomodar esta máscara usando como molde al paciente original
        pred_sitk = sitk.ReadImage(temp_mask_path)
        resampler = sitk.ResampleImageFilter()
        resampler.SetReferenceImage(native_sitk) # <- El secreto está aquí
        resampler.SetInterpolator(sitk.sitkNearestNeighbor)
        resampler.SetDefaultPixelValue(0)
        final_mask_sitk = resampler.Execute(pred_sitk)

        # 5. GUARDADO SEGURO
        mask_out_path = os.path.join(args.out_dir, f"MASK_FINAL_{int(time.time())}.nii.gz")
        sitk.WriteImage(final_mask_sitk, mask_out_path)

        result["status"] = "success"
        result["mask_path"] = mask_out_path

    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)

    finally:
        sys.stdout = sys.__stdout__
        print(json.dumps(result))

if __name__ == '__main__':
    main()