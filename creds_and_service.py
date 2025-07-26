import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
]

def get_credentials(token_path='token.json', client_secrets_path='client_secrets.json'):
    """
    Get Google API credentials using google-auth and google-auth-oauthlib.
    Handles token refresh and initial OAuth flow as needed.
    """
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
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

if __name__ == "__main__":
    creds = get_credentials()
    sheets_service = get_sheets_service(creds)
    print("Sheets service created successfully.")