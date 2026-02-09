import numpy as np
from .base import AIPluginBase

class AIPocPlugin(AIPluginBase):

    def load(self):
        # Simula carga de modelo
        return True

    def predict(self, volume):
        """
        volume: np.ndarray (Z, H, W)
        """
        return {
            "status": "ok",
            "type": "POC",
            "slices": int(volume.shape[0]),
            "mean_intensity": float(np.mean(volume)),
            "message": "Inferencia simulada (sin modelo real)"
        }
