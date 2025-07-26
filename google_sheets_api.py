import json
from .creds_and_service import get_credentials, get_sheets_service
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


def add_sheet_to_spreadsheet(service, spreadsheet_id, sheet_title=None):
    """
    Adds a new sheet (tab) to an existing Google Spreadsheet.
    :param service: Google Sheets API service instance
    :param spreadsheet_id: ID of the spreadsheet
    :param sheet_title: Optional title for the new sheet. If None, uses 'SheetN'.
    :return: The new sheet's ID, or None if failed.
    """
    try:
        # If no title provided, generate 'SheetN' where N is next available
        if sheet_title is None:
            spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            existing_titles = [sheet['properties']['title'] for sheet in spreadsheet.get('sheets', [])]
            sheet_title = f"Sheet{len(existing_titles) + 1}"
        request_body = {
            "requests": [
                {
                    "addSheet": {
                        "properties": {
                            "title": sheet_title
                        }
                    }
                }
            ]
        }
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()
        new_sheet_id = response['replies'][0]['addSheet']['properties']['sheetId']
        print(f"Added sheet '{sheet_title}' with ID {new_sheet_id}")
        return new_sheet_id
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


def create_table_from_schema(service, spreadsheet_id, sheet_id, schema_path, table_name="Flashcards Table", start_row=0, start_col=0):
    """
    Creates a Google Sheets table based on a JSON schema.
    :param service: Google Sheets API service instance
    :param spreadsheet_id: ID of the spreadsheet
    :param sheet_id: ID of the sheet/tab within the spreadsheet
    :param schema_path: Path to the JSON schema file
    :param table_name: Name for the table
    :param start_row: Starting row index for the table
    :param start_col: Starting column index for the table
    """

    import re
    # Check that table_name contains only letters, numbers, underscores, or spaces
    if not re.match(r'^[A-Za-z0-9_ ]+$', table_name):
        raise ValueError("Table name must contain only letters, numbers, underscores, or spaces.")
    # Load schema
    with open(schema_path, "r") as f:
        schema = json.load(f)
    properties = schema["properties"]

    # Map JSON schema types to Sheets table column types
    type_map = {
        "string": "TEXT",
        "number": "TEXT",
        "integer": "TEXT",
        "boolean": "TEXT"
    }

    column_properties = []
    col_idx = 0
    for prop, details in properties.items():
        col_type = type_map.get(details.get("type"), "TEXT")
        col_def = {
            "columnIndex": col_idx,
            "columnName": prop.capitalize(),
            "columnType": col_type
        }
        # Handle enum as dropdown
        if "enum" in details:
            col_def["columnType"] = "DROPDOWN"
            col_def["dataValidationRule"] = {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [{"userEnteredValue": v} for v in details["enum"]]
                }
            }
        column_properties.append(col_def)
        col_idx += 1

    # Table range: for now, just header row (expand as needed)
    end_col = start_col + len(column_properties)
    end_row = start_row + 2  # header + 1 empty row

    table_request = {
        "addTable": {
            "table": {
                "name": table_name,
                "tableId": table_name.lower().replace(' ', '_'),
                "range": {
                    "sheetId": sheet_id,
                    "startColumnIndex": start_col,
                    "endColumnIndex": end_col,
                    "startRowIndex": start_row,
                    "endRowIndex": end_row,
                },
                "columnProperties": column_properties
            }
        }
    }

    try:
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [table_request]}
        ).execute()
        print("Table created:", response)

        # Set default column width for all columns in the table
        column_width_request = {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": start_col,
                    "endIndex": end_col
                },
                "properties": {
                    "pixelSize": 200  # Set your desired width in pixels
                },
                "fields": "pixelSize"
            }
        }
        width_response = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [column_width_request]}
        ).execute()
        print("Column width set:", width_response)

        # Set text wrapping for the table range
        wrap_request = {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": start_row,
                    "endRowIndex": end_row,
                    "startColumnIndex": start_col,
                    "endColumnIndex": end_col
                },
                "cell": {
                    "userEnteredFormat": {
                        "wrapStrategy": "WRAP"
                    }
                },
                "fields": "userEnteredFormat.wrapStrategy"
            }
        }
        wrap_response = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [wrap_request]}
        ).execute()
        print("Text wrapping applied:", wrap_response)
        return response
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


def _get_sheet_name_by_id(service, spreadsheet_id, sheet_id):
    """
    Helper to get the sheet name from its ID using the Sheets API.
    """
    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        for sheet in spreadsheet.get('sheets', []):
            if sheet['properties']['sheetId'] == sheet_id:
                return sheet['properties']['title']
        raise ValueError(f"Sheet ID {sheet_id} not found in spreadsheet {spreadsheet_id}")
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


def add_rows_to_sheet(service, spreadsheet_id, sheet_id, data_dicts, column_order):
    """
    Appends one or more dictionaries as rows to a Google Sheet, using the provided column order.
    :param service: Google Sheets API service instance
    :param spreadsheet_id: ID of the spreadsheet
    :param sheet_id: ID of the sheet/tab (as integer)
    :param data_dicts: dict or list of dicts to append as rows
    :param column_order: list of column names (order for the sheet)
    """
    # Accept single dict or list of dicts
    if isinstance(data_dicts, dict):
        data_dicts = [data_dicts]

    # Prepare values in correct order
    values = []
    for item in data_dicts:
        row = [item.get(col, "") for col in column_order]
        values.append(row)

    # Get sheet name from sheet_id
    sheet_name = _get_sheet_name_by_id(service, spreadsheet_id, sheet_id)
    if not sheet_name:
        print(f"Could not resolve sheet name for sheet_id {sheet_id}")
        return None

    body = {
        'values': values
    }
    try:
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f'{sheet_name}!A1',  # Assumes table starts at A1
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        print(f"{len(values)} row(s) appended.")
        return result
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None



if __name__ == "__main__":
    creds = get_credentials(token_path='token.json', client_secrets_path='client_secrets.json')
    service = get_sheets_service(creds)
    spreadsheet_id = create_sheet(service, "test")
    sheet_id = 0  # or the actual sheet/tab ID
    create_table_from_schema(
        service,
        spreadsheet_id,
        sheet_id,
        "response_format.json"
    )

    # Example usage of add_rows_to_sheet
    example_data = [
        {
            "title": "Sample Title",
            "question": "What is Python?",
            "answer": "A programming language.",
            "priority": 1,
            "difficulty": "easy",
            "category": "technical",
            "topic": "python"
        },
        {
            "title": "Another Card",
            "question": "What is Docker?",
            "answer": "A containerization platform.",
            "priority": 2,
            "difficulty": "medium",
            "category": "technical",
            "topic": "docker"
        }
    ]
    example_column_order = [
        "title", "question", "answer", "priority", "difficulty", "category", "topic"
    ]
   
    add_rows_to_sheet(service, spreadsheet_id, sheet_id, example_data, example_column_order)