"""Perform a single scan for new emails and files."""
import os
import sys
from google_drive_monitor import GoogleDriveMonitor
from gmail_monitor import GmailMonitor
from google_sheets_client import GoogleSheetsClient
from event_creator import EventCreator
from property_agent import PropertyManagementAgent
import config

# Global variables to cache initialized clients
_initialized = False
_drive_monitor = None
_gmail_monitor = None
_sheets_client = None
_event_creator = None
_property_agent = None

def initialize_clients():
    """Initialize all clients (cached for performance)."""
    global _initialized, _drive_monitor, _gmail_monitor, _sheets_client, _event_creator, _property_agent
    
    if _initialized:
        return _drive_monitor, _gmail_monitor, _sheets_client, _event_creator, _property_agent
    
    # Ensure we're in the project root directory for credentials.json
    # Get the directory where this file (scan_once.py) is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = script_dir  # scan_once.py is in project root
    
    # Get absolute path to credentials.json
    credentials_path = os.path.join(project_root, "credentials.json")
    gmail_credentials_path = os.path.join(project_root, "gmail_credentials.json")
    gmail_token_path = os.path.join(project_root, "gmail_token.json")
    
    # Change to project root if we're not already there
    original_cwd = os.getcwd()
    if os.path.basename(original_cwd) == 'ui':
        # We're in the ui/ directory, need to go up one level
        os.chdir(project_root)
    
    try:
        _drive_monitor = GoogleDriveMonitor(credentials_path=credentials_path)
        _sheets_client = GoogleSheetsClient(credentials_path=credentials_path)
        _event_creator = EventCreator(_sheets_client)
        _property_agent = PropertyManagementAgent(_sheets_client)
        
        # Initialize Gmail monitor if enabled
        _gmail_monitor = None
        if config.GMAIL_ENABLED:
            try:
                email_address = config.GMAIL_EMAIL_ADDRESS if config.GMAIL_EMAIL_ADDRESS else None
                _gmail_monitor = GmailMonitor(
                    credentials_path=gmail_credentials_path,
                    token_path=gmail_token_path,
                    email_address=email_address
                )
            except Exception as e:
                print(f"Warning: Could not initialize Gmail monitor: {e}")
                _gmail_monitor = None
        
        _initialized = True
        return _drive_monitor, _gmail_monitor, _sheets_client, _event_creator, _property_agent
        
    except Exception as e:
        print(f"Error initializing clients: {e}")
        raise

