from Pool import Pool 
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
import random
import math
import datetime
from Season import Season
from PoolDAO import PoolDAO

class WorldCup(Pool):

    # constants
    dao = PoolDAO()



    def new_entry(self, pool_id, user, admin):
        response = ''
        entry = {}

        if user.find('|') != -1:
            [user_id, user_name] = user.split('|')
            user_id = user_id[1:]
            user_name = user_name[:-1]
        else:
            user_id = ' '
            user_name = user

        # get the pool to update
        table = boto3.resource('dynamodb').Table('pools')

        entry['user_id'] = user_id
        entry['user_name'] = user_name
        entry['teams'] = []

        try:
            # add new entry
            result = table.update_item(
                Key={'POOL_NAME':pool_id},
                UpdateExpression='SET entries.#u = :e',
                ConditionExpression="size(entries) < expected_entries and admin_user = :au and attribute_not_exists(entries.#u)",
                ExpressionAttributeNames={'#u': user_name},
                ExpressionAttributeValues={
                    ':e': entry,
                    ':au': admin
                },
                ReturnValues='ALL_NEW'
            )

            num_entries = len(result['Attributes']['entries'])
            remaining_slots = result['Attributes']['expected_entries'] - num_entries
            response = user_name + ' added to the pool!\n'
            response += 'There are ' + str(remaining_slots) + ' spots left in the pool.\n'

            # if pool is full, create draft order and update (again)
            if remaining_slots == 0:
                draft_order = list(result['Attributes']['entries'].keys())
                random.shuffle(draft_order, random.random)

                result2 = table.update_item(
                    Key={'POOL_NAME':pool_id},
                    UpdateExpression='SET draft.#o = :o, draft.#s = :s',
                    ExpressionAttributeNames={'#o': 'order', '#s': 'status'},
                    ExpressionAttributeValues={
                        ':o': draft_order,
                        ':s': 'STARTED'
                    },
                    ReturnValues='ALL_NEW'
                )

                response += "Your pool is full and the draft order has been set!\n"
                response += "Use /wcpool draft {pool-name} to get draft info."
         
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                response = '*Error*\nEntry failed. Duplicate entry or pool is full.'
            else:
                response = '*Error*\nEntry failed. ['   + e.response['Error']['Code'] + ']'
            print(e.response['Error']['Message'])
            
        return response

    def get_standings(self, pool_id, team_domain):
        response = ("*Current Standings for " + pool_id + "*\n")

        # make sure pool is valid
        try:
            pool = self.__get_pool(pool_id)

            if 'Item' not in pool:
                return '*Error*\nInvalid pool.'
        except ClientError as e:
            return "*Error*\nSomething went wrong retrieving pool"

        if team_domain != pool['Item']['domain']:
            return "*Error*\n_" + pool_id + "_ doesn't exist in this Slack workspace."
        
        # get season
        season = self.__get_season(pool['Item']['SEASON_ID'])

        # check season and pool status
        if pool['Item']['draft']['status'] != 'COMPLETE':
            return "*Error*\nDraft is not complete for this pool." 
        elif len(season['Item']['Results']) == 0:
            response = "No results for this season.\n"

        # do standings need to be recalculated?
        last_result_time = datetime.datetime.strptime(season['Item']['last_update'], "%Y-%m-%d %H:%M:%S.%f")
        if 'last_updated' in pool['Item']:
            last_standings_update = datetime.datetime.strptime(pool['Item']['last_updated'], "%Y-%m-%d %H:%M:%S.%f")
            update_required = last_result_time > last_standings_update
        else:
            update_required = True
        

        if update_required:
            standings = self.__calculate_standings(season['Item'], pool['Item'])

            # update standings
            self.__update_standings(pool_id, standings)
        else:
            standings = pool['Item']['standings']

        # build response
        for entry in standings:
            name = entry['name']
            teams = self.__get_entry_teams(pool['Item'], name)

            response += name + " (" + str(entry['matches_played']) + ") " + "[" + teams + "]: " + str(entry['points']) + "\n"     
        
        return response   
        
        
    def get_draft_order(self, pool_id):
        response = ("*Draft Status: ")
        
        # make sure pool is valid
        try:
            pool = self.__get_pool(pool_id)

            if 'Item' not in pool:
                return '*Error*\nInvalid pool.'
        except ClientError as e:
            return "*Error*\nSomething went wrong retrieving pool" 

        
        if pool['Item']['draft']['status'] == 'COMPLETE':
            response += "COMPLETE*\n"
            return response
        elif (len(pool['Item']['draft']['picks'])):
            response += "UNDERWAY*\n"
            response += "Last Pick: *" + pool['Item']['draft']['picks'][-1]['entry'] + "* picked *" + pool['Item']['draft']['picks'][-1]['team'] + "*\n"
            response += "* " + self.__get_current_pick(pool['Item']) + "* is on the clock\n"
        else:
            response += "NOT STARTED*\n"
            #response += "* " + self.__get_current_pick(pool['Item']) + "* is on the clock\n"

        # include draft order
        response += "\n*Draft Order (Snake Style)*\n"
        for idx, user in enumerate(pool['Item']['draft']['order']):
            teams = self.__get_entry_teams(pool['Item'], user)
            response += str(idx+1) + ": " + user + " (" + teams + ")\n"
            
        # include available teams
        response += "\n*Available Teams*\n"
        response += self.__format_available_teams(pool['Item'])
        
        return response


    def make_draft_pick(self, pool_id, team_id, entry_id, admin=''):
        response = ("*Draft Status*\n")
        team_id = team_id.upper()
        pick = {}

        # clean user if admin is making pick
        if entry_id.find('|') != -1:
            [user_id, entry] = entry_id.split('|')
            entry = entry[:-1]
        else:
            entry = entry_id
            
        # make sure pool is valid
        try:
            pool = self.__get_pool(pool_id)

            if 'Item' not in pool:
                return '*Error*\nInvalid pool.'
        except ClientError as e:
            return "*Error*\nSomething went wrong retrieving pool" 

        # confirm user has admin rights
        if admin != '' and not self.__is_admin(pool['Item'], admin):
            return "*Error*\nMust be admin to pick on behalf of others."
                
        # confirm draft is ongoing and user's pick
        if pool['Item']['draft']['status'] == 'NOT_STARTED':
            return "*Error*\nDraft has yet to begin."
        elif pool['Item']['draft']['status'] == 'COMPLETE':
            return "*Error*\nDraft is complete!"
        
        current_pick = self.__get_current_pick(pool['Item'])
        user_atts = current_pick.split("|")
        if len(user_atts) > 1:
            current_pick_user = user_atts[1]
            current_pick_user = current_pick_user[:-1]
        else:
            current_pick_user = user_atts[0]

        if entry != current_pick_user:
            return "*Error*\nNot Your Pick. Current pick is " + current_pick
        
        # ensure team is valid
        season = self.__get_season(pool['Item']['SEASON_ID'])

        if team_id not in season['Item']['TEAMS']:
            return "*Error*\nInvalid team."

        # ensure team is available
        if not self.__is_team_available(pool['Item'], team_id):
            return "*Error*\nTeam *" + team_id + "* unavailable"
            
        # write pick
        pick['entry'] = entry
        pick['team'] = team_id
        
        try:
            # get the pool to update
            table = boto3.resource('dynamodb').Table('pools')
            
            # add new pick
            result = table.update_item(
                Key={'POOL_NAME':pool_id},
                UpdateExpression='SET draft.picks = list_append(draft.picks, :v), entries.#user.teams = list_append(entries.#user.teams, :team)',
                ExpressionAttributeNames={'#user': entry},
                ExpressionAttributeValues={
                    ':v': [pick],
                    ':team': [team_id]
                },
                ReturnValues='ALL_NEW'
            )
        except ClientError as e:
            print(e.response['Error']['Message'])
            return "*Error*\nSomething went wrong making the pick" 

        remaining_teams = self.__get_available_teams(season['Item'], result['Attributes'])
        next_pick = self.__get_current_pick(result['Attributes'])
        response = ("*" + entry + " has picked " + team_id + "*\n")

        response += self.__get_draft_order(pool_id) + "\n\n"
        
        if len(remaining_teams) > 0:
            response += "Next Pick: *" + next_pick + "*\n"
            response += "There are * " + str(len(remaining_teams)) + "* teams available for selection. "
            response += self.__format_available_teams(result['Attributes'])
            
        else:
            # mark draft complete
            status_update = table.update_item(
                Key={'POOL_NAME':pool_id},
                UpdateExpression='SET draft.#s = :s',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={':s': 'COMPLETE'},
                ReturnValues='ALL_NEW'
            )
            response += "Draft is complete!"
        
        
        return response

    def add_result(self, season, result_type, game_date, team1, team2, score):
        table = boto3.resource('dynamodb').Table('seasons')
        currenttime = str(datetime.datetime.now())

        [team1_score, team2_score] = score.split('-')

        # make sure game date is in correct format
        game_date = game_date.replace("-", " ")
        try:
            game_dt = datetime.datetime.strptime(game_date, "%Y %m %d")
        except Exception as e:
            print(e)
            return "*Error*\nInvalid date format. Use YYYY-MM-DD."
        
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
        seasondata = self.__get_season(season)

        valid_game = False
        if game_date not in seasondata['Item']['MATCHES']:
            return "*Error*\nNo matches on the provided date."
        else:
            for fixture in seasondata['Item']['MATCHES'][game_date]:
                teams = [fixture['team1'], fixture['team2']]
                if match['team1'] in teams and match['team2'] in teams:
                    valid_game = True
                
        if not valid_game:
            return "*Error*\nTeams not scheduled to play."

        for result in seasondata['Item']['Results']:
            if result['game_date'] == match['game_date'] and (match['team1'] == result['team1'] or match['team1'] == result['team2']):
                return "*Error*\nResult already added."
        
        # update season
        try:
            game_update = table.update_item(
                Key={'id':season},
                UpdateExpression='SET last_update = :d, Results = list_append(Results, :r), TEAMS.#tone.#toneresult = TEAMS.#tone.#toneresult + :i, TEAMS.#ttwo.#ttworesult = TEAMS.#ttwo.#ttworesult + :i',
                ExpressionAttributeNames={
                    '#tone': match['team1'],
                    '#toneresult': team1_result,
                    '#ttwo': match['team2'],
                    '#ttworesult': team2_result
                },
                ExpressionAttributeValues={':d': currenttime, ':r': [match], ':i': 1},
                ReturnValues='ALL_NEW'
            )
            
            return "*Success*\nresult added successfully"
        except Exception as e:
            print(e)
            return "*Error*\nSomething went wrong attempting to add the result"


    # note: using snake draft here, where in a 4-entry league the draft
    # order would be 1,2,3,4,4,3,2,1,1 ... repeat
    def __get_current_pick(self, pool):
        last_pick = ''
        next_pick_idx = 0
        num_picks = len(pool['draft']['picks'])
        entries = len(pool['entries'])
        draft_round = math.ceil((num_picks+1)/entries)
        
        # determine next pick index
        if num_picks:
            # find last pick
            last_pick = pool['draft']['picks'][-1]
            last_pick_idx = pool['draft']['order'].index(last_pick['entry'])

            if num_picks % entries == 0:
                next_pick_idx = last_pick_idx
            else:
                if draft_round % 2 == 0:
                    next_pick_idx = last_pick_idx - 1
                else:
                    next_pick_idx = last_pick_idx + 1         

        next_pick = pool['draft']['order'][next_pick_idx]

        if len(pool['entries'][next_pick]['user_id']) > 1:
            response = "<" + pool['entries'][next_pick]['user_id'] + "|" + pool['entries'][next_pick]['user_name'] + ">"
        else:
            response = pool['entries'][next_pick]['user_name']

        return response
    
        #return "<" + pool['entries'][next_pick]['user_id'] + "|" + pool['entries'][next_pick]['user_name'] + ">"


    def __get_entry(self, pool, team):
        for entry in pool['entries']:
            for team_id in pool['entries'][entry]['teams']:
                if team_id == team:
                    return pool['entries'][entry]['user_name']

        return ""
                                      
    def __format_available_teams(self, pool):
        season = self.__get_season(pool['SEASON_ID'])
        available_teams = self.__get_available_teams(season['Item'], pool)
        
        response = "The following teams remain available:\n"

        for team in available_teams:
            response += " -" + available_teams[team]['NAME'] + " (" + team + ")\n"

        return response

    def __get_available_teams(self, season, pool):
        teams = season['TEAMS']

        # loop over picks, removing picked teams from the map
        for pick in pool['draft']['picks']:
            del teams[pick['team']]

        return teams

    def __is_team_available(self, pool, team_id):
        # loop over picks, looking for team
        for pick in pool['draft']['picks']:
            if pick['team'] == team_id:
                return False
            
        return True

    def __is_admin(self, pool, user_name):
        if pool['admin_user'] == user_name:
            return True
        else:
            return False


    def __get_pool(self, pool_id):
        table = boto3.resource('dynamodb').Table('pools')
        pool = table.get_item(Key={'POOL_NAME':pool_id})

        return pool
    

    def __get_season(self, season_id):
        table = boto3.resource('dynamodb').Table('seasons')
        season = table.get_item(Key={'id':season_id})

        return season

    def __get_entry_teams(self, pool, entry):
        teams = ""
        for team in pool['entries'][entry]['teams']:
            teams += team + ", "

        teams = teams[:-2]

        return teams

    def __update_standings(self, pool_id, standings):
        table = boto3.resource('dynamodb').Table('pools')
        currenttime = str(datetime.datetime.now())
        
        result = table.update_item(
                Key={'POOL_NAME':pool_id},
                UpdateExpression='SET standings = :s, last_updated = :d',
                #UpdateExpression='SET standings = :s, entries.#user.teams = list_append(entries.#user.teams, :team)',
                #ExpressionAttributeNames={'#user': entry},
                ExpressionAttributeValues={
                    ':s': standings,
                    ':d': currenttime
                },
                ReturnValues='ALL_NEW'
            )

        return
    
    def __calculate_standings(self, season, pool):   
        points_by_entry = {}
        result_totals = {}

        # loop over the teams for each entries in season
        # looking up the wins and ties
        for entry in pool['entries']:
            points_by_entry[entry] = 0
            result_totals[entry] = 0
            
            for team in pool['entries'][entry]['teams']:
                points_by_entry[entry] += (season['TEAMS'][team]['WINS'] * 3) + season['TEAMS'][team]['TIES']
                result_totals[entry] += season['TEAMS'][team]['WINS'] + season['TEAMS'][team]['TIES'] + season['TEAMS'][team]['LOSSES']

        standings = sorted(points_by_entry.items(), key=lambda value: value[1], reverse=True)

        result = []
        for position in standings:
            person = {}
            person['name'] = position[0]
            person['points'] = position[1]
            person['matches_played'] = result_totals[person['name']]
            result.append(person)
        
        return result
    
