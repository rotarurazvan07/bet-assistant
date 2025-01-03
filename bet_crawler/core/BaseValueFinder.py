from abc import abstractmethod

from bet_crawler.core.BaseCrawler import BaseCrawler


class BaseValueFinder(BaseCrawler):
    def __init__(self, add_value_match_callback):
         """
         Initialize common attributes for all ValueFinders.
         """
         super().__init__()
         self.add_value_match_callback = add_value_match_callback

    @abstractmethod
    def get_value_matches(self):
        """
        Abstract method to fetch matches.
        Subclasses must implement this method.
        """
        pass