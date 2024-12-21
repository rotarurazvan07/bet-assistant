"""
Bet assistant, 2022
"""
from datetime import datetime

from flask import Flask, render_template, jsonify, request

from bet_framework.DatabaseManager import DatabaseManager

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/fetch_match_data')
def fetch_tips_data():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else None
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else None

    tips_data = db_manager.fetch_match_data(start_date, end_date)
    return tips_data


@app.route('/analyse_data')
def analyse_data():
    try:
        db_manager.analyse_data()
        response = {"status": "success"}
    except Exception as e:
        response = {"status": "error", "message": str(e)}

    return jsonify(response)


if __name__ == "__main__":
    db_manager = DatabaseManager()

    app.run(debug=False, port=5000)
