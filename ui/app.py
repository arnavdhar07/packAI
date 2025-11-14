"""Flask web application for viewing cases and integrations."""
from flask import Flask, render_template, jsonify, request
import os
import sys
import json
from datetime import datetime

# Add parent directory to path to import modules
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Ensure .env is loaded from project root
from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, '.env'))

from case_file import CaseFile
import config

# Fix case file directory path to be relative to project root, not ui/
config.CASE_FILE_DIR = os.path.join(project_root, config.CASE_FILE_DIR)

# Update sheet IDs to use the new ones
config.GOOGLE_SHEETS_EVENTS_ID = os.getenv("GOOGLE_SHEETS_EVENTS_ID", "1MBKbE6ubsKcrrmP1EqdCK5mu0mAPba-Wm1cV1AnJsO0")
config.GOOGLE_SHEETS_MAINTENANCE_ID = os.getenv("GOOGLE_SHEETS_MAINTENANCE_ID", "13HD2FI-Cl3xNzlTC6pHYCyxY_cA7QwC4Sv548C58AHM")

# Try to import Google Sheets client for events (optional)
try:
    from google_sheets_client import GoogleSheetsClient
    sheets_client_available = True
except Exception:
    sheets_client_available = False

# Try to import scan_once function
try:
    from scan_once import scan_once
    scan_available = True
except Exception as e:
    print(f"Warning: Could not import scan_once: {e}")
    scan_available = False

app = Flask(__name__)

def get_all_cases():
    """Get all case files."""
    cases = []
    case_dir = config.CASE_FILE_DIR
    
    if not os.path.exists(case_dir):
        return cases
    
    for filename in os.listdir(case_dir):
        if filename.endswith('.json'):
            event_id = filename.replace('.json', '')
            try:
                case_file = CaseFile.load(event_id)
                if case_file:
                    case_data = case_file.to_dict()
                    # Add display name based on event type (new format, max 4 words)
                    event_type = case_file.event_data.get('event_type', '')
                    summary = case_file.event_data.get('summary', case_file.event_data.get('description', ''))
                    location = case_file.event_data.get('location', 'unknown')
                    case_data['display_name'] = extract_readable_name(event_type, summary, location, max_words=4)
                    # Add summary info for list view
                    case_data['summary'] = {
                        'event_type': case_file.event_data.get('event_type', 'unknown'),
                        'location': case_file.event_data.get('location', 'unknown'),
                        'urgency': case_file.event_data.get('urgency', 'routine'),
                        'created_at': case_file.created_at,
                        'actions_count': len(case_file.actions),
                        'emails_count': len(case_file.emails)
                    }
                    cases.append(case_data)
            except Exception as e:
                print(f"Error loading case {event_id}: {e}")
    
    # Sort by created_at, newest first
    cases.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return cases

def get_agents():
    """Get all agents with their case counts."""
    all_cases = get_all_cases()
    
    # For MVP, we only have the property management agent
    # All cases belong to this agent
    agents = [{
        'id': config.PROPERTY_MANAGEMENT_AGENT_ID,
        'name': 'Property Management Agent',
        'cases_count': len(all_cases)
    }]
    
    return agents

def get_cases_for_agent(agent_id):
    """Get all cases for a specific agent."""
    all_cases = get_all_cases()
    
    # For MVP, all cases belong to the property management agent
    if agent_id == config.PROPERTY_MANAGEMENT_AGENT_ID:
        return all_cases
    
    return []

def extract_readable_name(event_type: str = "", summary: str = "", location: str = "", max_words: int = 4) -> str:
    """Extract a readable name from event metadata (max 4 words).
    
    Uses new event format: event_type, summary, location.
    
    Args:
        event_type: The event type (e.g., "maintenance_request")
        summary: Optional summary from metadata
        location: Optional location from metadata
        max_words: Maximum number of words (default 4)
        
    Returns:
        A readable name string (max 4 words)
    """
    words = []
    
    # Start with event type (formatted)
    if event_type:
        type_words = event_type.replace('_', ' ').title().split()
        words.extend(type_words[:2])  # Max 2 words from event type
    
    # Add location if available and we have space
    if location and location.lower() != 'unknown' and len(words) < max_words:
        # Clean location: if it's an email, extract just the name part
        clean_location = location
        if '@' in location:
            # Extract name from email (e.g., "connorquintenz@gmail.com" -> "connorquintenz")
            clean_location = location.split('@')[0]
        
        location_words = clean_location.split()[:2]  # Max 2 words from location
        remaining = max_words - len(words)
        words.extend(location_words[:remaining])
    
    # If still have space, add first word from summary
    if summary and len(words) < max_words:
        summary_words = summary.split()[:max_words - len(words)]
        words.extend(summary_words)
    
    # Fallback if no words
    if not words:
        return "Untitled Event"
    
    # Return max 4 words
    return ' '.join(words[:max_words])

