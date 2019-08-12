import datetime 
from pytz import timezone
import pytz

class SlackFormatter:

    def stats(self, week, pool, stats, season):
        response = "*Week " +  week + " Statistics*\n"
        response += "Total Entries: " + str(stats['entries']) + "\n"
        response += "Remaining Entries: " + str(stats['remaining']) + " ( "

        for entry in stats['remaining_entries']:
            if entry in stats['missing_picks']:
                entry_display = "_<@" + entry + ">_ "
            else:
                entry_display = "<@" + entry + "> "
            response += entry_display
            
        response += ")\nEliminated this Week: " + str(stats['eliminated_this_week']['total'])

        if len(stats['eliminated_this_week']['eliminated']):
            response += " ("
            
            for entry in stats['eliminated_this_week']['eliminated']:
                response += "<@" + entry + "> "

            response += ")"
                        
        if 'team_picks' in stats:
            response += "\nPicks this Week\n"
            for team in sorted(stats['team_picks']):
                if team != 'NO-PICK':
                    team_info = season.get_team(team)
                    response += "  " + team_info['NAME'] + ": " + str(len(stats['team_picks'][team])) + " ( "

                    for entry in stats['team_picks'][team]:
                        response += "<@" + entry + "> "

                    response += ")\n"

            # add no picks last
            response += "  No Pick: " + str(len(stats['team_picks']['NO-PICK'])) + "\n"
        
        response += "\nEntries in _italics_ are missing picks for this week.\n"
        
        return response
    
    def matchups(self, matches, pool, date):
        response = "*Matches for " + date + "* (_times in PDT_)\n"

        for match in matches:
            entry1 = pool.get_entry_by_team(match['team1'])
            entry2 = pool.get_entry_by_team(match['team1'])
            gametime = match['time']
            response += gametime + " - " + match['team1'] + " v. " + match['team2'] + " (" + entry1 + " v. " + entry2 + ")\n"

        return response

    def enter(self, user, num_entries):
        response = "Welcome to the pool, <@" + user + ">!\nThere are now " + str(num_entries) + " entrants in the pool"

        return response

    def result(self, result):
        response = "*Success!*\nResult successfully added.\n"

        response += str(result) + " entries eliminated."
        
        return response
    
    def results(self, results):
        response = "*Latest Matches*\n"

        for result in reversed(results):
            game_date = datetime.datetime.strptime(result['game_date'], "%Y %m %d")
            display_date = game_date.strftime("%B") + " " + game_date.strftime("%d")
            [team1score, team2score] = result['score'].split('-')
            response += display_date + ": " + result['team1'] + " (" + team1score + ") - " + result['team2'] + " (" + team2score + ")\n"

        return response

    def teams_by_division(self, league, teams):
        response = "*Teams for " + league + "*\n"
        
        for division in sorted(teams):
            response += "*" + division + "*: " #+ str(teams[division])

            division_teams = ""
            for team in teams[division]:
                division_teams += team['name'] + " (" + team['code'] + ")  "
                
            response += division_teams + '\n'
            
        return response

    def schedule(self, season, week, pool, user):
        games = season.get_schedule_by_week(week)
        response = "*Schedule for Week " + week + "*\n"
        date = ""
        

        for game in games:
            if date != game['game_date']:
                date = game['game_date']
                display_date = game['game_date']
                
                # not all games include time info
                try:
                    gamedate_naive = datetime.datetime.strptime(display_date, "%Y-%m-%d %H:%M:%S")
                    date_format='%m/%d/%Y %H:%M'
                    date_format='%Y-%m-%d %H:%M'
                    response += "\n*" + gamedate_naive.strftime(date_format) + "*\n"
                except ValueError:
                    response += "\n*" + date + "*\n"


            if 'winner' in game:
                winner = game['winner']
            else:
                winner = "n/a"

            team1 = game['team1_name']
            team1_eligible = pool.eligible_pick(season, user, week, game['team1'])
            if not team1_eligible:
                team1 = "~" + team1 + "~"

            if game['team1'] == winner:
                team1 = "*" + team1 + "*"
                
            #if game['team1_league'] != 'PAC12':
                #team1 +=  " (" + game['team1_name'] + ")"

            team2 = game['team2_name']
            team2_eligible = pool.eligible_pick(season, user, week, game['team2'])
            if not team2_eligible:
                team2 = "~" + team2 + "~"

            if game['team2'] == winner:
                team2 = "*" + team2 + "*"
                
            #if game['team2_league'] != 'PAC12':
                #team2 +=  " (" + game['team2_name'] + ")"

            response +=  team1 + " (" + game['team1'] + ") @ " + team2 + " (" + game['team2']+ ")\n"

        response += "\nNote: *bold* indicates a winner; ~strikethru~ indicates a team you're ineligible to pick"

        return response
        
        
    def team_record(self, team):
        record = str(team['WINS']) + '-'
        record += str(team['LOSSES']) +'-'
        record += str(team['TIES'])
        response = '*' + team['NAME'] + '*: '  + record

        return response

    def new_pool(self, pool):
        response = "*Success!*\nPool entry *" + pool.get_name() + "* for season *" + pool.get_season_id() + "* successfully created.\n\n"
        response += "*Next*: add participants using /wcpool entry"

        return response

    def picks(self, user, picks, season):
        response = "*Picks for <@" + user + ">*\n"

        if not len(picks):
            response += "_No picks to display._"

        teams = season.get_teams()
        sorted_picks = sorted(picks.items(), key=lambda x: int(x[0]))
        for pick in sorted_picks:
            if pick[1] in teams:
                team_name = teams[pick[1]]['NAME']
            else:
                team_name = pick[1]
            response += "Week " + pick[0] + ": " + team_name + "\n"
            
        return response
    
    def pick(self, week, team, season):
        response = "*Success!*\n"
        teams = season.get_teams()
        if team in teams:
            team_name = teams[team]['NAME']
        else:
            team_name = team
            
        response += team_name + " is your pick for week " + week

        return response
    
    def handle_exception(self, exception):
        return "*Error*\n" + str(exception)

    def pick_options(self, week, user, teams):
        attachments = []
        attachment = {}
        attachment['callback_id'] = "make_pick"
        attachment['title'] = "Options for " + user + "\n"
        #attachment['text'] = "attachment 1 text"
        attachment['actions'] = []

        action = {}
        action['type'] = "select"
        action['name'] = "selected_team"
        action['text'] = "Available Teams ..."
        action['options'] = []
        
        for team in teams:
            option = {}
            option['text'] = team['NAME']
            option['value'] = team['ID']
            action['options'].append(option)

        attachment['actions'].append(action)    
        attachments.append(attachment)
        
        return attachments
        
    def get_attachments(self):
        attachments = []
        attachment = {}
        attachment['callback_id'] = "make_pick"
        attachment['title'] = "attachment 1 title"
        attachment['text'] = "attachment 1 text"
        attachment['actions'] = []
        
        action = {}
        action['type'] = "select"
        action['name'] = "teams"
        action['text'] = "Available Teams ..."
        action['options'] = []

        option1 = {}
        option1['text'] = "UCLA"
        option1['value'] = "UCLA"
        action['options'].append(option1)

        option2 = {}
        option2['text'] = "Stanford"
        option2['value'] = "STAN"
        action['options'].append(option2)
        

        attachment['actions'].append(action)

        attachments.append(attachment)
        
        return attachments
