from bet_crawler.value_finder.impl.ForebetFinder import ForebetFinder
from bet_crawler.value_finder.impl.VitibetFinder import VitibetFinder


class ValueFinder:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def _add_value_match_callback(self, match):
        self.db_manager.add_match(match)

    def get_value_matches(self):
        value_finders = [
            ForebetFinder(self._add_value_match_callback),
            VitibetFinder(self._add_value_match_callback),
        ]

        for value_finder in value_finders:
            value_finder.get_value_matches()
