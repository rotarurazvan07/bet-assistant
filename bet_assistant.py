"""
Bet assistant, 2022
"""
import asyncio
from datetime import datetime

from flask import Flask, render_template, jsonify, request

from src.DatabaseManager import DatabaseManager
from src.Tipper import Tipper
from src.ValueFinder import ValueFinder

app = Flask(__name__)
value_finder = ValueFinder()


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


@app.route('/generate_data')
def generate_data():
    # Simulate data generation process
    db_manager.reset_db()
    try:
        # Add your data generation logic here
        tipper.get_tips()
        # Example response
        response = {"status": "success"}
    except Exception as e:
        response = {"status": "error", "message": str(e)}

    return jsonify(response)


@app.route('/analyse_data')
def analyse_data():
    try:
        db_manager.analyse_data()
        response = {"status": "success"}
    except Exception as e:
        response = {"status": "error", "message": str(e)}

    return jsonify(response)


if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    db_manager = DatabaseManager()
    tipper = Tipper(db_manager)
    # db_manager.analyse_data()
    app.run(debug=True, host='192.168.0.129', port=5000)
