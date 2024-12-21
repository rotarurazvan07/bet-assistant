from abc import ABC, abstractmethod

class BaseTipper(ABC):
    def __init__(self, add_tip_callback):
         """
         Initialize common attributes for all Tippers.
         """
         self.add_tip_callback = add_tip_callback

    @abstractmethod
    def get_tips(self):
        """
        Abstract method to fetch tips.
        Subclasses must implement this method.
        """
        pass