"""GPT-powered event creator from unstructured data."""
from openai import OpenAI
from datetime import datetime
import uuid
import json
from typing import Dict, Optional
from google_sheets_client import GoogleSheetsClient
import config

class EventCreator:
    """Creates events from unstructured data using GPT."""
    
    def __init__(self, sheets_client: GoogleSheetsClient):
        """Initialize the event creator.
        
        Args:
            sheets_client: Google Sheets client instance
        """
        self.sheets_client = sheets_client
        if not config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in environment variables")
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
    
    def create_event(self, content: str, source: str) -> tuple:
        """Create an event from unstructured content and save to spreadsheet.
        
        Event creator only creates events with: event_id, source, timestamp, subscribed_agents
        The property management agent will fill in event_type and details later.
        
        Args:
            content: The unstructured text content (stored for agent processing)
            source: The source identifier (e.g., file name)
            
        Returns:
            Tuple of (event_id, content) - content is stored for agent to process
        """
        # Generate event ID
        event_id = f"event_{uuid.uuid4().hex[:12]}"
        
        # Get current timestamp
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        # Subscribe the property management agent
        subscribed_agents = config.PROPERTY_MANAGEMENT_AGENT_ID
        
        # Prepare row data for spreadsheet
        # Columns: event_id, event_type, source, timestamp, details, subscribed_agents
        # event_type and details are left empty for agent to fill in
        row_data = [
            event_id,
            "",  # event_type - to be filled by agent
            source,
            timestamp,
            "",  # details - to be filled by agent
            subscribed_agents
        ]
        
        # Append to events spreadsheet
        self.sheets_client.append_row(
            config.GOOGLE_SHEETS_EVENTS_ID,
            row_data
        )
        
        print(f"Created event: {event_id} from source: {source}")
        
        # Return event_id and content for agent to process
        return event_id, content

