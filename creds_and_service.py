# Create credentials from the TOKEN dictionary
from oauth2client.client import OAuth2Credentials
import json
import os
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def get_credentials_from_client_secrets(client_secrets_path='client_secrets.json'):
    """
    Get credentials from client secrets.
    Use this function when you get access exception due to expired token / "invalid_grant".
    """

    SCOPES = [
        'https://www.googleapis.com/auth/drive.file',
    ]

    # Load client secrets
    if os.path.exists(client_secrets_path):
        with open(client_secrets_path, 'r') as f:
            client_secrets = json.load(f)
    elif os.environ.get('CLIENT_SECRET'):
        client_secrets = json.loads(os.environ.get('CLIENT_SECRET'))
    else:
        raise FileNotFoundError("client_secrets.json not found and CLIENT_SECRET environment variable is not set")

    # Create flow object from client secrets
    flow = client.flow_from_clientsecrets(
        client_secrets_path,
        SCOPES,
        redirect_uri='http://localhost'
    )
    
    # Run local server to get authorization
    creds = tools.run_flow(flow, Storage('token.json'))

    return creds

def get_credentials_from_token(token_path='token.json'):
    from oauth2client.client import OAuth2Credentials
    import json
    import os

    if os.path.exists(token_path):
        with open(token_path, 'r') as f:
            TOKEN = json.load(f)
    elif os.environ.get('TOKEN'):
        TOKEN = json.loads(os.environ.get('TOKEN'))
    else:
        raise FileNotFoundError("token.json not found and TOKEN environment variable is not set")
    
    TOKEN.pop('invalid')
    TOKEN.pop('_class')
    TOKEN.pop('_module')

    creds = OAuth2Credentials(**TOKEN)
    
    return creds

def get_credentials(token_path='token.json', client_secrets_path='client_secrets.json'):
    if os.path.exists(token_path):
        return get_credentials_from_token(token_path)
    else:
        return get_credentials_from_client_secrets(client_secrets_path)

def get_sheets_service(creds):
    return build("sheets", "v4", credentials=creds)

def get_drive_service(creds):
    return build('drive', 'v3', credentials=creds)

if __name__ == "__main__":
    create_sheet("test")