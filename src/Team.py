WIN_WEIGHT = 3
DRAW_WEIGHT = 1
LOSE_WEIGHT = -3
LEAGUE_POINTS_WEIGHT = 1


class Team:
    def __init__(self, name, league_points, form):
        self.name = name
        self.league_points = league_points
        self.form = form  # list containing latest matches results

    # Team value is represented by an integer by adding
    # the league points and the obtained points minus the losses
    # in the last matches (recent form)
    def get_team_score(self):
        form_value = WIN_WEIGHT * self.form.count("W") + \
                     DRAW_WEIGHT * self.form.count("D") + \
                     LOSE_WEIGHT * self.form.count("L")
        return form_value + LEAGUE_POINTS_WEIGHT * self.league_points