def scan_once():
    """Perform a single scan for new emails and files.
    
    Returns:
        Dictionary with scan results
    """
    results = {
        'success': True,
        'emails_processed': 0,
        'files_processed': 0,
        'events_created': 0,
        'cases_created': 0,
        'errors': []
    }
    
    try:
        # Initialize clients
        drive_monitor, gmail_monitor, sheets_client, event_creator, property_agent = initialize_clients()
        
        # Check for new emails from Gmail (only last 5 minutes for testing)
        if gmail_monitor:
            try:
                new_emails = gmail_monitor.get_new_emails(max_age_minutes=5)
                
                if new_emails:
                    print(f"Found {len(new_emails)} new email(s)")
                    results['emails_processed'] = len(new_emails)
                    
                    for email_data in new_emails:
                        message_id = email_data['message_id']
                        subject = email_data['subject']
                        from_email = email_data['from']
                        body = email_data['body']
                        
                        print(f"\nProcessing email: {subject} (From: {from_email})")
                        
                        # Create email content string for event
                        email_content = f"Subject: {subject}\nFrom: {from_email}\n\n{body}"
                        source = f"gmail:{from_email}:{message_id}"
                        
                        # Create event from email (event creator extracts lightweight metadata)
                        try:
                            event_id, event_type, metadata = event_creator.create_event(email_content, source)
                            results['events_created'] += 1
                            print(f"Event created: {event_id} (type: {event_type}, urgency: {metadata.get('urgency')})")
                            
                            # Mark email as processed and read
                            gmail_monitor.mark_email_processed(message_id)
                            try:
                                gmail_monitor.mark_email_read(message_id)
                            except Exception as e:
                                # Non-critical error - email was processed, just couldn't mark as read
                                print(f"Warning: Could not mark email as read (non-critical): {e}")
                                
                        except Exception as e:
                            error_msg = f"Error processing email {subject}: {e}"
                            print(error_msg)
                            results['errors'].append(error_msg)
            except Exception as e:
                error_msg = f"Error checking Gmail: {e}"
                print(error_msg)
                results['errors'].append(error_msg)
        
        # Check for new files in Google Drive folder
        if config.GOOGLE_DRIVE_FOLDER_ID:
            try:
                new_files = drive_monitor.get_new_files(config.GOOGLE_DRIVE_FOLDER_ID)
                
                if new_files:
                    print(f"Found {len(new_files)} new file(s)")
                    results['files_processed'] = len(new_files)
                    
                    for file_info in new_files:
                        file_id = file_info['id']
                        file_name = file_info['name']
                        
                        print(f"\nProcessing file: {file_name} (ID: {file_id})")
                        
                        # Download file content
                        content = drive_monitor.download_file_content(file_id)
                        
                        if content:
                            # Create event from content (event creator extracts lightweight metadata)
                            try:
                                # Create source string for Google Drive
                                source_str = f"google_drive:{file_id}"
                                event_id, event_type, metadata = event_creator.create_event(content, source_str)
                                results['events_created'] += 1
                                print(f"Event created: {event_id} (type: {event_type}, urgency: {metadata.get('urgency')})")
                                    
                            except Exception as e:
                                error_msg = f"Error processing file {file_name}: {e}"
                                print(error_msg)
                                results['errors'].append(error_msg)
                        else:
                            print(f"Could not extract content from {file_name} (unsupported file type)")
                        
                        # Mark file as processed
                        drive_monitor.mark_file_processed(file_id)
            except Exception as e:
                error_msg = f"Error checking Google Drive: {e}"
                error_str = str(e)
                # Check if it's a non-critical API not enabled error
                if 'API has not been used' in error_str or 'accessNotConfigured' in error_str:
                    print(f"Warning (non-critical): {error_msg}")
                    # Don't add to errors - this is a configuration issue, not a scan failure
                else:
                    print(error_msg)
                    results['errors'].append(error_msg)
        
        # After creating events, check for subscribed events and process them
        print("\nChecking for subscribed events to process...")
        try:
            case_files = property_agent.check_and_process_subscribed_events()
            results['cases_created'] = len(case_files)
            if case_files:
                print(f"Created {len(case_files)} case(s) from subscribed events")
        except Exception as e:
            error_msg = f"Error processing subscribed events: {e}"
            print(error_msg)
            results['errors'].append(error_msg)
        
        # Only mark as failed if there are critical errors
        # Filter out non-critical errors (API not enabled, email marking issues)
        critical_errors = []
        for error in results.get('errors', []):
            error_str = str(error)
            # Skip non-critical errors
            if 'insufficient authentication scopes' in error_str.lower():
                continue
            if 'mark email as read' in error_str.lower():
                continue
            if 'API has not been used' in error_str:
                continue
            if 'accessNotConfigured' in error_str:
                continue
            critical_errors.append(error)
        
        if critical_errors:
            results['success'] = False
            results['errors'] = critical_errors
        else:
            # Clear errors if they're all non-critical
            results['success'] = True
            results['errors'] = []
        
        return results
        
    except Exception as e:
        error_msg = f"Error during scan: {e}"
        print(error_msg)
        results['success'] = False
        results['errors'].append(error_msg)
        return results

if __name__ == "__main__":
    # For testing
    result = scan_once()
    print("\nScan Results:")
    print(f"  Emails processed: {result['emails_processed']}")
    print(f"  Files processed: {result['files_processed']}")
    print(f"  Events created: {result['events_created']}")
    print(f"  Cases created: {result['cases_created']}")
    if result['errors']:
        print(f"  Errors: {len(result['errors'])}")
        for error in result['errors']:
            print(f"    - {error}")

