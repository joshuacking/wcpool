import urllib
import json

class Slack:

    authorized_workspaces = ['218CogtRDasg7efSACjmet79', 'YChHriE1pkFCxCh1R8Sj7Gqr', 'n98YX0F5xE1qaULjwmXxB6Ev', '7H7Wow9vLHfkKI4B0FdQCcAH', 'WIRTeN1y3Irh4L0wJ0hI24LX']
    global_admins = ['joshuaking', 'pontefract', 'aolenski']

    def get_entry(self):
        if self.operation == "draft" and len(command) > 2:
            return self.command[2]
        elif self.operation == "entry" and len(command) > 1:
            return self.command[1]
        else:
            return ""

    def get_date(self):
        if self.operation == "matches":
            return self.command[1]
        elif self.operation in "result,schedule":
            return self.command[0]
        else:
            return ""
        
    def get_pool(self):
        if self.operation in ["draft", "register", "entry", "standings"]:
            return self.command[0]
        else:
            return ""

    def get_team(self):
        if self.operation == "draft" and len(command) > 1:
            return self.command[1]
        elif self.operation == "teams":
            return self.command[0]
        else:
            return ""
                         
    def is_authorized_workspace(self):
        if self.token in self.authorized_workspaces:
            return True
        else:
            return False
            #raise Exception("Not Authorized")

    def is_global_admin(self):
        if self.user_name in self.global_admins:
            return True
        else:
            return False
        
    def __init__(self, event):
        # event keys: dict_keys(['body-json', 'params', 'stage-variables', 'context'])
        request = {}

        if ('body-json' in event and event['body-json'] is not None):
            pairs = event['body-json'].split("&")
            for pair in pairs:
                name, value = pair.split("=")
                request[name] = value

        payload = {}
        self.callback_id = ""
        self.actions = []
        if "payload" in request:
            payload_string = urllib.parse.unquote(request['payload'])
            payload = json.loads(payload_string)

            if "actions" in payload:
                self.actions = payload['actions']
                
            #for key in payload:
                #print(key + ":" + payload[key])
            #print(str(payload.keys()))

        self.token = ""
        if "token" in request:
            self.token = request['token']
        elif "token" in payload:
            self.token = payload['token']

        self.team_id = ""
        if "team_id" in request:
            self.team_id = request['team_id']
        elif "team" in payload and "id" in payload['team']:
            self.team_id = payload['team']['id']
            
        self.team_domain = ""
        if "team_domain" in request:
            self.team_domain = request['team_domain']
        elif "team" in payload and "domain" in payload['team']:
            self.team_domain = payload['team']['domain']

        self.channel_id = ""
        if "channel_id" in request:
            self.channel_id = request['channel_id']
        elif "channel" in payload and "id" in payload['channel']:
            self.channel_id = payload['channel']['id']

        self.channel_name = ""
        if "channel_name" in request:
            self.channel_name = request['channel_name']
        elif "channel" in payload and "name" in payload['channel']:
            self.channel_name = payload['channel']['name']

        self.user_id = ""
        if "user_id" in request:
            self.user_id = request['user_id']
        elif "user" in payload and "id" in payload['user']:
            self.user_id = payload['user']['id']

        self.user_name = ""
        if "user_name" in request:
            self.user_name = request['user_name']
        elif "user" in payload and "name" in payload['user']:
            self.user_name = payload['user']['name']

        self.context_root = ""
        if "command" in request:
            self.context_root = request['command']
            self.context_root  = self.context_root.replace('%2F', '')

        self.arguments = ""
        if "text" in request:
            self.arguments = request['text']

        self.arguments  = self.arguments.replace('%3C', '<')
        self.arguments  = self.arguments.replace('%3E', '>')
        self.arguments  = self.arguments.replace('%26', '&')
        self.arguments  = self.arguments.replace('%40', '@')
        self.arguments  = self.arguments.replace('%7C', '|')

        if len(self.arguments):
            self.command = self.arguments.split('+')
            self.operation = self.command.pop(0)
        elif "callback_id" in payload:
            self.command = []
            self.operation = payload['callback_id']
        else:
            self.command = []
            self.operation = ""
            
        self.response_url = ""
        if "response_url" in request:
            self.response_url = request['response_url']
            

    def get_operation(self):
        return self.operation

    def get_command(self):
        return self.command

    def get_context_root(self):
        return self.context_root

    def get_domain(self):
        return self.team_domain

    def get_username(self):
        return self.user_name

    def get_user_id(self):
        return self.user_id

    def get_channel_id(self):
        return self.channel_id

    def get_channel_name(self):
        return self.channel_name

    def get_actions(self):
        return self.actions

    def get_selected_option(self):
        for action in self.actions:
            for key, value in action.items():
                if key == 'selected_options':
                    return value[0]['value']

        return ""
