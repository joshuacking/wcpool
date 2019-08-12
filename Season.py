from PoolDAO import PoolDAO
from datetime import datetime, timedelta



class Season:

    dao = PoolDAO()


    def __init__(self, season_id, now):
        self.retrieved = False
        self.season = {}
        self.id = season_id
        self.last_update = ""
        self.league = ""
        self.matches = {}
        self.results = []
        self.teams = {}
        self.year = ""
        self.week_override = ""
        self.global_now = now 
        
    def get_results(self, count=10):
        """Returns the most recent results"""
        season = self.retrieve()
        result_count = len(self.results)
        display_count = min(count, result_count) * -1

        return self.results[display_count:]

    def get_teams(self):
        """Returns the teams for this season"""
        season = self.retrieve()

        return self.teams

    def get_name(self):
        """Returns the name for this season"""
        season = self.retrieve()

        return self.year + " " + self.league

    def get_matches(self):
        """Returns the matches for this season"""
        season = self.retrieve()
        
        return self.matches

    def get_matches_by_date(self, date):
        """Returns the matches for a specific date for this season"""
        season = self.retrieve()
        
        # make sure date is valid
        date = date.replace("-", " ")
        try:
            game_date = datetime.strptime(date, "%Y %m %d")
        except Exception as e:
            print(e)
            raise Exception("Invalid date format. Use YYYY-MM-DD.")
        
        if date not in self.matches:
            raise Exception("No matches scheduled for " + date)
            
        return self.matches[date]

    def get_schedule_by_week(self, week_number):
        """Returns the matches for a specific date for this season"""
        season = self.retrieve()
        games = []
        week = "WEEK" + str(week_number)

        # if week is invalid, raise exception
        if not week in self.matches:
            raise Exception("No games scheduled.")
        
        return self.matches[week]
    
    def get_schedule_by_date(self, date):
        """Returns the matches for a specific date for this season"""
        season = self.retrieve()
        games = []

        # which week is it?
        d = datetime.strptime(date, '%Y-%m-%d')
        t = timedelta((12 - d.weekday()) % 7)
        next_saturday = ((d + t).strftime('%Y-%m-%d'))
        week = self.find_week(next_saturday)

        # if week is invalid, raise exception
        if not week in self.matches:
            raise Exception("No games scheduled.")
        
        return self.matches[week]

    
    def get_teams_by_division(self):
        """Returns the teams for this season"""
        season = self.retrieve()
        response = {}

        for team_code in self.teams:
            if self.teams[team_code]['DIVISION'] not in response:
                response[self.teams[team_code]['DIVISION']] = []

            team = {}
            team['name'] = self.teams[team_code]['NAME']
            team['code'] = team_code
            response[self.teams[team_code]['DIVISION']].append(team)
            
        return response

    def get_league_teams(self):
        self.retrieve()
        
        result = {}

        for team in self.teams:
            if self.teams[team]['LEAGUE'] == self.league:
                result[team] = self.teams[team]

        return result
    
    def get_team(self, season_id, team_id):
        """Return team and record for a specific team"""
        season = self.retrieve()
        team_id = team_id.upper()
            
        
        if team_id not in self.teams:
            raise Exception('Team not found (' + team_id + ')')
                            
        return self.teams[team_id]

    def add_result(self, result_type, game_date, team1, team2, score):
        season = self.retrieve()
        
        [team1_score, team2_score] = score.split('-')

        # make sure game date is in correct format
        game_date = game_date.replace("-", " ")
        try:
            game_dt = datetime.strptime(game_date, "%Y %m %d")
        except Exception as e:
            raise Exception("Invalid date format. Use YYYY-MM-DD.")
        
        if team1_score > team2_score:
            team1_result = "WINS"
            team2_result = "LOSSES"
        elif team2_score > team1_score:
            team1_result = "LOSSES"
            team2_result = "WINS"
        else:
            team1_result = "TIES"
            team2_result = "TIES"
        
        match = {}
        match['team1'] = team1.upper()
        match['team2'] = team2.upper()
        match['score'] = score
        match['result_type'] = result_type.upper()
        match['game_date'] = game_date

        # a team can only play once on a given date
        valid_game = False
        if game_date not in self.matches:
            raise Exception("No matches on the provided date.")
        else:
            for fixture in self.matches[game_date]:
                teams = [fixture['team1'], fixture['team2']]
                if match['team1'] in teams and match['team2'] in teams:
                    valid_game = True
                
        if not valid_game:
            raise Exception("Teams not scheduled to play.")

        # make sure this isn't a duplicate entry
        for result in self.results:
            if result['game_date'] == match['game_date'] and (match['team1'] == result['team1'] or match['team1'] == result['team2']):
                raise Exception("Result already added.")

        self.dao.add_result(self.id, match['team1'], team1_result, match['team2'], team2_result, match)
        

    def retrieve(self):
        if self.retrieved:
            return
        
        season = self.dao.get_season(self.id)

        if 'Item' not in season:
            raise Exception('Season not found ' + self.id)

        self.retrieved = True
        self.last_update = season['Item']['last_update']
        self.league = season['Item']['League']
        self.matches = season['Item']['MATCHES']

        if 'Results' in season['Item']:
            self.results = season['Item']['Results']
        self.teams = season['Item']['TEAMS']
        self.year = season['Item']['YEAR']

    def get_about(self):
        response = "The wcpool command is intended to run a World Cup pool for 8 participants. "
        response += "Each participant drafts 4 teams in a snake-order draft, with the draft order determined automatically.\n"
        response += "Get started by registering a pool. As the admin, then add participants to your pool, after which the draft will start. "
        response += "Use /wcpool help for further info."
        
        return response

    def get_help(self, command, user):
            operation = "none"
            response = "*Sample Usage*:\n"

            if len(command):
                operation = command[0]
                
            if operation == "draft":
                response += "*Use to draft teams, either by team owners or the pool admin*\n"
                response += "-/wcpool draft efa (returns draft status for _efa_ pool)\n"
                response += "-/wcpool draft efa ENG (drafts England for the current user in the _efa_ pool)\n"
                response += "-/wcpool draft efa ENG @pontefract (drafts England for user _@pontefract_ in the _efa_ pool; only available to pool admin)\n"
            elif operation == "register":
                response += "*Use to register a new pool*\n"
                response += "-/wcpool register efa (register the _efa_ league)\n"
            elif operation == "seasons":
                response += "*Use to retrieve list of available seasons*\n"
                response += "-/wcpool seasons (returns available seasons in the WCPool App)\n"
            elif operation == "teams":
                response += "*Use to (1) list all the teams; and (2) retrieve the record for a given team*\n"
                response += "-/wcpool teams\n"
                response += "-/wcpool teams ENG (returns the record for England)\n"
            elif operation == "entry":
                response += "*Use to add entry to a pool (restricted to league admins)*\n"
                response += "-/wcpool entry efa @pontefract (adds user @pontefract to the _efa_ pool)\n"
            elif operation == "results":
                response += "*Use to see the latest results.*\n"
                response += "-/wcpool results (see latest results)\n"
            elif operation == "result":
                response += "*Use to add a result to a season (restricted to league admins)*\n"
                response += "-/wcpool result 2018-07-01 MEX BRA 6-1 (add 6-1 Mexico win over Brasil on July 1)\n"
            elif operation == "standings":
                response += "*Use to see pool standings*\n"
                response += "-/wcpool standings efa (returns standings for the _efa_ pool)"
            elif operation == "none":
                response = ("The following commands are supported (*admins only):\n"
                            "  -/wcpool help {command}\n"
                            "  commands: register, entry*, draft, teams, results, result*, standings")
            else:
                response += "Invalid command for /wcpool"
            

            #if user in admin_users:
            #response += "\n-/wcpool result {season} [GROUP|KNOCKOUT] {game-date} {team1} {team2} {score} (e.g. 2-2)"
                        
            return response
