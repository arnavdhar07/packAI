"""Case file management for tracking agent actions."""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import config

class CaseFile:
    """Manages case files that track all agent actions for an event."""
    
    def __init__(self, event_id: str, event_data: Dict):
        """Initialize a case file.
        
        Args:
            event_id: The event ID
            event_data: Initial event data
        """
        self.event_id = event_id
        self.event_data = event_data
        self.actions: List[Dict] = []
        self.emails: List[Dict] = []
        self.created_at = datetime.utcnow().isoformat() + "Z"
        self.status = "open"  # Default status
        
        # Ensure case file directory exists
        os.makedirs(config.CASE_FILE_DIR, exist_ok=True)
    
    def add_action(self, action_type: str, action_data: Dict):
        """Add an action to the case file.
        
        Args:
            action_type: Type of action (e.g., "determined_repair_type")
            action_data: Data associated with the action
        """
        action = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action_type": action_type,
            "data": action_data
        }
        self.actions.append(action)
    
    def add_email(self, recipient: str, content: str):
        """Add an email to the case file.
        
        Args:
            recipient: Email recipient type (property_manager, maintenance_company, tenant)
            content: Email content
        """
        email = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "recipient": recipient,
            "content": content
        }
        self.emails.append(email)
    
    def to_dict(self) -> Dict:
        """Convert case file to dictionary.
        
        Returns:
            Dictionary representation of the case file
        """
        return {
            "event_id": self.event_id,
            "event_data": self.event_data,
            "created_at": self.created_at,
            "status": self.status,
            "actions": self.actions,
            "emails": self.emails
        }
    
    def save(self):
        """Save case file to disk."""
        file_path = os.path.join(config.CASE_FILE_DIR, f"{self.event_id}.json")
        
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        
        print(f"Case file saved: {file_path}")
    
    @staticmethod
    def load(event_id: str) -> Optional['CaseFile']:
        """Load a case file from disk.
        
        Args:
            event_id: The event ID
            
        Returns:
            CaseFile object or None if not found
        """
        file_path = os.path.join(config.CASE_FILE_DIR, f"{event_id}.json")
        
        if not os.path.exists(file_path):
            return None
        
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        case_file = CaseFile(data['event_id'], data['event_data'])
        case_file.actions = data.get('actions', [])
        case_file.emails = data.get('emails', [])
        case_file.created_at = data.get('created_at', datetime.utcnow().isoformat() + "Z")
        case_file.status = data.get('status', 'open')
        
        return case_file
    
    def get_summary(self) -> str:
        """Get a human-readable summary of the case file.
        
        Returns:
            Summary string
        """
        summary = f"Case File: {self.event_id}\n"
        summary += f"Created: {self.created_at}\n"
        summary += f"Event Type: {self.event_data.get('event_type', 'unknown')}\n"
        summary += f"Entity: {self.event_data.get('entity_id', 'unknown')}\n"
        summary += f"\nActions Taken ({len(self.actions)}):\n"
        
        for action in self.actions:
            summary += f"  - {action['timestamp']}: {action['action_type']}\n"
        
        summary += f"\nEmails Generated ({len(self.emails)}):\n"
        
        for email in self.emails:
            summary += f"  - {email['timestamp']}: To {email['recipient']}\n"
            summary += f"    {email['content'][:100]}...\n"
        
        return summary

