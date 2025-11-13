"""Client for interacting with Google Sheets."""
import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Optional
import os

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

class GoogleSheetsClient:
    """Client for reading and writing to Google Sheets."""
    
    def __init__(self, credentials_path: str = "credentials.json"):
        """Initialize the Google Sheets client.
        
        Args:
            credentials_path: Path to Google service account credentials JSON file
        """
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(
                f"Credentials file not found at {credentials_path}. "
                "Please download your service account credentials from Google Cloud Console."
            )
        
        creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
        self.client = gspread.authorize(creds)
    
    def get_sheet(self, spreadsheet_id: str, sheet_name: Optional[str] = None):
        """Get a specific sheet from a spreadsheet.
        
        Args:
            spreadsheet_id: The ID of the Google Spreadsheet
            sheet_name: Optional name of the specific sheet (uses first sheet if None)
        """
        spreadsheet = self.client.open_by_key(spreadsheet_id)
        if sheet_name:
            return spreadsheet.worksheet(sheet_name)
        return spreadsheet.sheet1
    
    def read_all_rows(self, spreadsheet_id: str, sheet_name: Optional[str] = None) -> List[List]:
        """Read all rows from a sheet.
        
        Args:
            spreadsheet_id: The ID of the Google Spreadsheet
            sheet_name: Optional name of the specific sheet
        """
        sheet = self.get_sheet(spreadsheet_id, sheet_name)
        return sheet.get_all_values()
    
    def read_as_dicts(self, spreadsheet_id: str, sheet_name: Optional[str] = None) -> List[Dict]:
        """Read sheet data as list of dictionaries (first row as keys).
        
        Args:
            spreadsheet_id: The ID of the Google Spreadsheet
            sheet_name: Optional name of the specific sheet
        """
        sheet = self.get_sheet(spreadsheet_id, sheet_name)
        return sheet.get_all_records()
    
    def append_row(self, spreadsheet_id: str, values: List, sheet_name: Optional[str] = None):
        """Append a row to a sheet.
        
        Args:
            spreadsheet_id: The ID of the Google Spreadsheet
            values: List of values to append
            sheet_name: Optional name of the specific sheet
        """
        sheet = self.get_sheet(spreadsheet_id, sheet_name)
        sheet.append_row(values)
    
    def update_cell(self, spreadsheet_id: str, row: int, col: int, value, sheet_name: Optional[str] = None):
        """Update a specific cell.
        
        Args:
            spreadsheet_id: The ID of the Google Spreadsheet
            row: Row number (1-indexed)
            col: Column number (1-indexed)
            value: Value to set
            sheet_name: Optional name of the specific sheet
        """
        sheet = self.get_sheet(spreadsheet_id, sheet_name)
        sheet.update_cell(row, col, value)
    
    def update_event(self, spreadsheet_id: str, event_id: str, event_type: str, details: str, sheet_name: Optional[str] = None):
        """Update event_type and details for a specific event.
        
        Args:
            spreadsheet_id: The ID of the Google Spreadsheet
            event_id: The event ID to update
            event_type: The event type to set
            details: The details to set
            sheet_name: Optional name of the specific sheet
        """
        sheet = self.get_sheet(spreadsheet_id, sheet_name)
        all_values = sheet.get_all_values()
        
        # Find the row with matching event_id (assuming event_id is in first column)
        for i, row in enumerate(all_values, start=1):
            if row and row[0] == event_id:
                # Update event_type (column 2) and details (column 5)
                # Columns: event_id, event_type, source, timestamp, details, subscribed_agents
                sheet.update_cell(i, 2, event_type)  # event_type column
                sheet.update_cell(i, 5, details)  # details column
                return
        
        raise ValueError(f"Event {event_id} not found in spreadsheet")

