from abc import abstractmethod

from bet_crawler.core.BaseCrawler import BaseCrawler


class BaseTipper(BaseCrawler):
    def __init__(self, add_tip_callback):
         """
         Initialize common attributes for all Tippers.
         """
         super().__init__()
         self.add_tip_callback = add_tip_callback

    @abstractmethod
    def get_tips(self):
        """
        Abstract method to fetch tips.
        Subclasses must implement this method.
        """
        pass