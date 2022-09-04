"""
Bet assistant, 2022
"""
from ValueFinder import ValueFinder, export_matches
from utils import init_time

CHROME_PATH = ""
CHROMEDRIVER_PATH = ""

if __name__ == "__main__":
    init_time()

    value_finder = ValueFinder(CHROME_PATH, CHROMEDRIVER_PATH)
    matches = value_finder.get_values()
    export_matches(matches)
