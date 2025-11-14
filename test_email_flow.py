"""Test script to simulate an email being processed through the system."""
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from google_sheets_client import GoogleSheetsClient
from event_creator import EventCreator
from property_agent import PropertyManagementAgent
import config

def test_email_flow():
    """Test the complete email processing flow."""
    print("=" * 60)
    print("Testing Email Processing Flow")
    print("=" * 60)
    
    # Initialize clients
    print("\n1. Initializing services...")
    try:
        sheets_client = GoogleSheetsClient()
        event_creator = EventCreator(sheets_client)
        property_agent = PropertyManagementAgent(sheets_client)
        print("   ✓ All services initialized")
    except Exception as e:
        print(f"   ✗ Error initializing services: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Simulate an email
    print("\n2. Simulating incoming email...")
    test_email_content = """Subject: Urgent: Leaking Pipe in Unit 3B

From: tenant@example.com

Hi Property Management,

I'm writing to report a serious issue in my unit (3B). There's a pipe that's been leaking in the kitchen for the past few hours. Water is starting to pool on the floor and I'm concerned about water damage.

The leak is coming from under the kitchen sink. I've tried to turn off the water valve but it seems stuck. This needs immediate attention as the water is spreading.

Please send someone as soon as possible.

Thank you,
John Smith
Unit 3B
Phone: (555) 123-4567"""
    
    source = f"gmail:tenant@example.com:test_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    print(f"   ✓ Email simulated from: tenant@example.com")
    print(f"   Source: {source}")
    
    # Create event (event creator uses OpenAI to analyze)
    print("\n3. Creating event from email...")
    print("   (Event creator will use OpenAI to analyze content and determine event_type/details)")
    try:
        event_id, event_type, details = event_creator.create_event(test_email_content, source)
        print(f"   ✓ Event created: {event_id} (type: {event_type})")
    except Exception as e:
        print(f"   ✗ Error creating event: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Process subscribed events with agent
    print("\n4. Checking for subscribed events and processing...")
    print("   (Property agent will check if subscribed and process maintenance-related events)")
    try:
        case_files = property_agent.check_and_process_subscribed_events()
        if not case_files:
            print(f"   ⚠ No cases created (event may not be maintenance-related)")
            return False
        
        case_file = case_files[0]  # Get the first case file
        print(f"   ✓ Event processed successfully")
        print(f"   ✓ Case file created: {case_file.event_id}.json")
    except Exception as e:
        print(f"   ✗ Error processing subscribed events: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Verify case file
    print("\n5. Verifying case file...")
    case_file_path = os.path.join(config.CASE_FILE_DIR, f"{case_file.event_id}.json")
    if os.path.exists(case_file_path):
        print(f"   ✓ Case file exists: {case_file_path}")
        
        # Show summary
        print("\n6. Case File Summary:")
        print("-" * 60)
        print(case_file.get_summary())
        print("-" * 60)
        
        # Show actions
        print(f"\n   Actions taken: {len(case_file.actions)}")
        for i, action in enumerate(case_file.actions, 1):
            action_type = action.get('type', 'unknown')
            print(f"   {i}. {action_type}")
            if action_type == 'generated_email':
                email_data = action.get('data', {})
                print(f"      To: {email_data.get('to', 'N/A')}")
                print(f"      Subject: {email_data.get('subject', 'N/A')[:50]}...")
        
        return True
    else:
        print(f"   ✗ Case file not found: {case_file_path}")
        return False

if __name__ == "__main__":
    success = test_email_flow()
    print("\n" + "=" * 60)
    if success:
        print("✓ TEST PASSED - System is working correctly!")
    else:
        print("✗ TEST FAILED - Check errors above")
    print("=" * 60)
    sys.exit(0 if success else 1)