def get_all_events():
    """Get all events from Google Sheets or case files."""
    events = []
    
    # Try to get events from Google Sheets first
    if sheets_client_available:
        try:
            sheets_client = GoogleSheetsClient()
            events_data = sheets_client.read_as_dicts(config.GOOGLE_SHEETS_EVENTS_ID)
            
            for event_row in events_data:
                # Skip header row if present
                if 'event_id' not in event_row or not event_row.get('event_id'):
                    continue
                
                # Use new event format only
                event_type = event_row.get('event_type', '')
                summary = event_row.get('summary', '')
                location = event_row.get('location', 'unknown')
                urgency = event_row.get('urgency', 'routine')
                source_type = event_row.get('source_type', 'unknown')
                source_id = event_row.get('source_id', '')
                status = event_row.get('status', 'new')
                
                # Build display name (max 4 words)
                display_name = extract_readable_name(event_type, summary, location, max_words=4)
                
                event = {
                    'event_id': event_row.get('event_id', ''),
                    'event_type': event_type if event_type else 'Pending Analysis',
                    'source_type': source_type,
                    'source_id': source_id,
                    'timestamp': event_row.get('timestamp', ''),
                    'summary': summary,
                    'location': location,
                    'urgency': urgency,
                    'status': status,
                    'subscribed_agents': event_row.get('subscribed_agents', ''),
                    'display_name': display_name
                }
                events.append(event)
        except Exception as e:
            print(f"Error reading events from Google Sheets: {e}")
            # Fallback to case files
    
    # Fallback: get events from case files (using new format)
    if not events:
        all_cases = get_all_cases()
        for case in all_cases:
            event_data = case.get('event_data', {})
            event_type = event_data.get('event_type', '')
            summary = event_data.get('summary', event_data.get('description', ''))
            location = event_data.get('location', 'unknown')
            urgency = event_data.get('urgency', 'routine')
            source_type = event_data.get('source_type', 'unknown')
            source_id = event_data.get('source_id', '')
            
            event = {
                'event_id': case.get('event_id', ''),
                'event_type': event_type if event_type else 'Pending Analysis',
                'source_type': source_type,
                'source_id': source_id,
                'timestamp': event_data.get('timestamp', case.get('created_at', '')),
                'summary': summary,
                'location': location,
                'urgency': urgency,
                'status': case.get('status', 'new'),
                'subscribed_agents': config.PROPERTY_MANAGEMENT_AGENT_ID,
                'display_name': extract_readable_name(event_type, summary, location, max_words=4)
            }
            events.append(event)
    
    # Sort by timestamp, newest first
    events.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return events

def get_event_by_id(event_id):
    """Get a specific event by ID."""
    events = get_all_events()
    event = next((e for e in events if e['event_id'] == event_id), None)
    if event and 'display_name' not in event:
        # Ensure display_name is set using new format
        event['display_name'] = extract_readable_name(
            event.get('event_type', ''),
            event.get('summary', ''),
            event.get('location', ''),
            max_words=4
        )
    return event

@app.route('/')
def index():
    """Redirect to agents page."""
    return render_template('agents.html', agents=get_agents())

@app.route('/agents')
def agents():
    """Agents page."""
    return render_template('agents.html', agents=get_agents())

@app.route('/agents/<agent_id>')
def agent_detail(agent_id):
    """Agent detail page showing cases for that agent."""
    agents_list = get_agents()
    agent = next((a for a in agents_list if a['id'] == agent_id), None)
    
    if not agent:
        return f"Agent not found: {agent_id}", 404
    
    cases = get_cases_for_agent(agent_id)
    # Ensure each case has status
    for case in cases:
        if 'status' not in case:
            case['status'] = 'open'
    return render_template('agent_detail.html', agent=agent, cases=cases)

