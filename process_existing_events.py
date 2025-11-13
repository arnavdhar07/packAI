"""Script to process existing events from the spreadsheet."""
import sys
from google_sheets_client import GoogleSheetsClient
from property_agent import PropertyManagementAgent
from case_file import CaseFile
import config

def process_existing_events():
    """Process all events from the spreadsheet that haven't been processed yet."""
    print("Processing existing events from spreadsheet...")
    
    try:
        sheets_client = GoogleSheetsClient()
        property_agent = PropertyManagementAgent(sheets_client)
        
        # Read all events from spreadsheet
        events = sheets_client.read_as_dicts(config.GOOGLE_SHEETS_EVENTS_ID)
        
        print(f"Found {len(events)} event(s) in spreadsheet")
        
        processed_count = 0
        skipped_count = 0
        
        for event_row in events:
            event_id = event_row.get('event_id', '')
            
            if not event_id:
                continue
            
            # Check if case file already exists
            existing_case = CaseFile.load(event_id)
            if existing_case:
                print(f"Skipping {event_id} - already processed")
                skipped_count += 1
                continue
            
            # Check if subscribed to property management agent
            subscribed_agents = event_row.get('subscribed_agents', '')
            if config.PROPERTY_MANAGEMENT_AGENT_ID not in subscribed_agents:
                print(f"Skipping {event_id} - not subscribed to property management agent")
                skipped_count += 1
                continue
            
            # Get source content - we need to read it from somewhere
            # For existing events, we'll use the details field if available, or create a placeholder
            source = event_row.get('source', 'unknown')
            details = event_row.get('details', '')
            content = details if details else f"Event from {source}"
            
            print(f"\nProcessing event: {event_id}")
            
            try:
                case_file = property_agent.process_event(event_id, content, source)
                print(f"✓ Processed {event_id}")
                processed_count += 1
            except Exception as e:
                print(f"✗ Error processing {event_id}: {e}")
        
        print(f"\n{'='*60}")
        print(f"Processing complete!")
        print(f"  Processed: {processed_count}")
        print(f"  Skipped: {skipped_count}")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    process_existing_events()

