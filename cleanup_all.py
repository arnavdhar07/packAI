"""Cleanup script to delete all cases and events except test cases."""
import os
import sys
from google_sheets_client import GoogleSheetsClient
from case_file import CaseFile
import config

def cleanup_all():
    """Delete all cases and events except test cases."""
    
    # Clean up case files
    case_dir = config.CASE_FILE_DIR
    if not os.path.exists(case_dir):
        print("Case files directory does not exist")
    else:
        deleted_count = 0
        kept_count = 0
        
        for filename in os.listdir(case_dir):
            if filename.endswith('.json'):
                event_id = filename.replace('.json', '')
                
                # Keep test cases
                if 'test' in event_id.lower() or '[test case]' in filename.lower():
                    kept_count += 1
                    print(f"Keeping test case: {filename}")
                    continue
                
                # Delete non-test cases
                try:
                    file_path = os.path.join(case_dir, filename)
                    os.remove(file_path)
                    deleted_count += 1
                    print(f"Deleted case: {filename}")
                except Exception as e:
                    print(f"Error deleting {filename}: {e}")
        
        print(f"\nCase files: Deleted {deleted_count}, Kept {kept_count}")
    
    # Clean up events in Google Sheets
    try:
        sheets_client = GoogleSheetsClient()
        sheet = sheets_client.get_sheet(config.GOOGLE_SHEETS_EVENTS_ID)
        all_values = sheet.get_all_values()
        
        if len(all_values) <= 1:
            print("No events to clean (only header row)")
            return
        
        # Keep header row
        rows_to_keep = [all_values[0]]  # Header row
        
        deleted_count = 0
        for i in range(len(all_values) - 1, 0, -1):  # Start from bottom to avoid index issues
            row = all_values[i]
            if len(row) > 0:
                event_id = row[0] if row else ""
                
                # Delete all events (no test events to keep)
                try:
                    # Delete row (i+1 because enumerate starts at 1, but we're going backwards)
                    sheet.delete_rows(i + 1)
                    deleted_count += 1
                    if deleted_count % 10 == 0:
                        print(f"Deleted {deleted_count} events...")
                except Exception as e:
                    print(f"Error deleting row {i+1}: {e}")
        
        print(f"\nEvents: Deleted {deleted_count} events from spreadsheet")
        print("All events deleted (no test events kept)")
        
    except Exception as e:
        print(f"Error cleaning up events in spreadsheet: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 60)
    print("Cleaning up all cases and events (except test cases)")
    print("=" * 60)
    response = input("Are you sure you want to delete all cases and events? (yes/no): ")
    if response.lower() == 'yes':
        cleanup_all()
        print("\n" + "=" * 60)
        print("Cleanup complete!")
        print("=" * 60)
    else:
        print("Cleanup cancelled.")

