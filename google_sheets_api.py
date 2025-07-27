import json
from .creds_and_service import get_credentials, get_sheets_service
from googleapiclient.errors import HttpError
import google_auth_httplib2
import httplib2

"""
The google-api-python-client library is built on top of the httplib2 library, which is not thread-safe. Therefore, if you are running as a multi-threaded application, each thread that you are making requests from must have its own instance of httplib2.Http().
https://github.com/nithinmurali/pygsheets/issues/291
https://googleapis.github.io/google-api-python-client/docs/thread_safety.html
"""
def create_sheet(service, title):
    try:
        http = google_auth_httplib2.AuthorizedHttp(get_credentials(), http=httplib2.Http())
        spreadsheet = {"properties": {"title": title}}
        spreadsheet = (
            service.spreadsheets()
            .create(body=spreadsheet, fields="spreadsheetId")
            .execute(http=http)
        )
        print(f"✓ Spreadsheet ID: {(spreadsheet.get('spreadsheetId'))}")
        return spreadsheet.get("spreadsheetId")
    except HttpError as error:
        print(f"An error occurred: {error}")
        return error


def add_sheet_to_spreadsheet(service, spreadsheet_id, sheet_title=None, num_columns=50, num_rows=None):
    """
    Adds a new sheet (tab) to an existing Google Spreadsheet.
    :param service: Google Sheets API service instance
    :param spreadsheet_id: ID of the spreadsheet
    :param sheet_title: Optional title for the new sheet. If None, uses 'SheetN'.
    :param num_columns: Optional number of columns for the new sheet.
    :param num_rows: Optional number of rows for the new sheet.
    :return: The new sheet's ID, or None if failed.
    """
    try:
        # If no title provided, generate 'SheetN' where N is next available
        if sheet_title is None:
            http = google_auth_httplib2.AuthorizedHttp(get_credentials(), http=httplib2.Http())
            spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute(http=http)
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
        http = google_auth_httplib2.AuthorizedHttp(get_credentials(), http=httplib2.Http())
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute(http=http)
        new_sheet_id = response['replies'][0]['addSheet']['properties']['sheetId']
        print(f"✓ Added sheet '{sheet_title}' with ID {new_sheet_id}")

        # If custom columns or rows are specified, update the sheet properties safely
        grid_properties = {}
        fields = []
        if num_columns is not None and num_columns > 0:
            grid_properties["columnCount"] = num_columns
            fields.append("gridProperties.columnCount")
        if num_rows is not None and num_rows > 0:
            grid_properties["rowCount"] = num_rows
            fields.append("gridProperties.rowCount")
        if grid_properties:
            update_properties = {
                "sheetId": new_sheet_id,
                "gridProperties": grid_properties
            }
            update_request_body = {
                "requests": [
                    {
                        "updateSheetProperties": {
                            "properties": update_properties,
                            "fields": ",".join(fields)
                        }
                    }
                ]
            }
            http = google_auth_httplib2.AuthorizedHttp(get_credentials(), http=httplib2.Http())
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=update_request_body
            ).execute(http=http)
            print(f"✓ Updated sheet '{sheet_title}' with columns={num_columns}, rows={num_rows}")
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
    if isinstance(schema_path, dict):
        schema = schema_path
    else:
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
        http = google_auth_httplib2.AuthorizedHttp(get_credentials(), http=httplib2.Http())
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [table_request]}
        ).execute(http=http)
        print("✓ Table created")

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
        http = google_auth_httplib2.AuthorizedHttp(get_credentials(), http=httplib2.Http())
        width_response = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [column_width_request]}
        ).execute(http=http)
        print("Column width set")

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
        http = google_auth_httplib2.AuthorizedHttp(get_credentials(), http=httplib2.Http())
        wrap_response = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [wrap_request]}
        ).execute(http=http)
        print("Text wrapping applied")
        return response
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


def _get_sheet_name_by_id(service, spreadsheet_id, sheet_id):
    """
    Helper to get the sheet name from its ID using the Sheets API.
    """
    try:
        http = google_auth_httplib2.AuthorizedHttp(get_credentials(), http=httplib2.Http())
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute(http=http)
        for sheet in spreadsheet.get('sheets', []):
            if sheet['properties']['sheetId'] == sheet_id:
                return sheet['properties']['title']
        raise ValueError(f"Sheet ID {sheet_id} not found in spreadsheet {spreadsheet_id}")
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


