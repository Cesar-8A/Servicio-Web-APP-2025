import os

# Absolute path to the project root (parent of this app/ package).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    """Base configuration shared by all environments."""

    # --- Security ---
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SECRET_KEY = os.environ.get('WTF_CSRF_SECRET_KEY', SECRET_KEY)

    # --- Upload directories (absolute paths) ---
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    UPLOAD_FOLDER_NRRD = os.path.join(BASE_DIR, 'upload_nrrd')
    ANONIMIZADO_FOLDER = os.path.join(BASE_DIR, 'anonimizado')

    # --- Segmentation ---
    SEGMENTATION_COLORS = ['#00FFFF', '#ADFF2F', '#FF8C00', '#FF00FF', '#FFD700']

    # --- Ports ---
    BOKEH_PORT = int(os.environ.get('BOKEH_PORT', 5010))
    FLASK_RUN_PORT = int(os.environ.get('FLASK_RUN_PORT', 5001))

    # --- AI Plugin ---
    # Override with env var to point to the correct Conda environment on each machine.
    AI_PYTHON_EXECUTABLE = os.environ.get(
        'AI_PYTHON_EXECUTABLE',
        r'C:\Users\jesus\anaconda3\envs\medaimg\python.exe',
    )


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    # In production these MUST come from the environment — no fallback.
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')
    WTF_CSRF_SECRET_KEY = os.environ.get('WTF_CSRF_SECRET_KEY')


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_SECRET_KEY = 'test-csrf-key'


_config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
}


def get_config(config_name=None):
    """Return the config class for *config_name* (defaults to FLASK_ENV or 'development')."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    return _config_map.get(config_name, DevelopmentConfig)
