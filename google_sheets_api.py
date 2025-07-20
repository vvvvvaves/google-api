from creds_and_service import get_credentials, get_sheets_service
from googleapiclient.errors import HttpError


def create_sheet(service, title):
    try:
        spreadsheet = {"properties": {"title": title}}
        spreadsheet = (
            service.spreadsheets()
            .create(body=spreadsheet, fields="spreadsheetId")
            .execute()
        )
        print(f"Spreadsheet ID: {(spreadsheet.get('spreadsheetId'))}")
        return spreadsheet.get("spreadsheetId")
    except HttpError as error:
        print(f"An error occurred: {error}")
        return error

if __name__ == "__main__":
    creds = get_credentials(token_path='token.json', client_secrets_path='client_secrets.json')
    service = get_sheets_service(creds)
    create_sheet(service, "test")