"""
Bet assistant, 2022
"""
import os

import pandas as pd
from flask import Flask, render_template, jsonify

from src.ValueFinder import ValueFinder
from src.Tipper import Tipper
from src.utils import export_matches,export_tips

app = Flask(__name__)
value_finder = ValueFinder()
tipper = Tipper()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/fetch_cached_match_value_data')
def fetch_cached_match_value_data():
    df = pd.read_excel(os.path.join("data", "Values.xlsx")).fillna("")
    print(str(jsonify(df.to_dict(orient='records'))))
    return jsonify(df.to_dict(orient='records'))


@app.route('/fetch_cached_tips_data')
def fetch_cached_tips_data():
    df = pd.read_excel(os.path.join("data", "Tips.xlsx")).fillna("")
    print(str(jsonify(df.to_dict(orient='records'))))
    return jsonify(df.to_dict(orient='records'))


@app.route('/start_value_finder')
def start_value_finder():
    value_finder.execution = 1
    value_finder.find_value_matches()

    return jsonify("OK")


@app.route('/start_tips_finder')
def start_tips_finder():
    tipper.execution = 1
    tipper.get_tips()

    return jsonify("OK")


@app.route('/fetch_match_value_progress')
def fetch_match_value_progress():
    data = {"x": value_finder._scanned_matches, "y": value_finder._matches_to_scan}

    return jsonify(data)


@app.route('/fetch_tips_progress')
def fetch_tips_progress():
    data = {"x": tipper._searched_tips, "y": tipper._tips_to_search}

    return jsonify(data)


@app.route('/generate_data_for_match_value_table')
def generate_data_for_match_value_table():
    data_for_table = []
    for match in value_finder.matches:
        match_data = match.get_match_data()
        data_for_table.append(
            {"Home": match_data[0], "Away": match_data[1], "Day": match_data[2],
             "Hour": match_data[3], "Home Points": match_data[4], "Away Points": match_data[5],
             "Home Form": match_data[6], "Away Form": match_data[7], "Match Value": match_data[8],
             "1x2 % Prediction": match_data[9], "Forebet Score": match_data[10], "Odds": match_data[11], }
        )
    data_for_table = sorted(data_for_table, key=lambda x: x['Match Value'], reverse=True)
    if value_finder.execution:
        return jsonify(data_for_table)
    else:
        export_matches(value_finder.matches)
        return jsonify("1x2")


@app.route('/generate_data_for_tips_table')
def generate_data_for_tips_table():
    data_for_table = []
    for tip in tipper.tips:
        tip_data = tip.get_tip_data()
        data_for_table.append(
            {"Match": tip_data[0], "Time": tip_data[1], "Tip": tip_data[2],
             "Confidence (out of 3)": tip_data[3], "Source": tip_data[4], "Odds": tip_data[5]}
        )
    data_for_table = sorted(data_for_table, key=lambda x: x['Confidence (out of 3)'], reverse=True)
    if tipper.execution:
        return jsonify(data_for_table)
    else:
        export_tips(tipper.tips)
        return jsonify("1x2")


if __name__ == "__main__":
    app.run(debug=True, host='192.168.0.129', port=5000)
