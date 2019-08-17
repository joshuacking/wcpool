import json
import time
from WorldCup import WorldCup
from Survivor import Survivor
from Season import Season
from FootballSeason import FootballSeason
from SlackFormatter import SlackFormatter
#import datetime
from datetime import datetime, timedelta
from pytz import timezone
import pytz
import traceback
from Slack import Slack

def lambda_handler(event, context):
    t1 = int(round(time.time() * 1000))
    response = {}
    response['text'] = ""
    slack  = Slack(event)
    tz = pytz.timezone("US/Pacific")
    global_now = datetime.now(tz=tz)
    
    # remove comment on next line to test different dates
    global_now = tz.localize(datetime(2019, 8, 24, 19, 31), is_dst=None)

    date_format='%m/%d/%Y %H:%M:%S %Z'
    print('Current date & time is:', global_now.strftime(date_format))
    
    if slack.get_context_root() == "wcpool":
        pool = WorldCup(slack.get_channel_id(), global_now)
        season_id = 'wc2018'
        season = Season(season_id, global_now)
    else:
        pool = Survivor(slack.get_channel_id(), global_now)
        season_id = 'pac12-2019'
        season = FootballSeason(season_id, global_now)
    
    formatter = SlackFormatter()
    command = slack.get_command()
    
    
    # check auth
    if not slack.is_authorized_workspace():
        response['text']  = "*Not Authorized*"
        return json.dumps(response)

    # get operation
    operation = slack.get_operation()

    # log command
    print(slack.get_username() + ' (' + slack.get_domain() + ')' + ' requested ' + operation + ' with args ' + str(command) + " in channel " + slack.get_channel_id() + " / " + slack.get_channel_name())
        
    # return help info      
    

    if operation == 'about':
        response['text'] = season.get_about()
        response['response_type'] = 'ephemeral'

    # draft a team for an entry
    elif operation == 'draft':
        response['response_type'] = 'in_channel'
        
        if len(command) < 1:
            response['response_type'] = 'ephemeral'
            response['text'] = "*Error*\nInsufficient arguments"
        # i.e. /wcpool draft {pool}
        elif len(command) == 1:
            response['response_type'] = 'ephemeral'
            response['text'] = pool.get_draft_order(slack.get_pool())
        # i.e. /wcpool draft {pool} {team}
        elif len(command) == 2:
            response['text'] = pool.make_draft_pick(slack.get_pool(), slack.get_team(), slack.get_username())
        # i.e. /wcpool draft {pool} {team} {entry}
        elif len(command) == 3:
            response['text'] = pool.make_draft_pick(slack.get_pool(), slack.get_team(), slack.get_entry(), slack.get_username())
        else:
            response['text'] = "*Error*\Draft command not yet supported."
            

    # with no args, just adds the current user
    # with one arg, adds the named user (only if caller is admin)
    elif operation == 'enter':
        try:
            if len(command) == 0:
                user = slack.get_username()
            else:
                user = command[0]
                
            num_entries = pool.new_entry(slack.get_channel_id(), user, slack.get_user_id(), season)
                
            response['text'] = formatter.enter(slack.get_user_id(), num_entries)
            response['response_type'] = 'in_channel'
        except Exception as e:
            response['text']  = formatter.handle_exception(e)
            print(str(traceback.format_exc()))
            
    # add an entry to an existing pool
    elif operation == 'entry':
        if len(command) < 2:
            response['text'] = "*Error*\nInsufficient arguments"
        else:
            response['text'] = pool.new_entry(slack.get_pool(), slack.get_entry(), slack.get_username())
            response['response_type'] = 'in_channel'

    elif operation == 'help':
        response['text'] = season.get_help(command, slack.get_username())
        response['response_type'] = 'ephemeral'
        
    # return matches
    # /wcpool matches efa (returns matches for the efa pool for today)
    # /wcpool matches efa 2018-06-23 (returns matches for the efa pool for Jun-23)
    elif operation == 'matches':
        date = ""
        response['text'] = '*Error*\nNot yet supported.'
        if len(command) == 0:
            response['text'] = '*Error*\nInsufficient arguments.'
        # no date passed in; use today
        elif len(command) == 1:
            try:
                # use today's date + 4 hours, which will give us tomorrow's result after 1pm PT
                now = datetime.today() + timedelta(hours=4)
                date = now.strftime('%Y-%m-%d')
            except Exception as e:
                response['text']  = formatter.handle_exception(e)
        else:
            date = slack.get_date()

        try:
            matches = season.get_matches_by_date(date)
            pool.retrieve(slack.get_pool())
            response['text'] = formatter.matchups(matches, pool, date)
            response['response_type'] = 'in_channel'
        except Exception as e:
            response['text'] = formatter.handle_exception(e)
        
    # first arg is the team to pick; second arg is the optional week as an int
    elif operation == 'make_pick':
        week = str(season.get_current_week())
        if operation == 'pick':
            team = command[0].upper()
        elif operation == 'make_pick':
            team = slack.get_selected_option()

        try:
            result = pool.pick(season, slack.get_username(), week, team)
            response['text'] = formatter.pick(week, team, season)
        except Exception as e:
            print(str(traceback.format_exc()))
            response['text'] = formatter.handle_exception(e)
        
    elif operation == 'picks':
        try:
            if len(command) == 1:
                [user_id, user] = command[0].split('|')
                user = user[:-1]
                user_id = user_id[2:]
            else:
                user = slack.get_username()
                user_id = slack.get_user_id()

            
            requestor = slack.get_username()
            picks = pool.get_picks(user, requestor, season)
            response['text'] = formatter.picks(user_id, picks, season)
        except Exception as e:
            print(str(traceback.format_exc()))
            response['text'] = formatter.handle_exception(e)
            
    # create a new pool
    elif operation == 'register':
        if len(command) == 0:
            pool_id = slack.get_channel_id()
        else:
            pool_id = slack.get_pool()
            
        try:
            pool.create(pool_id, season_id, 8, slack.get_username(), slack.get_domain())
            response['text'] = formatter.new_pool(pool)
        except Exception as e:
            print(str(traceback.format_exc()))
            response['text'] = formatter.handle_exception(e)
        response['response_type'] = 'ephemeral'

    elif operation == 'result':
        if not slack.is_global_admin():
            response['text'] = "*Error*\nInsufficient privileges."
        elif len(command) < 2:
            response['text'] = "*Error*\nInsufficient arguments"
        else:
            try:
                result = season.add_result(command[0], command[1], pool)
                response['text'] = formatter.result(result)
            except Exception as e:
                print(str(traceback.format_exc()))
                response['text'] = "Issue adding result"
                
    # add a result to the season info in the form {season} [GROUP|KNOCKOUT] {game_date} {team-id1} {team-id2} {score}
    elif operation == 'wcresult':
        if not slack.is_global_admin():
            response['text'] = "*Error*\nInsufficient privileges."
        elif len(command) < 4:
            response['text'] = "*Error*\nInsufficient arguments"
        else:
            if False:
                try:
                    gamedate = datetime.strptime(slack.get_date(), "%Y-%m-%d")
                    group_end = datetime.strptime('2018 06 29', "%Y %m %d")
                except Exception as e:
                    response['text'] = "Invalid date format"
                    return json.dumps(response)
                    
                if gamedate < group_end:
                    stage = 'GROUP'
                else:
                    stage = 'KNOCKOUT'

            try:
                season.add_result(command[0], command[1], command[2], command[3])
                #season.add_result(stage, slack.get_date(), command[1], command[2], command[3])
                response['text'] = "*Success*\nresult added successfully"
            except Exception as e:
                response['text'] = formatter.handle_exception(e)

            response['response_type'] = 'ephemeral'
        
    # add an entry to an existing pool
    elif operation == 'results':
        results = season.get_results()
        response['text'] = formatter.results(results)
        response['response_type'] = 'in_channel'

    # if no week specified, get the next schedule
    elif operation == 'schedule':
        try:
            # no week passed in
            if len(command) == 0:
                week = season.get_current_week()
            # use week passed in
            else:
                week = command[0]

            response['text'] = formatter.schedule(season, week, pool, slack.get_username())
        except Exception as e:
            print(str(traceback.format_exc()))
            response['text'] = formatter.handle_exception(e)
        
        
    # return standings for a pool
    elif operation == 'standings':
        if len(command) < 1:
            response['text'] = "*Error*\nInsufficient arguments"
        else:
            response['text'] = pool.get_standings(slack.get_pool(), slack.get_domain())
            response['response_type'] = 'in_channel'

    # return standings for a pool
    elif operation == 'stats':
        # no week passed in
        if len(command) == 0:
            week = season.get_current_week()
        # use week passed in
        else:
            week = command[0]
                
        stats = pool.get_stats(week, season)
        response['text'] = formatter.stats(week, pool, stats, season)
        response['response_type'] = 'in_channel'
            
    elif operation == 'pick':
        week = season.get_current_week()
        user = slack.get_username()
        teams = pool.get_eligible_teams_with_names(season, user, week)
        
        response['text'] = "*Select a Team for Week " + str(week) + "*"
        response['attachments'] = formatter.pick_options(season, pool, week, user, teams)
        
    # return teams for a season
    elif operation == 'teams':
        # get all teams for a season
        try:
            if len(command) == 0:
                teams = season.get_teams_by_division()
                league = season.get_name()
                response['text'] = formatter.teams_by_division(league, teams)
            # get record for the named team
            else:
                team = season.get_team(season_id, slack.get_team())
                response['text'] = formatter.team_record(team)
            response['response_type'] = 'in_channel'
        except Exception as e:
            response['text'] = formatter.handle_exception(e)
            print(str(traceback.format_exc()))

    else:
        response['text'] = '*Error*\nunknown command'
        response['response_type'] = 'ephemeral'

    # optional timing info
    #t2 = int(round(time.time() * 1000))
    #if slack.is_global_admin():
        #response['text'] += '\n_Timing: ' + str(t2-t1) + '_'
    
    return json.dumps(response)
