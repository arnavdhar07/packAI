"""Flask web application for viewing cases and integrations."""
from flask import Flask, render_template, jsonify
import os
import sys
import json
from datetime import datetime

# Add parent directory to path to import modules
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from case_file import CaseFile
import config

# Fix case file directory path to be relative to project root, not ui/
config.CASE_FILE_DIR = os.path.join(project_root, config.CASE_FILE_DIR)

# Try to import Google Sheets client for events (optional)
try:
    from google_sheets_client import GoogleSheetsClient
    sheets_client_available = True
except Exception:
    sheets_client_available = False

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
                    # Add summary info for list view
                    case_data['summary'] = {
                        'event_type': case_file.event_data.get('event_type', 'unknown'),
                        'entity_id': case_file.event_data.get('entity_id', 'unknown'),
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
                
                event = {
                    'event_id': event_row.get('event_id', ''),
                    'event_type': event_row.get('event_type', ''),
                    'source': event_row.get('source', 'unknown'),
                    'timestamp': event_row.get('timestamp', ''),
                    'details': event_row.get('details', ''),
                    'subscribed_agents': event_row.get('subscribed_agents', '')
                }
                events.append(event)
        except Exception as e:
            print(f"Error reading events from Google Sheets: {e}")
            # Fallback to case files
    
    # Fallback: get events from case files
    if not events:
        all_cases = get_all_cases()
        for case in all_cases:
            event_data = case.get('event_data', {})
            event = {
                'event_id': case.get('event_id', ''),
                'event_type': event_data.get('event_type', ''),
                'source': event_data.get('source', 'unknown'),
                'timestamp': event_data.get('timestamp', case.get('created_at', '')),
                'details': event_data.get('details', event_data.get('description', '')),
                'subscribed_agents': ''
            }
            events.append(event)
    
    # Sort by timestamp, newest first
    events.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return events

def get_event_by_id(event_id):
    """Get a specific event by ID."""
    events = get_all_events()
    event = next((e for e in events if e['event_id'] == event_id), None)
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
    
    integration_status = {
        'google_drive': {
            'name': 'Google Drive',
            'configured': drive_configured,
            'folder_id': drive_folder_id,
            'status': 'Connected' if drive_configured else 'Not configured'
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)

