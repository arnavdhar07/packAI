"""Event creator from unstructured data using OpenAI."""
from openai import OpenAI
from datetime import datetime
import uuid
import json
from typing import Dict, Optional
from google_sheets_client import GoogleSheetsClient
import config

class EventCreator:
    """Creates events from unstructured data using OpenAI to analyze content."""
    
    def __init__(self, sheets_client: GoogleSheetsClient):
        """Initialize the event creator.
        
        Args:
            sheets_client: Google Sheets client instance
        """
        self.sheets_client = sheets_client
        if not config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in environment variables")
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
    
    def extract_metadata(self, content: str) -> Dict:
        """Extract lightweight metadata from content using OpenAI.
        
        Only extracts essential fields for fast agent decisions - not full summaries.
        
        Args:
            content: The unstructured text content to analyze
            
        Returns:
            Dictionary with extracted metadata (urgency, location, issue_type, summary)
        """
        prompt = f"""Extract ONLY essential metadata from this property management document/email for fast decision-making.

Extract:
1. urgency: "urgent" or "routine" (urgent = needs immediate attention, routine = can wait)
2. location: Unit/apartment number or location (e.g., "Unit 4B", "Building A", "Main Office"). If not mentioned, extract the sender's name or email address (e.g., "John Smith" or "john@example.com") instead of "unknown"
3. issue_type: Type of issue (e.g., "leak", "hvac", "appliance", "electrical", "plumbing", "general", "inquiry", "complaint") or "general" if unclear
4. summary: ONE sentence summary (max 50 words) - just enough to understand the issue

Content:
{content[:2000]}

Return JSON with keys: urgency, location, issue_type, summary.
For location: If no unit/location is mentioned, use the sender's name or email address.
Be concise - agents need this for fast decisions, not full analysis."""

        try:
            response = self.client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a metadata extraction assistant. Extract only essential fields for fast decision-making. Always respond with valid JSON. Be concise."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2  # Lower temperature for more consistent extraction
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Try to parse JSON from response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            metadata = json.loads(response_text)
            
            # Ensure fields exist with defaults
            metadata.setdefault('urgency', 'routine')
            metadata.setdefault('location', 'unknown')
            metadata.setdefault('issue_type', 'general')
            metadata.setdefault('summary', content[:100])  # Fallback to truncated content
            
            # Normalize urgency
            if metadata['urgency'].lower() not in ['urgent', 'routine']:
                metadata['urgency'] = 'routine'
            
            # Always try to extract sender name/email from content as fallback or improvement
            # This ensures we have a meaningful location even if OpenAI doesn't extract it
            if 'From:' in content:
                from_line = [line for line in content.split('\n') if 'From:' in line]
                if from_line:
                    from_text = from_line[0].replace('From:', '').strip()
                    # Extract name if in format "Name <email>"
                    if '<' in from_text and '>' in from_text:
                        name_part = from_text.split('<')[0].strip()
                        if name_part:
                            # Prefer extracted name over OpenAI's response if OpenAI returned email/unknown
                            if metadata.get('location', '').lower() in ['unknown', ''] or '@' in metadata.get('location', ''):
                                metadata['location'] = name_part
                        else:
                            # Use email username if no name
                            email_part = from_text.split('<')[1].split('>')[0].strip()
                            if metadata.get('location', '').lower() in ['unknown', '']:
                                metadata['location'] = email_part.split('@')[0] if '@' in email_part else email_part
                    else:
                        # If it's just an email, extract the name part before @
                        if '@' in from_text:
                            if metadata.get('location', '').lower() in ['unknown', '']:
                                metadata['location'] = from_text.split('@')[0]
                        else:
                            if metadata.get('location', '').lower() in ['unknown', '']:
                                metadata['location'] = from_text
            
            # Final fallback: if location is still unknown or is an email, try to extract name
            if metadata.get('location', '').lower() == 'unknown' or '@' in metadata.get('location', ''):
                if 'From:' in content:
                    from_line = [line for line in content.split('\n') if 'From:' in line]
                    if from_line:
                        from_text = from_line[0].replace('From:', '').strip()
                        if '<' in from_text and '>' in from_text:
                            name_part = from_text.split('<')[0].strip()
                            if name_part:
                                metadata['location'] = name_part
            
            return metadata
            
        except Exception as e:
            print(f"Error extracting metadata with OpenAI: {e}")
            # Try to extract sender from content as fallback
            location = 'unknown'
            if 'From:' in content:
                from_line = [line for line in content.split('\n') if 'From:' in line]
                if from_line:
                    from_text = from_line[0].replace('From:', '').strip()
                    if '<' in from_text:
                        name_part = from_text.split('<')[0].strip()
                        if name_part:
                            location = name_part
                        else:
                            email_part = from_text.split('<')[1].split('>')[0].strip()
                            location = email_part.split('@')[0] if '@' in email_part else email_part
                    else:
                        # If it's just an email, extract the name part
                        if '@' in from_text:
                            location = from_text.split('@')[0]
                        else:
                            location = from_text
            
            # Return default values if extraction fails
            return {
                'urgency': 'routine',
                'location': location,
                'issue_type': 'general',
                'summary': content[:100]
            }
    
    def parse_source(self, source: str) -> Dict:
        """Parse source string into structured source object.
        
        Args:
            source: Source identifier (e.g., "gmail:email@example.com:msg123" or "google_drive:file_id" or filename)
            
        Returns:
            Dictionary with source type, id, and other info
        """
        if source.startswith("gmail:"):
            # Format: gmail:email:message_id
            parts = source.split(":", 2)
            return {
                "type": "gmail",
                "id": parts[2] if len(parts) > 2 else parts[1],
                "email": parts[1] if len(parts) > 1 else "unknown",
                "url": f"https://mail.google.com/mail/u/0/#inbox/{parts[2]}" if len(parts) > 2 else ""
            }
        elif source.startswith("google_drive:") or "drive.google.com" in source:
            # Format: google_drive:file_id or full URL
            if "drive.google.com" in source:
                # Extract file ID from URL
                file_id = source.split("/d/")[1].split("/")[0] if "/d/" in source else source
            else:
                file_id = source.split(":", 1)[1] if ":" in source else source
            return {
                "type": "google_drive",
                "id": file_id,
                "url": f"https://drive.google.com/file/d/{file_id}" if file_id else "",
                "filename": source.split("/")[-1] if "/" in source else source
            }
        else:
            # Assume it's a filename or generic source
            return {
                "type": "unknown",
                "id": source,
                "filename": source,
                "url": ""
            }
    
    def create_event(self, content: str, source: str) -> tuple:
        """Create an event from unstructured content and save to spreadsheet.
        
        Uses OpenAI to extract lightweight metadata (not full summaries).
        Stores source reference, not full content.
        
        Args:
            content: The unstructured text content (used for extraction, not stored)
            source: The source identifier (e.g., "gmail:email:msg123" or filename)
            
        Returns:
            Tuple of (event_id, event_type, metadata_dict) - event is saved with metadata
        """
        # Extract lightweight metadata using OpenAI
        print(f"Extracting metadata from {source}...")
        metadata = self.extract_metadata(content)
        
        # Parse source into structured format
        source_obj = self.parse_source(source)
        
        # Determine event_type from issue_type
        issue_type = metadata.get('issue_type', 'general')
        if issue_type in ['leak', 'hvac', 'appliance', 'electrical', 'plumbing']:
            event_type = 'maintenance_request'
        elif issue_type == 'inquiry':
            event_type = 'inquiry'
        elif issue_type == 'complaint':
            event_type = 'complaint'
        else:
            event_type = 'document_added'  # Generic type
        
        # Generate event ID
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        
        # Get current timestamp
        timestamp = datetime.utcnow().isoformat() + "Z"
        extraction_timestamp = timestamp
        
        # Subscribe the property management agent
        subscribed_agents = config.PROPERTY_MANAGEMENT_AGENT_ID
        
        # Prepare row data for spreadsheet
        # Columns: event_id, timestamp, event_type, source_type, source_id, urgency, location, summary, subscribed_agents, status
        row_data = [
            event_id,
            timestamp,
            event_type,
            source_obj.get('type', 'unknown'),
            source_obj.get('id', source),
            metadata.get('urgency', 'routine'),
            metadata.get('location', 'unknown'),
            metadata.get('summary', ''),
            subscribed_agents,
            'new'  # status
        ]
        
        # Append to events spreadsheet
        self.sheets_client.append_row(
            config.GOOGLE_SHEETS_EVENTS_ID,
            row_data
        )
        
        print(f"Created event: {event_id} (type: {event_type}, urgency: {metadata.get('urgency')}) from {source_obj.get('type')}")
        
        # Return event_id, event_type, and metadata for agent processing
        return event_id, event_type, metadata

