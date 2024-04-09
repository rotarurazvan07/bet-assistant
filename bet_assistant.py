"""
Bet assistant, 2022
"""
from src.ValueFinder import ValueFinder
from src.utils import export_matches
# from src.Tipper import Tipper, export_tips

if __name__ == "__main__":
    # TODO - create a GUI to add the CHROME paths
    #  then to select either values and tips
    #  and keep track of progress then show where the excel files are
    value_finder = ValueFinder()
    matches = value_finder.find_value_matches()
    export_matches(matches)

    # tipper = Tipper()
    # tips = tipper.get_tips()
    # export_tips(tips)
