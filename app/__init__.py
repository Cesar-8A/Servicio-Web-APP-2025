import os

import pyvista as pv
import panel as pn
from flask import Flask, session
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf

from .config import get_config, BASE_DIR

# Extension instance created here so it can be imported by future Blueprint modules
# without triggering a circular import.  It is bound to the app inside create_app().
csrf = CSRFProtect()


def create_app(config_name=None):
    """
    Application Factory.

    Creates and returns a fully configured Flask instance.
    All environment-specific settings come from app/config.py.
    """
    app = Flask(
        __name__,
        # Resolve templates/ and static/ relative to the project root, not this package.
        template_folder=os.path.join(BASE_DIR, 'templates'),
        static_folder=os.path.join(BASE_DIR, 'static'),
    )

    # --- Configuration ---
    app.config.from_object(get_config(config_name))

    # --- Extensions ---
    csrf.init_app(app)

    # --- PyVista (must be off-screen on a headless server) ---
    pv.OFF_SCREEN = True
    pv.global_theme.jupyter_backend = 'static'

    # --- Panel / Bokeh (VTK embedding) ---
    pn.extension('vtk')

    # --- Upload directories ---
    for folder in [
        app.config['UPLOAD_FOLDER'],
        app.config['UPLOAD_FOLDER_NRRD'],
        app.config['ANONIMIZADO_FOLDER'],
    ]:
        os.makedirs(folder, exist_ok=True)

    # --- Template globals ---
    @app.context_processor
    def inject_user():
        return {
            'user_logged_in': session.get('user_logged_in', False),
            'user_initials': session.get('user_initials', ''),
            'csrf_token': generate_csrf,
        }

    return app
