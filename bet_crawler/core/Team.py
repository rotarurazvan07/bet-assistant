WIN_WEIGHT = 3
DRAW_WEIGHT = 1
LOSE_WEIGHT = -3
LEAGUE_POINTS_WEIGHT = 1

class TeamStatistics:
    def __init__(self, avg_corners, avg_offsides, avg_gk_saves, avg_yellow_cards, avg_fouls, avg_tackles,
                 avg_scored, avg_conceded, avg_shots_on_target, avg_possession):
        self.avg_corners = avg_corners
        self.avg_offsides = avg_offsides
        self.avg_gk_saves = avg_gk_saves
        self.avg_yellow_cards = avg_yellow_cards
        self.avg_fouls = avg_fouls
        self.avg_tackles = avg_tackles
        self.avg_scored = avg_scored
        self.avg_conceded = avg_conceded
        self.avg_shots_on_target = avg_shots_on_target
        self.avg_possession = avg_possession

class Team:
    def __init__(self, name, league_points, form, statistics):
        self.name = name
        self.league_points = league_points
        self.form = form  # list containing latest matches results
        self.statistics = statistics
    # Team value is represented by an integer by adding
    # the league points and the obtained points minus the losses
    # in the last matches (recent form)
    def get_team_score(self):
        form_value = WIN_WEIGHT * self.form.count("W") + \
                     DRAW_WEIGHT * self.form.count("D") + \
                     LOSE_WEIGHT * self.form.count("L")
        return form_value + LEAGUE_POINTS_WEIGHT * self.league_points

    def to_dict(self):
        return {
            "name": self.name,
            "league_points": self.league_points,
            "form": self.form,
            "statistics": self.statistics.__dict__ if self.statistics else None
        }
