"""Clean up events and cases, keeping only the test case."""
from google_sheets_client import GoogleSheetsClient
import config
import os
import json

def cleanup_events_and_cases():
    """Delete all events and cases except the test case."""
    print("Cleaning up events and cases...")
    
    # Clean up case files (keep only test case)
    case_dir = config.CASE_FILE_DIR
    if os.path.exists(case_dir):
        test_case_files = [
            "[test case].json",
            "event_test_case.json"
        ]
        
        deleted_count = 0
        for filename in os.listdir(case_dir):
            if filename.endswith('.json') and filename not in test_case_files:
                filepath = os.path.join(case_dir, filename)
                try:
                    os.remove(filepath)
                    deleted_count += 1
                    print(f"Deleted case file: {filename}")
                except Exception as e:
                    print(f"Error deleting {filename}: {e}")
        
        print(f"Deleted {deleted_count} case files")
    
    # Clean up events in Google Sheets (keep only test events)
    try:
        sheets_client = GoogleSheetsClient()
        sheet = sheets_client.get_sheet(config.GOOGLE_SHEETS_EVENTS_ID)
        all_values = sheet.get_all_values()
        
        if len(all_values) <= 1:
            print("No events to clean (only header row)")
            return
        
        # Keep header row and test events
        # Test events might have "test" in the event_id or source
        rows_to_keep = [all_values[0]]  # Header row
        
        deleted_count = 0
        for i, row in enumerate(all_values[1:], start=2):  # Start from row 2 (skip header)
            if len(row) > 0:
                event_id = row[0] if row else ""
                source = row[2] if len(row) > 2 else ""
                
                # Keep test events
                if "test" in event_id.lower() or "test" in source.lower():
                    rows_to_keep.append(row)
                    print(f"Keeping test event: {event_id}")
                else:
                    # Delete this row by clearing it
                    try:
                        sheet.delete_rows(i)
                        deleted_count += 1
                        print(f"Deleted event: {event_id}")
                    except Exception as e:
                        print(f"Error deleting row {i}: {e}")
        
        print(f"Deleted {deleted_count} events from spreadsheet")
        print(f"Kept {len(rows_to_keep) - 1} test events")
        
    except Exception as e:
        print(f"Error cleaning up events in spreadsheet: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    cleanup_events_and_cases()
    print("\nCleanup complete!")

