"""Main application runner for the MVP."""
import time
import sys
from google_drive_monitor import GoogleDriveMonitor
from google_sheets_client import GoogleSheetsClient
from event_creator import EventCreator
from property_agent import PropertyManagementAgent
from case_file import CaseFile
import config

def main():
    """Main application loop."""
    print("Starting Property Management MVP...")
    
    # Initialize clients
    try:
        print("Initializing Google services...")
        drive_monitor = GoogleDriveMonitor()
        sheets_client = GoogleSheetsClient()
        event_creator = EventCreator(sheets_client)
        property_agent = PropertyManagementAgent(sheets_client)
        print("Google services initialized successfully.")
    except Exception as e:
        print(f"Error initializing services: {e}")
        print("\nPlease ensure:")
        print("1. You have downloaded credentials.json from Google Cloud Console")
        print("2. The credentials file is in the project root directory")
        print("3. The service account has access to the Drive folder and Spreadsheets")
        sys.exit(1)
    
    # Check configuration
    if not config.GOOGLE_DRIVE_FOLDER_ID:
        print("Warning: GOOGLE_DRIVE_FOLDER_ID not set. Please set it in .env file.")
        print("You can find the folder ID in the Google Drive URL.")
        return
    
    if not config.OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not set. Please set it in .env file.")
        sys.exit(1)
    
    print(f"\nMonitoring Google Drive folder: {config.GOOGLE_DRIVE_FOLDER_ID}")
    print(f"Events spreadsheet: {config.GOOGLE_SHEETS_EVENTS_ID}")
    print(f"Maintenance companies spreadsheet: {config.GOOGLE_SHEETS_MAINTENANCE_ID}")
    print(f"Using OpenAI model: {config.OPENAI_MODEL}")
    print("\nStarting monitoring loop (press Ctrl+C to stop)...\n")
    
    # Main monitoring loop
    try:
        while True:
            # Check for new files in Google Drive folder
            new_files = drive_monitor.get_new_files(config.GOOGLE_DRIVE_FOLDER_ID)
            
            if new_files:
                print(f"Found {len(new_files)} new file(s)")
                
                for file_info in new_files:
                    file_id = file_info['id']
                    file_name = file_info['name']
                    
                    print(f"\nProcessing file: {file_name} (ID: {file_id})")
                    
                    # Download file content
                    content = drive_monitor.download_file_content(file_id)
                    
                    if content:
                        # Create event from content
                        try:
                            event_id, content_for_agent = event_creator.create_event(content, file_name)
                            print(f"Event created: {event_id}")
                            
                            # Event is automatically subscribed to property management agent
                            # Process event with agent (agent will fill in event_type and details)
                            print(f"Processing event {event_id} with property management agent...")
                            case_file = property_agent.process_event(event_id, content_for_agent, file_name)
                            
                            # Print case file summary
                            print("\n" + "="*60)
                            print(case_file.get_summary())
                            print("="*60 + "\n")
                                
                        except Exception as e:
                            print(f"Error processing file {file_name}: {e}")
                    else:
                        print(f"Could not extract content from {file_name} (unsupported file type)")
                    
                    # Mark file as processed
                    drive_monitor.mark_file_processed(file_id)
            
            # Wait before checking again (poll every 30 seconds)
            time.sleep(30)
            
    except KeyboardInterrupt:
        print("\n\nStopping monitor...")
        print("Case files saved in:", config.CASE_FILE_DIR)
    except Exception as e:
        print(f"\nError in main loop: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

