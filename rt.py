# rt_utils.py
import numpy as np
import pyvista as pv
import panel as pn
from flask import current_app as app

def add_RT_to_plotter(render_state):
    """
    Agrega una máscara RT al plotter existente y actualiza el panel.
    `render_state` debe ser el diccionario retornado por create_render() y almacenado en app.config["render_state"].
    """
    plotter = render_state["plotter"]
    panel_vtk = render_state["panel_vtk"]
    skin_actor = render_state["skin_actor"]
    slider = render_state["slider"]
    grid_dicom = render_state["grid_dicom"]
    panel_column = render_state["panel_column"]

    if plotter is None:
        print("❌ No hay plotter activo.")
        return

    if "RT" not in app.config:
        print("❌ No hay RT cargado.")
        return

    # --- Transformar el volumen RT ---
    RT_Image = np.flip(app.config['RT'], axis=(0, 1, 2))  # Voltear para alinear con DICOM
    RT_Image = RT_Image.transpose(2, 0, 1)  # (X, Y, Z) → (Z, X, Y)

    # Guardar RT 2D para cortes
    RT_2D = np.flip(app.config['RT'], axis=2)
    app.config['RT_aligned'] = RT_2D

    # --- Crear grid de segmentación ---
    rt_grid = pv.ImageData()
    rt_grid.dimensions = np.array(RT_Image.shape) + 1
    rt_grid.origin = grid_dicom.origin
    rt_grid.spacing = grid_dicom.spacing

    rt_grid.cell_data["values"] = (RT_Image > 1).astype(np.uint8).flatten(order="F")
    rt_grid = rt_grid.cell_data_to_point_data()
    surface = rt_grid.contour([0.5])

    # --- Agregar malla al plotter ---
    mask_actor = plotter.add_mesh(
        surface,
        color="red",
        opacity=0.5,
        smooth_shading=True,
        specular=0.3
    )

    # --- Callback para slider de opacidad de piel ---
    def update_opacity(event):
        skin_actor.GetProperty().SetOpacity(event.new)
        panel_vtk.param.trigger('object')

    slider.param.watch(update_opacity, 'value')

    # --- Toggle de visibilidad de la máscara ---
    toggle_button = pn.widgets.Toggle(name='Mostrar/Ocultar máscara', button_type='danger', value=True)

    def toggle_mask_visibility(event):
        if event.new:
            mask_actor.GetProperty().SetOpacity(0.5)
        else:
            mask_actor.GetProperty().SetOpacity(0.0)

    toggle_button.param.watch(toggle_mask_visibility, 'value')

    # --- Actualizar Panel ---
    plotter.render()
    panel_vtk.object = plotter.ren_win
    panel_column.append(toggle_button)

    return panel_column
