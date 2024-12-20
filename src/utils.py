import inspect
import os
from datetime import datetime

# import xlsxwriter

CURRENT_TIME = datetime.now()


def fractional_to_decimal_odds(fractional_odds):
    numerator, denominator = map(int, fractional_odds.split('/'))
    decimal_odds = numerator / denominator + 1
    return round(decimal_odds, 2)


def export_matches(match_list):
    # If folder doesn't exist, then create it.
    if not os.path.isdir("data"):
        os.makedirs("data")
    # Create an Excel spreadsheet in the directory where the script is called
    workbook = xlsxwriter.Workbook('data/Values.xlsx')
    worksheet = workbook.add_worksheet()
    headers = ["Home", "Away", "Day", "Hour", "Home Points", "Away Points", "Home Form", "Away Form",
               "Match Value", "1x2 % Prediction", "Forebet Score", "Odds"]
    for column, header in enumerate(headers):
        worksheet.write(0, column, header)

    match_list.sort(key=lambda x: x.get_match_value(), reverse=True)

    for match_no, match in enumerate(match_list):
        for column, data in enumerate(match.get_match_data()):
            worksheet.write(match_no + 1, column, data)

    workbook.close()


def export_tips(tips_list):
    # If folder doesn't exist, then create it.
    if not os.path.isdir("data"):
        os.makedirs("data")
    # Create an Excel spreadsheet in the directory where the script is called
    workbook = xlsxwriter.Workbook('data/Tips.xlsx')
    worksheet = workbook.add_worksheet()
    headers = ["Match", "Time", "Tip", "Confidence (out of 3)", "Source", "Odds"]
    for column, header in enumerate(headers):
        worksheet.write(0, column, header)

    tips_list.sort(key=lambda x: (-x.confidence, x.match_name))

    for tip_no, tip in enumerate(tips_list):
        for column, data in enumerate(tip.get_tip_data()):
            worksheet.write(tip_no + 1, column, data)

    workbook.close()


def log(message):
    func = inspect.currentframe().f_back.f_code
    print("%s: %s" % (func.co_name, message))
