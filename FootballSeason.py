from PoolDAO import PoolDAO
from datetime import datetime, timedelta
from pytz import timezone
import pytz
from Season import Season



class FootballSeason(Season):

    
    def set_week_override(self, week):
        season = self.retrieve()
        self.week_override = str(week)
        
    def get_number_of_weeks(self):
        return len(self.matches)
        
    def get_results(self, count=10):
        """Returns the most recent results"""
        season = self.retrieve()
        result_count = len(self.matches)
        display_count = min(count, result_count) * -1

        return self.matches[display_count:]

    def get_schedule_by_week(self, week):
        """Returns the matches for a specific date for this season"""
        season = self.retrieve()
        games = []
        week = str(week)

        # if week is invalid, raise exception
        if not week in self.matches:
            raise Exception("No games scheduled.")

        # include team name based upon id
        for game in self.matches[week]:
            game['team1_name'] = self.teams[game['team1']]['NAME']
            game['team2_name'] = self.teams[game['team2']]['NAME']
            game['team1_league'] = self.teams[game['team1']]['LEAGUE']
            game['team2_league'] = self.teams[game['team2']]['LEAGUE']
            
            games.append(game)
            
        return games 
    
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


    def add_result(self, week, winner, pool):
        season = self.retrieve()
        week = str(week)
              
        game = {}
        game['winner'] = winner.upper()
        game['week'] =  week

        # a team can only play once on a given date
        valid_game = False
        print(str(self.matches.keys()) + ": " + week)
        if week not in self.matches:
            raise Exception("No games for week " + week)
        else:
            # find the game to update
            game_idx = -1
            for fixture in self.matches[week]:
                game_idx += 1
                teams = [fixture['team1'], fixture['team2']]
                if game['winner'] in teams:
                    teams.remove(game['winner'])
                    game['game_date'] = fixture['game_date']
                    game['team1'] = fixture['team1']
                    game['team2'] = fixture['team2']
                    
                    valid_game = True
                    break
                
        if not valid_game:
            raise Exception("Teams not scheduled to play.")

        self.dao.update_score(self.id, week, game_idx, game)

        loser_count = pool.purge_losers(week, teams[0])
        
        return loser_count

    def team_scheduled_to_play(self, team, week):
        season = self.retrieve()
        
        for game in self.matches[week]:                
            teams = [game['team1'], game['team2']]
            if team in teams:
                return True
                
        return False

    def in_blackout(self):
        self.retrieve()
        
        result = True
        now = self.global_now #datetime.now(tz=pytz.utc)
        #now = datetime.strptime("2019-08-29", "%Y-%m-%d") + timedelta(hours=7) + timedelta(hours=17)
        now = now.astimezone(timezone('US/Pacific'))
        weekday = now.weekday()
        hour = now.hour
        #print("now is " + str(weekday) + " hour is " + str(hour))
        date_format='%m/%d/%Y %H:%M:%S %Z'
        #print('Current date & time is:', now.strftime(date_format))
        

        # prior to the first game of the season, return false
        # always return false Sun 12a -  Thu 5p
        # add 7 hours to the game to account for PT, then another 17 to adjust to 5p
        first_game_date = datetime.strptime("2019-08-29", "%Y-%m-%d") + timedelta(hours=24) #datetime.strptime(self.matches['1'][0]['game_date'], "%Y-%m-%d") + timedelta(hours=24)
        first_game_date = first_game_date.astimezone(timezone('US/Pacific'))
        #print('first game is:', first_game_date.strftime(date_format))
        
        if now < first_game_date or weekday in [6,0,1,2]:
            return False
        elif weekday == 3 and hour < 17:
            return False
        else:
            return True

    def has_started(self):
        season = self.retrieve()
        week = int(self.get_current_week())

        # if it's the first week and we're in blackout OR it's past the first week, return True
        if (week == 1 and self.in_blackout()) or week > 1:
            return True

        return False
    
    def find_week(self, date):
        season = self.retrieve()

        if len(self.week_override):
            return self.week_override
        
        # find the next saturday
        d = datetime.strptime(date, '%Y-%m-%d')
        t = timedelta((12 - d.weekday()) % 7)
        next_saturday = ((d + t).strftime('%Y-%m-%d'))
        
        # find a matching Saturday
        for week in self.matches:
            for game in self.matches[week]:
                if next_saturday == game['game_date']:
                    return week

        if d.month < 9:
            return str(1)
        else:
            return str(13)
            #raise Exception("No games scheduled.")

    def get_current_week(self):
        now = self.global_now #datetime.now()
        date_string = now.strftime('%Y-%m-%d')

        return self.find_week(date_string)

    def get_team(self, team):
        season = self.retrieve()

        if team in self.teams:
            return self.teams[team]
        else:
            raise Exception("Team not found with code " + team)
        
    def add_resultxxx(self, winner, loser, pool):
        season = self.retrieve()
        
        # find game and add winner
        game_search = self.__find_game(winner, loser)
        game_search['game']['winner'] = winner
        game_search['game']['loser'] = loser
        
        # update season
        self.dao.add_match_result(self.id, game_search['game'], game_search['week'], game_search['game_idx'])
        
        # tell pool to purge losers
        number_of_losers = pool.purge_losers(loser)

        return number_of_losers

    def __find_game(self, winner, loser):
        season = self.retrieve()

        for week in self.matches:
            game_idx = -1
            for game in self.matches[week]:
                game_idx += 1
                teams = [game['team1'], game['team2']]
                if winner in teams and loser in teams:
                    result['game'] = game
                    result['week'] = week
                    result['game_idx'] = game_idx
                    
                    return result

        raise Exception("Game not found between " + winner + " and " + loser)

    def get_about(self):
        response = "*Survivor Pool Rules*\n"
        response += "1. Each week, you pick the winner of one (and only one) game involving a Pac-12 team. Picks are due by Thursday @ 5pm PT (no exceptions).\n"
        response += "2. If your team loses (or you fail to submit a pick), you're out of the pool. \n"
        response += "3. You cannot pick a team twice until you've picked every team in the league (i.e. Pac-12) once. "
        response += "However, this does not mean that you always must pick a Pac-12 team for the week. "
        response += "For example, you can pick BYU to beat AZ in week one, but you still need to pick AZ to win a game *before* any repeat picks (within the Pac-12 or otherwise).\n"
        response += "4. Last person standing wins the pot. If there's a tie at the end of the regular season, it will be resolved by picking the winner (and total points as a subsequent tiebreaker) of the Pac-12 title game. If there's still a tie at that point, we'll split the pot.\n"
        response += "5. $40 entry fee.\n\n"
        response += "Try _/sp help_ to learn about the commands."
    
        return response

    def get_help(self, command, user):
            operation = "none"
            response = ""

            if len(command):
                operation = command[0]
                
            if operation == "register":
                response += "*Use to register a new pool in the current channel*\n"
                response += "_/sp register_\n"
            elif operation == "enter":
                response += "*Use to enter the pool in the current channel*\n"
                response += "_/sp enter_\n"
            elif operation == "result":
                response += "*Use to add a result to a season (restricted to league admins)*\n"
                response += "_/sp result_ {week} {winner}\n"
            elif operation == "schedule":
                response += "*Use to see the schedule for the week*\n"
                response += "_/sp schedule_ {week_number} (week defaults to current week)"
            elif operation == "pick":
                response += "*Use to make your pick for the current week.*\n"
                response += "_/sp pick_"
            elif operation == "picks":
                response += "*Use to see picks for a user*\n"
                response += "_/sp picks_ {user} (user defaults to current user)"
            elif operation == "stats":
                response += "*Use to see stats for the pool*\n"
                response += "_/sp stats_ "
            elif operation == "none":
                response = ("The following commands are supported:\n"
                            "  _/sp help_ {command}\n"
                            "  commands: enter, schedule, pick, picks, stats")
            else:
                response += "Invalid command for /sp"
            

            #if user in admin_users:
            #response += "\n-/wcpool result {season} [GROUP|KNOCKOUT] {game-date} {team1} {team2} {score} (e.g. 2-2)"
                        
            return response
