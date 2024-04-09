import inspect
import os
from datetime import datetime

import xlsxwriter

CURRENT_TIME = datetime.now()


def export_matches(match_list):
    # If folder doesn't exist, then create it.
    if not os.path.isdir("output"):
        os.makedirs("output")
    # Create an Excel spreadsheet in the directory where the script is called
    workbook = xlsxwriter.Workbook('output/Values-' + str(CURRENT_TIME.date()) +
                                   "_" + str(CURRENT_TIME.time().hour) +
                                   "-" + str(CURRENT_TIME.time().minute) + '.xlsx')
    worksheet = workbook.add_worksheet()
    headers = ["Home", "Away", "Day", "Hour", "Home Points", "Away Points", "Home Form", "Away Form",
               "Match Value", "1x2 % Prediction", "Forebet Score"]
    for column, header in enumerate(headers):
        worksheet.write(0, column, header)

    match_list.sort(key=lambda x: x.get_match_value(), reverse=True)

    for match_no, match in enumerate(match_list):
        for column, data in enumerate(match.get_match_data()):
            worksheet.write(match_no + 1, column, data)

    workbook.close()


def log(message):
    func = inspect.currentframe().f_back.f_code
    print("%s: %s" % (func.co_name, message))
