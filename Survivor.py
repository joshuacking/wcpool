from Pool import Pool
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
import random
import math
import datetime
from PoolDAO import PoolDAO
from FootballSeason import FootballSeason
from pytz import timezone
import pytz

class Survivor(Pool):

    def get_stats(self, week, season):
        self.retrieve()
        stats = {}
        
        stats['entries'] = len(self.entries)
        stats['remaining'] = self.__get_remaining_team_count()
        stats['eliminated_this_week'] = self.__get_eliminated_by_week(week)
        stats['remaining_entries'] = self.__get_remaining_entries()

        # if current week, only include picks by team if in blackout
        if not season.get_current_week() == week or season.in_blackout():
            stats['team_picks'] = self.__get_team_picks(week)

        stats['missing_picks'] = self.__get_missing_picks(week)
        
        return stats

    def __get_missing_picks(self, week):
        result = []

        week = str(week)
        
        for entry in self.entries:
            if self.entries[entry]['status'] == 'ACTIVE':
                if week not in self.entries[entry]['picks']:
                    result.append(self.entries[entry]['user_id'])
                
        return result
    
    def __get_team_picks(self, week):
        teams = {}
        #teams['NO-PICK'] = 0
        teams['NO-PICK'] = []
        
        week = str(week)

        # get count of team picks for active entries
        for entry in self.entries:
            if self.entries[entry]['status'] == 'ACTIVE':
                if week in self.entries[entry]['picks']:
                    if self.entries[entry]['picks'][week] not in teams:
                        #teams[self.entries[entry]['picks'][week]] = 1
                        teams[self.entries[entry]['picks'][week]] = []
                    #else:
                        #teams[self.entries[entry]['picks'][week]] += 1
                    teams[self.entries[entry]['picks'][week]].append(self.entries[entry]['user_id'])
                else:
                    #teams['NO-PICK'] += 1
                    teams['NO-PICK'].append(self.entries[entry]['user_id'])

        return teams
    
    
    def __get_eliminated_by_week(self, week):
        result = {}
        result['total'] = 0
        result['eliminated'] = []

        for entry in self.entries:
            if self.entries[entry]['status'] == 'ELIMINATED' and self.entries[entry]['eliminated_week'] == week:
                result['total']  += 1
                result['eliminated'].append(self.entries[entry]['user_id'])
                
                # include team totals where pick was made
                if week in self.entries[entry]['picks']:
                    if self.entries[entry]['picks'][week] in result:
                        result[self.entries[entry]['picks'][week]] += 1
                    else:
                        result[self.entries[entry]['picks'][week]] = 1
                
        return result

    def __get_remaining_entries(self):
        result = []

        for entry in self.entries:
            if self.entries[entry]['status'] == 'ACTIVE':
                result.append(self.entries[entry]['user_id'])
                
        return result
    
    def __get_remaining_team_count(self):
        count = 0

        for entry in self.entries:
            if self.entries[entry]['status'] == 'ACTIVE':
                count += 1
                
        return count
    
    def get_picks(self, user, requestor, season):
        self.retrieve()
        if user in self.entries:
            picks = self.entries[user]['picks']
        else:
            raise Exception("Invalid user id -- *" + user + "*")

        # if requestor != user and not in blackout, remove current week's pick
        if requestor != user and not season.in_blackout():
            week = season.get_current_week()
            
            for pick in picks:
                if int(pick) == int(week):
                    del picks[pick]
                    break
                    
        return picks
    
    def purge_losers(self, week, loser):
        self.retrieve()
        eliminated = 0
        
        print("purging entries with " + loser + " in week " + week)

        # lop over entries, altering status where the entry either
        # didn't have a pick or picked the loser
        for entry in self.entries:
            if self.entries[entry]['status'] == 'ACTIVE':
                if week not in self.entries[entry]['picks'] or self.entries[entry]['picks'][week] == loser:
                    print(" eliminating: " + entry + " in week " + week + " with pick of " + loser)
                    eliminated = eliminated + 1
                    self.entries[entry]['status'] = 'ELIMINATED'
                    self.entries[entry]['eliminated_week'] = week

        if eliminated > 0:
            self.dao.update_entries(self.name, self.entries)
        
        return eliminated
        
    def new_entry(self, pool_id, user, userid, season):
        self.retrieve()
        entry = {}

        if user.find('|') != -1:
            [user_id, username] = user.split('|')
            username = username[:-1]
        else:
            username = user

        # make sure entry isn't a dupe
        if username in self.entries:
            raise Exception(username + " already exists in this pool.")

        # don't allow entries after season has started
        if season.has_started():
            raise Exception("Season has started -- no longer accepting new entries.")
        
        entry['user_id'] = userid
        entry['user_name'] = username
        entry['status'] = 'ACTIVE'
        entry['picks'] = {}

        result = self.dao.survivor_entry(pool_id, username, entry)

        return len(result['Attributes']['entries'])

    def pick(self, season, user, week, winner):
        self.retrieve()

        print(user + " picking " + winner + " in week " + week)
        #now = datetime.datetime.now()
        
        # is user still active?
        if self.__get_user_status(user) != "ACTIVE":
            raise Exception("Sorry, you are no longer active. Better luck next year.")

        # pick must be in by 5pm PT Thursday
        if season.in_blackout():
            raise Exception("Sorry, picks not allowed during the blackout period.")
        
        # does team play this week?
        if not season.team_scheduled_to_play(winner, week):
            raise Exception(winner + " not scheduled to play in week " + week)
        
        # is team eligible to be picked?
        if not self.eligible_pick(season, user, week, winner):
            raise Exception("You cannot pick the same team twice until you've picked all teams.")

        # update entry with pick
        result = self.dao.add_pick(self.name, user, week, winner)
        print("success: " + user + " picking " + winner + " in week " + week)

        return "success"

    def eligible_pick(self, season, user, week, winner):
        eligible_teams = self.get_eligible_teams(season, user, week)

        if winner in eligible_teams:
            return True
        else:
            return False

    def get_eligible_teams(self, season, user, week):
        self.retrieve()
        
        result = []
        games = season.get_schedule_by_week(week)
        picks = self.__get_picks_to_date(user, week)
        gamedate_naive = ""

        for game in games:
            # has the game started?
            try:
                gamedate_naive = datetime.datetime.strptime(game['game_date'], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                game['game_date'] = game['game_date'] + " 01:00:00"
                gamedate_naive = datetime.datetime.strptime(game['game_date'], "%Y-%m-%d %H:%M:%S")
                
            gamedate_aware = timezone('US/Pacific').localize(gamedate_naive)
               
            #date_format='%m/%d/%Y %H:%M:%S %Z'
            #print('Now:', self.global_now.strftime(date_format))
            #print('game:', gamedate_aware.strftime(date_format))
            if gamedate_aware < self.global_now:
                game_started = True
            else:
                game_started = False
                
                
            # if team hasn't been picked already and game hasn't started, team is an eligible pick
            if (game['team1'] not in picks and not game_started) or self.__picks_complete(season, user, week): 
                result.append(game['team1'])
                              
            if (game['team2'] not in picks and not game_started) or self.__picks_complete(season, user, week): 
                result.append(game['team2'])
                              
        return result

    def get_eligible_teams_with_names(self, season, user, week):
        self.retrieve()
        result = []
        
        teams = self.get_eligible_teams(season, user, week)
        teams.sort()

        for team_abbr in teams:
            result.append(season.get_team(team_abbr))

        result = sorted(result, key=lambda k: k['NAME'])
                        
        return result
    
    def __picks_complete(self, season, user, week):
        """Indicates if user has picked all teams in the league"""
        result = False
        teams = season.get_league_teams()
        picks = self.__get_picks_to_date(user, week)

        if len(picks) < len(teams):
            return False

        for pick in picks:
            if pick in teams:
                del teams[pick]

        if len(teams):
            return False
        else:
            return True
    
            
    def __get_picks_to_date(self, user, week):
        """Return picks made thus far"""
        result = []

        if user not in self.entries:
            raise Exception(user + " not entered in this pool. Use the _enter_ command to join.")
                        
        for this_week in self.entries[user]['picks']:
            week_int = int(this_week)
            
            if week_int < int(week):
                result.append(self.entries[user]['picks'][this_week])

        return result
        
    def __get_user_status(self, user):
        if user in self.entries:
            return self.entries[user]['status']
        else:
            return 'NOTFOUND'

