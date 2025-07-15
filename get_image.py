# image_utils.py
import numpy as np
import matplotlib.pyplot as plt
import numpy.ma as ma
import io
from flask import current_app as app, send_file

def generate_slice_image(view, layer):
    image = app.config['Image']
    unique_id = app.config["unique_id"]

    # Rescale
    slope = app.config['dicom_series'][unique_id]["RescaleSlope"]
    intercept = app.config['dicom_series'][unique_id]["RescaleIntercept"]
    image = image * slope + intercept

    # Spacing
    slice_thickness = app.config['dicom_series'][unique_id]["SliceThickness"]
    pixel_spacing = app.config['dicom_series'][unique_id]["PixelSpacing"]

    # Optional segmentation
    rt = app.config.get('RT_aligned')
    show_seg = rt is not None

    if view == 'axial':
        slice_img = image[layer, :, :]
        seg_slice = np.flip(rt[:, :, layer], axis=0) if show_seg else None
        aspect_ratio = pixel_spacing[1] / pixel_spacing[0]
    elif view == 'sagital':
        slice_img = image[:, layer, :]
        seg_slice = np.flip(rt[:, layer, :], axis=0) if show_seg else None
        aspect_ratio = slice_thickness / pixel_spacing[0]
    elif view == 'coronal':
        slice_img = image[:, :, layer]
        seg_slice = np.flip(rt[layer, :, :], axis=0) if show_seg else None
        aspect_ratio = slice_thickness / pixel_spacing[1]
    else:
        return None, "Vista no válida", 400

    if show_seg:
        slice_img = np.flip(slice_img, axis=0)

    # Plot
    plt.figure(figsize=(6, 6))
    plt.imshow(slice_img, cmap='gray', aspect=aspect_ratio)
    plt.axis('off')

    if show_seg:
        flipped_seg = np.flip((seg_slice > 1).T)
        masked_seg = ma.masked_where(flipped_seg == 0, flipped_seg)
        plt.imshow(masked_seg, cmap='Reds', alpha=0.8, aspect=aspect_ratio, origin='lower', vmin=0, vmax=1)

    # Convert to PNG
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
    plt.close()
    buf.seek(0)
    return buf, None, 200
