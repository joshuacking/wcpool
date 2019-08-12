import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
import datetime
import traceback


class PoolDAO:

    # define constants
    seasons_table = 'seasons'
    pools_table = 'pools'
    db_resource = 'dynamodb'
    
    def get_season(self, season_id):
        """Retrieve season from DB"""
        table = boto3.resource(self.db_resource).Table(self.seasons_table)
        season = table.get_item(Key={'id':season_id})

        return season

    def get_pool(self, pool):
        """Retrieve pool from DB"""
        from Pool import Pool
        id = pool.get_name()
        #pool = Pool()
        
        table = boto3.resource(self.db_resource).Table(self.pools_table)
        result = table.get_item(Key={'POOL_NAME':id})

        if 'Item' not in result:
            raise Exception('Pool not found ' + id)

        pool.set_admin_user(result['Item']['admin_user'])
        pool.set_domain(result['Item']['domain'])
        pool.set_draft(result['Item']['draft'])
        pool.set_entries(result['Item']['entries'])
        pool.set_expected_entries(result['Item']['expected_entries'])

        if 'last_updated' in result['Item']:
            pool.set_last_updated(result['Item']['last_updated'])
        pool.set_season_id(result['Item']['SEASON_ID'])
        pool.set_standings(result['Item']['standings'])
        
        return pool

    def survivor_entry(self, pool_id, user, entry):
        # get the pool to update
        table = boto3.resource(self.db_resource).Table(self.pools_table)
        
        try:
            # add new entry
            result = table.update_item(
                Key={'POOL_NAME':pool_id},
                UpdateExpression='SET entries.#u = :e',
                ConditionExpression="attribute_not_exists(entries.#u)",
                ExpressionAttributeNames={'#u': user},
                ExpressionAttributeValues={
                    ':e': entry
                },
                ReturnValues='ALL_NEW'
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise Exception("Entry failed. Duplicate entry.")
            else:
                raise Exception(e.response['Error']['Code'])

        return result
        
    def add_result(self, season_id, team1, team1_result, team2, team2_result, match):
        """Update season with new result"""
        table = boto3.resource(self.db_resource).Table(self.seasons_table)
        currenttime = str(datetime.datetime.now())
        
        # update season
        try:
            game_update = table.update_item(
                Key={'id':season_id},
                UpdateExpression='SET last_update = :d, Results = list_append(Results, :r), TEAMS.#tone.#toneresult = TEAMS.#tone.#toneresult + :i, TEAMS.#ttwo.#ttworesult = TEAMS.#ttwo.#ttworesult + :i',
                ExpressionAttributeNames={
                    '#tone': team1,
                    '#toneresult': team1_result,
                    '#ttwo': team2,
                    '#ttworesult': team2_result
                },
                ExpressionAttributeValues={':d': currenttime, ':r': [match], ':i': 1},
                ReturnValues='ALL_NEW'
            )
            
            return
        except Exception as e:
            print(str(traceback.format_exc()))
            raise Exception("Something went wrong attempting to add the result.")

    def update_entries(self, poolname, entries):
        table = boto3.resource(self.db_resource).Table(self.pools_table)

        # update season
        try:
            game_update = table.update_item(
                Key={'POOL_NAME':poolname},
                UpdateExpression='SET entries = :e',
                ExpressionAttributeValues={':e': entries},
                ReturnValues='ALL_NEW'
            )
            
            return
        except Exception as e:
            print(str(traceback.format_exc()))
            raise Exception("Something went wrong attempting to update entries.")
        
    def update_score(self, season_id, week, game_id, game):
        """Update season with result"""
        table = boto3.resource(self.db_resource).Table(self.seasons_table)
        currenttime = str(datetime.datetime.now())
        
        #print("update score for game " + str(game_id) + " for teams " + team1 + ":" + team2 + " results " + team1_result + ":" + team2_result)
        
        # update season
        try:
            game_update = table.update_item(
                Key={'id':season_id},
                #UpdateExpression='SET last_update = :d, MATCHES.#week[' +  str(game_id) + '].score = :s',
                UpdateExpression='SET last_update = :d, MATCHES.#week[' +  str(game_id) + ']= :g',
                ExpressionAttributeNames={
                    #'#tone': team1,
                    #'#toneresult': team1_result,
                    '#week': week
                },
                ExpressionAttributeValues={':d': currenttime, ':g': game},
                ReturnValues='ALL_NEW'
            )
            
            return
        except Exception as e:
            print(str(traceback.format_exc()))
            raise Exception("Something went wrong attempting to add the score.")

    def new_pool(self, pool_name, season_id, entries, admin_user, domain_reference):
        """Inserts a new pool in DynamoDB"""
        item = {}
        
        # build item
        item['POOL_NAME'] = pool_name
        item['SEASON_ID'] = season_id
        item['expected_entries'] = int(entries)
        item['entries'] = {}
        item['admin_user'] = admin_user
        item['domain'] = domain_reference
        item['standings'] = []
        item['draft'] = {}
        item['draft']['order'] = []
        # draft states: NOT_STARTED, STARTED, COMPLETE
        item['draft']['status'] = 'NOT_STARTED'
        item['draft']['picks'] = []

        try:
            table = boto3.resource(self.db_resource).Table(self.pools_table)
            result = table.put_item(Item=item, ConditionExpression='attribute_not_exists(POOL_NAME)')

            return
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise Exception("Entry with that name already exists. Please try again.")
            else:
                raise Exception("Unable to register entry.")

    def add_pick(self, pool, user, week, winner):
        table = boto3.resource(self.db_resource).Table(self.pools_table)
        print("add pick to " + pool + " for " + user + " in " + week + ":" + winner)
        try:
            # add new entry
            result = table.update_item(
                Key={'POOL_NAME':pool},
                UpdateExpression='SET entries.#u.#p.#w = :wi',
                #ConditionExpression="attribute_not_exists(entries.#u)",
                ExpressionAttributeNames={'#u': user, '#p':'picks', '#w':week},
                ExpressionAttributeValues={
                    ':wi': winner
                },
                ReturnValues='ALL_NEW'
            )
        except ClientError as e:
                raise Exception(e.response['Error']['Code'])

        return result