def add_rows_to_sheet(service, spreadsheet_id, sheet_id, rows, column_order):
    """
    Appends one or more dictionaries as rows to a Google Sheet, using the provided column order.
    :param service: Google Sheets API service instance
    :param spreadsheet_id: ID of the spreadsheet
    :param sheet_id: ID of the sheet/tab (as integer)
    :param rows: list of dicts to append as rows
    :param column_order: list of column names (order for the sheet)
    """
    # Accept single dict or list of dicts
    if isinstance(rows, dict):
        rows = [rows]

    # Prepare values in correct order
    values = []
    for item in rows:
        row = []
        for col in column_order:
            col_value = item.get(col, "")
            if col_value is None:
                row.append("")
            elif isinstance(col_value, list):
                if len(col_value) > 0:
                    str_value = " ".join(col_value)
                else:
                    str_value = ""
                row.append(str_value)
            else:
                row.append(col_value)
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
        http = google_auth_httplib2.AuthorizedHttp(get_credentials(), http=httplib2.Http())
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f'{sheet_name}!A1',  # Assumes table starts at A1
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute(http=http)
        # print(f"{len(values)} row(s) appended.")
        return result
    except HttpError as error:
        print(f"An error occurred: {error}")
        if error.response_status == 400:
            print(json.dumps(rows, indent=4))
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def _col_num_to_letter(n):
    """Convert a 1-indexed column number to a column letter (e.g., 1 -> 'A', 27 -> 'AA')."""
    result = ''
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def get_rows_from_range(service, spreadsheet_id, sheet_id, start_row, end_row, start_col=None, end_col=None):
    """
    Retrieves rows from a specific range in a Google Sheet using numeric indices.
    :param service: Google Sheets API service instance
    :param spreadsheet_id: ID of the spreadsheet
    :param sheet_id: ID of the sheet/tab (as integer)
    :param start_row: First row number (1-indexed, inclusive)
    :param end_row: Last row number (1-indexed, inclusive)
    :param start_col: First column number (1-indexed, optional)
    :param end_col: Last column number (1-indexed, optional, exclusive)
    :return: List of rows (each row is a list of cell values)
    """
    sheet_name = _get_sheet_name_by_id(service, spreadsheet_id, sheet_id)
    if not sheet_name:
        print(f"Could not resolve sheet name for sheet_id {sheet_id}")
        return None
    # Build A1 notation
    if start_col and end_col:
        start_col_letter = _col_num_to_letter(start_col)
        end_col_letter = _col_num_to_letter(end_col - 1)
        range_notation = f"{sheet_name}!{start_col_letter}{start_row}:{end_col_letter}{end_row}"
    elif start_col:
        start_col_letter = _col_num_to_letter(start_col)
        range_notation = f"{sheet_name}!{start_col_letter}{start_row}:{start_col_letter}{end_row}"
    else:
        range_notation = f"{sheet_name}!{start_row}:{end_row}"
    try:
        http = google_auth_httplib2.AuthorizedHttp(get_credentials(), http=httplib2.Http())
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_notation
        ).execute(http=http)
        rows = result.get('values', [])
        return rows
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


def get_all_rows_from_sheet(service, spreadsheet_id, sheet_id):
    """
    Retrieves all non-empty rows from a Google Sheet by sheet ID, ensuring each row has the same number of columns as the header (filling missing cells with empty strings).
    :param service: Google Sheets API service instance
    :param spreadsheet_id: ID of the spreadsheet
    :param sheet_id: ID of the sheet/tab (as integer)
    :return: List of rows (each row is a list of cell values, padded to header length)
    """
    sheet_name = _get_sheet_name_by_id(service, spreadsheet_id, sheet_id)
    if not sheet_name:
        print(f"Could not resolve sheet name for sheet_id {sheet_id}")
        return None
    try:
        http = google_auth_httplib2.AuthorizedHttp(get_credentials(), http=httplib2.Http())
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=sheet_name
        ).execute(http=http)
        rows = result.get('values', [])
        if not rows:
            return []
        num_columns = len(rows[0])  # Assume first row is header
        padded_rows = [row + [""] * (num_columns - len(row)) for row in rows]
        return padded_rows
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