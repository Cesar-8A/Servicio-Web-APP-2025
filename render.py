# render_utils.py
import pyvista as pv
import panel as pn
import numpy as np
from flask import current_app as app

def create_render():
    panel_column = pn.Column()

    volume_bone = ((app.config['Image'] > 175) * 1).astype(np.int16)
    volume_skin = (((app.config['Image'] > -200) & (app.config['Image'] < 0)) * 1).astype(np.int16)
    unique_id = app.config["unique_id"]

    origin = app.config['dicom_series'][unique_id]["ImagePositionPatient"]
    spacing = (
        app.config['dicom_series'][unique_id]["SliceThickness"],
        app.config['dicom_series'][unique_id]["PixelSpacing"][0],
        app.config['dicom_series'][unique_id]["PixelSpacing"][1],
    )

    grid_bone = pv.ImageData()
    grid_bone.dimensions = np.array(volume_bone.shape) + 1
    grid_bone.origin = origin
    grid_bone.spacing = spacing
    grid_bone.cell_data["values"] = volume_bone.flatten(order="F")
    grid_bone = grid_bone.cell_data_to_point_data()
    surface_bone = grid_bone.contour([0.5])

    grid_skin = pv.ImageData()
    grid_skin.dimensions = np.array(volume_skin.shape) + 1
    grid_skin.origin = origin
    grid_skin.spacing = spacing
    grid_skin.cell_data["values"] = volume_skin.flatten(order="F")
    grid_skin = grid_skin.cell_data_to_point_data()
    surface_skin = grid_skin.contour([0.5])

    plotter = pv.Plotter(off_screen=True)
    plotter.set_background("black")
    plotter.add_mesh(surface_bone, color="white", smooth_shading=True, ambient=0.3, specular=0.4, specular_power=10)
    skin_actor = plotter.add_mesh(surface_skin, color="peachpuff", opacity=0.5, name="skin", smooth_shading=True)

    plotter.view_isometric()
    plotter.show_axes()

    panel_vtk = pn.pane.VTK(plotter.ren_win, width=400, height=500)

    slider = pn.widgets.FloatSlider(name="Opacidad de la piel", start=0.0, end=1.0, step=0.05, value=0.5)

    def update_opacity(event):
        skin_actor.GetProperty().SetOpacity(event.new)
        panel_vtk.param.trigger('object')

    slider.param.watch(update_opacity, 'value')

    panel_column[:] = [panel_vtk, slider]

    # Return all the state components in a dict
    return {
        "plotter": plotter,
        "skin_actor": skin_actor,
        "slider": slider,
        "grid_dicom": grid_skin,
        "panel_column": panel_column,
        "panel_vtk": panel_vtk
    }