@app.route('/cases/<event_id>')
def case_detail(event_id):
    """Case detail page."""
    case_file = CaseFile.load(event_id)
    if not case_file:
        return f"Case not found: {event_id}", 404
    
    # Get agent info for back link
    agents_list = get_agents()
    agent = agents_list[0] if agents_list else None
    
    case_dict = case_file.to_dict()
    
    # Add display name based on event type (new format, max 4 words)
    event_type = case_file.event_data.get('event_type', '')
    summary = case_file.event_data.get('summary', case_file.event_data.get('description', ''))
    location = case_file.event_data.get('location', 'unknown')
    case_dict['display_name'] = extract_readable_name(event_type, summary, location, max_words=4)
    
    # Ensure status exists, default to 'open'
    if 'status' not in case_dict:
        case_dict['status'] = 'open'
    
    return render_template('case_detail.html', case=case_dict, agent=agent)

@app.route('/api/cases/<event_id>/approve-email', methods=['POST'])
def approve_email(event_id):
    """API endpoint to approve/send an email."""
    from flask import request
    case_file = CaseFile.load(event_id)
    if not case_file:
        return jsonify({'error': 'Case not found'}), 404
    
    data = request.get_json()
    email_index = data.get('email_index')
    
    if email_index is None or email_index >= len(case_file.emails):
        return jsonify({'error': 'Invalid email index'}), 400
    
    # Mark email as sent
    case_file.emails[email_index]['sent'] = True
    case_file.save()
    
    return jsonify({'success': True, 'email_index': email_index})

@app.route('/events')
def events():
    """Events page."""
    return render_template('events.html', events=get_all_events())

@app.route('/events/<event_id>')
def event_detail(event_id):
    """Event detail page."""
    event = get_event_by_id(event_id)
    if not event:
        return f"Event not found: {event_id}", 404
    
    return render_template('event_detail.html', event=event)

@app.route('/integrations')
def integrations():
    """Integrations page."""
    # Check if Google Drive is configured
    drive_configured = bool(config.GOOGLE_DRIVE_FOLDER_ID)
    drive_folder_id = config.GOOGLE_DRIVE_FOLDER_ID or "Not configured"
    
    # Check if Gmail is configured
    gmail_configured = config.GMAIL_ENABLED
    gmail_email = config.GMAIL_EMAIL_ADDRESS or "Not specified"
    
    integration_status = {
        'google_drive': {
            'name': 'Google Drive',
            'configured': drive_configured,
            'folder_id': drive_folder_id,
            'status': 'Connected' if drive_configured else 'Not configured'
        },
        'gmail': {
            'name': 'Gmail',
            'configured': gmail_configured,
            'email_address': gmail_email,
            'status': 'Connected' if gmail_configured else 'Not configured'
        }
    }
    
    return render_template('integrations.html', integrations=integration_status)

@app.route('/api/cases')
def api_cases():
    """API endpoint for cases."""
    return jsonify(get_all_cases())

@app.route('/api/cases/<event_id>')
def api_case_detail(event_id):
    """API endpoint for case detail."""
    case_file = CaseFile.load(event_id)
    if not case_file:
        return jsonify({'error': 'Case not found'}), 404
    return jsonify(case_file.to_dict())

@app.route('/api/scan', methods=['POST'])
def trigger_scan():
    """API endpoint to trigger a manual scan."""
    if not scan_available:
        return jsonify({
            'success': False,
            'error': 'Scan functionality not available. Check server logs.'
        }), 500
    
    try:
        # Run scan with timeout protection
        import signal
        
        result = scan_once()
        
        # Ensure result has proper structure
        if not isinstance(result, dict):
            return jsonify({
                'success': False,
                'error': 'Invalid scan result format'
            }), 500
        
        # Result should already have errors filtered by scan_once, but double-check
        # Filter out non-critical errors (like email marking errors, API not enabled)
        if result.get('errors'):
            critical_errors = []
            for e in result['errors']:
                error_str = str(e).lower()
                if 'insufficient authentication scopes' in error_str:
                    continue
                if 'mark email as read' in error_str:
                    continue
                if 'api has not been used' in error_str:
                    continue
                if 'accessnotconfigured' in error_str:
                    continue
                critical_errors.append(e)
            
            if not critical_errors:
                result['success'] = True
                result['errors'] = []
            else:
                result['errors'] = critical_errors
        
        # Log success for debugging
        print(f"Scan completed: success={result.get('success')}, events={result.get('events_created', 0)}, cases={result.get('cases_created', 0)}")
        
        return jsonify(result)
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Scan error: {error_details}")
        # Return a more user-friendly error message
        error_msg = str(e)
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."
        return jsonify({
            'success': False,
            'error': error_msg,
            'errors': [error_msg]
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5001)

