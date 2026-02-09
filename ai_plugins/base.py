from abc import ABC, abstractmethod

class AIPluginBase(ABC):
    """
    Interfaz base para plugins de IA.
    Todos los modelos deben implementar esta clase.
    """

    @abstractmethod
    def load(self):
        """
        Carga el modelo en memoria.
        """
        pass

    @abstractmethod
    def predict(self, volume):
        """
        Ejecuta inferencia sobre un volumen 3D (NumPy).
        Retorna un diccionario JSON serializable.
        """
        pass
