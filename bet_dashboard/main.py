"""
Bet assistant, 2022
"""
from datetime import datetime
from statistics import mean

from flask import Flask, render_template, request

from bet_crawler.core.MatchStatistics import Score, Probability
from bet_framework.DatabaseManager import DatabaseManager
from bet_framework.utils import get_fav_dc, analyze_betting_predictions, get_value_bet

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/tipper', methods=["GET", "POST"])
def tipper():
    # Get start and end dates from the request, if provided
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    min_confidence = request.args.get('min_confidence', default=0)
    min_score_tip_percent = request.args.get('min_score_tip_percent', default=51)
    min_scores_no = request.args.get('min_scores_no', default=2)

    # Convert string dates to datetime objects
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None

    match_list = db_manager.fetch_matches()
    match_list = [match for match in match_list if len(match.statistics.tips) > 0]

    # Filter match_tips_list based on the date range
    filtered_match_list = []
    for match in match_list:
        if start_date and match.datetime.date() < start_date:
            continue
        if end_date and match.datetime.date() > end_date:
            continue
        if match.datetime <= datetime.now():
            continue
        match.statistics.tips = [tip for tip in match.statistics.tips if tip.confidence >= float(min_confidence)]
        if len(match.statistics.tips) == 0:
            continue

        # sort by reverse confidence of tips
        match.statistics.tips.sort(key=lambda x:x.confidence, reverse=True)
        filtered_match_list.append(match)

    filtered_match_list.sort(
        key=lambda match: (
            len(set(tip.source for tip in match.statistics.tips)),  # 1. Number of unique sources
            sum(
                max(tip.confidence for tip in match.statistics.tips if tip.source == source)
                for source in set(tip.source for tip in match.statistics.tips)
            ) / len(set(tip.source for tip in match.statistics.tips)) if match.statistics.tips else 0  # 2. Mean of max confidence per source
        ),
        reverse=True  # Reverse applies to the whole tuple sorting
    )

    # get match analysis
    analysis = []
    for match in filtered_match_list[:]:  # use slicing to avoid iteration issues while removing items
        prediction = '\n'.join(analyze_betting_predictions(match.statistics.scores, int(min_score_tip_percent), int(min_scores_no)))
        if prediction == '' or prediction == 'No predictions available for analysis.':
            filtered_match_list.remove(match)
            continue
        analysis.append(prediction)
        match.datetime = match.datetime.strftime('%Y-%m-%d %H:%M')
    filtered_match_list = [match.to_dict() for match in filtered_match_list]
    # Render the template with filtered match_tips_list
    return render_template('tipper.html', matches=filtered_match_list, analysis=analysis)


@app.route('/value_finder', methods=["GET", "POST"])
def value_finder():
    # Get start and end dates from the request, if provided
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    match_value_threshold = request.args.get('value_threshold')
    fav_min_dc_prob = request.args.get('dc_prob')

    # Convert string dates to datetime objects
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None

    value_matches_list = db_manager.fetch_matches()
    # Filter match_tips_list based on the date range
    filtered_value_matches_list = []
    for match in value_matches_list:
        if start_date and match.datetime.date() < start_date:
            continue
        if end_date and match.datetime.date() > end_date:
            continue
        if match.datetime <= datetime.now():
            continue
        filtered_value_matches_list.append(match)

    # Filter by threshold
    if match_value_threshold:
        filtered_value_matches_list = [match for match in filtered_value_matches_list if match.value >= int(match_value_threshold)]

    # calculate mean of scores and probabilities
    for match in filtered_value_matches_list:
        match.statistics.scores = Score(None, mean([sc.home for sc in match.statistics.scores]),
                                                     mean([sc.away for sc in match.statistics.scores]))
        match.statistics.probabilities = Probability(None, mean([pb.home for pb in match.statistics.probabilities]),
                                                                  mean([pb.draw for pb in match.statistics.probabilities]),
                                                                  mean([pb.away for pb in match.statistics.probabilities]))

    # Filter by fav_min_dc_prob
    if fav_min_dc_prob:
        filtered_value_matches_list = [match for match in filtered_value_matches_list if get_fav_dc(match) >= int(fav_min_dc_prob)]

    # sort by value
    filtered_value_matches_list.sort(key=lambda x:x.value, reverse=True)
    # get match analysis
    analysis = []
    for match in filtered_value_matches_list:
        analysis.append(get_value_bet(match.statistics.scores))

    return render_template('value_finder.html', matches=filtered_value_matches_list, analysis=analysis)


if __name__ == "__main__":
    db_manager = DatabaseManager()

    app.run(debug=False, host="192.168.100.27", port=5000)
