import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'   
]

def get_credentials(token=None, client_secret=None, save_token=False):
    """
    Get Google API credentials using google-auth and google-auth-oauthlib.
    Handles token refresh and initial OAuth flow as needed.
    """
    def _parse_json_data(data, data_type="data"):
        """Helper to parse JSON data from file path, JSON string, or dict"""
        if data is None:
            return None
        
        if isinstance(data, dict):
            return data
        
        if isinstance(data, str):
            # Try as file path first
            if os.path.exists(data):
                try:
                    with open(data, 'r') as f:
                        return json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Error reading {data_type} file: {e}")
                    return None
            
            # Try as JSON string
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                print(f"Invalid {data_type} format")
                return None
        
        return None

    # Get client secret from environment if not provided
    if client_secret is None:
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    
    # Parse token data
    token_data = _parse_json_data(token, "token")
    
    creds = None
    if token_data:
        print(f"Token data: {token_data}")
        print(f"type(token_data): {type(token_data)}")
        
        # Merge client credentials if missing from token data
        if 'client_id' not in token_data or 'client_secret' not in token_data:
            client_secret_data = _parse_json_data(client_secret, "client_secret")
            
            if client_secret_data and 'installed' in client_secret_data:
                token_data = {
                    **token_data,
                    'client_id': client_secret_data['installed']['client_id'],
                    'client_secret': client_secret_data['installed']['client_secret']
                }
                print("Merged token data with client credentials")
        
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    
    # Handle invalid/expired credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Need to run OAuth flow
            client_secret_data = _parse_json_data(client_secret, "client_secret")
            if not client_secret_data:
                raise ValueError("Valid client secret required for OAuth flow")
            
            flow = InstalledAppFlow.from_client_secrets_info(client_secret_data, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials if requested
        if save_token:
            with open("token.json", 'w') as token_file:
                token_file.write(creds.to_json())
            print("Token saved to token.json")
    
    return creds

def get_sheets_service(creds):
    """
    Create a new Google Sheets API service object for the current thread.
    """
    return build("sheets", "v4", credentials=creds)

def get_drive_service(creds):
    """
    Create a new Google Drive API service object for the current thread.
    """
    return build('drive', 'v3', credentials=creds)

def get_gmail_service(creds):
    """
    Create a new Gmail API service object for the current thread.
    """
    return build('gmail', 'v1', credentials=creds)

if __name__ == "__main__":
    creds = get_credentials()
    sheets_service = get_sheets_service(creds)
    print("Sheets service created successfully.")