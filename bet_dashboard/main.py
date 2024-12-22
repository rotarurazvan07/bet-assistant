"""
Bet assistant, 2022
"""
from datetime import datetime

from flask import Flask, render_template, request

from bet_framework.DatabaseManager import DatabaseManager

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/tipper', methods=["GET", "POST"])
def tipper():
    # Get start and end dates from the request, if provided
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    # Convert string dates to datetime objects
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None

    match_tips_list = db_manager.fetch_tips_data()
    # Filter match_tips_list based on the date range
    filtered_match_tips_list = []
    for match_tips in match_tips_list:
        if start_date and match_tips.match_datetime.date() < start_date:
            continue
        if end_date and match_tips.match_datetime.date() > end_date:
            continue
        # sort by reverse confidence of tips
        match_tips.tips.sort(key=lambda x:x.confidence, reverse=True)
        filtered_match_tips_list.append(match_tips)

    filtered_match_tips_list.sort(
        key=lambda match: (
            len(set(tip.source for tip in match.tips)),  # 1. Number of unique sources
            sum(
                max(tip.confidence for tip in match.tips if tip.source == source)
                for source in set(tip.source for tip in match.tips)
            ) / len(set(tip.source for tip in match.tips)) if match.tips else 0  # 2. Mean of max confidence per source
        ),
        reverse=True  # Reverse applies to the whole tuple sorting
    )

    # Render the template with filtered match_tips_list
    return render_template('tipper.html', match_tips_list=filtered_match_tips_list)


@app.route('/value_finder', methods=["GET", "POST"])
def value_finder():
    # Get start and end dates from the request, if provided
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    # Convert string dates to datetime objects
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None

    value_matches_list = db_manager.fetch_value_matches_data()
    # Filter match_tips_list based on the date range
    filtered_value_matches_list = []
    for match in value_matches_list:
        if start_date and match.match_datetime.date() < start_date:
            continue
        if end_date and match.match_datetime.date() > end_date:
            continue
        filtered_value_matches_list.append(match)

    filtered_value_matches_list.sort(key=lambda x:x.match_value, reverse=True)

    return render_template('value_finder.html', matches=filtered_value_matches_list)

if __name__ == "__main__":
    db_manager = DatabaseManager()

    app.run(debug=False, port=5000)
