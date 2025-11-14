"""Monitor Gmail account for new emails and create events."""
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
import json
import os
import re
from typing import List, Dict, Optional

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

class GmailMonitor:
    """Monitor a Gmail account for new emails."""
    
    def __init__(self, credentials_path: str = "gmail_credentials.json", token_path: str = "gmail_token.json", email_address: str = None):
        """Initialize the Gmail monitor.
        
        Args:
            credentials_path: Path to OAuth 2.0 credentials JSON file (from Google Cloud Console)
            token_path: Path to store/load OAuth token
            email_address: Email address to monitor (optional, will use 'me' if not provided)
        """
        self.email_address = email_address or "me"
        self.token_path = token_path
        creds = None
        
        # Load existing token
        if os.path.exists(token_path):
            with open(token_path, 'r') as token:
                token_data = json.load(token)
                creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        
        # If there are no (valid) credentials available, prompt user to log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(credentials_path):
                    raise FileNotFoundError(
                        f"Gmail credentials file not found at {credentials_path}. "
                        "Please download OAuth 2.0 credentials from Google Cloud Console. "
                        "See README for setup instructions."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('gmail', 'v1', credentials=creds)
        self.processed_message_ids = set()  # Track processed message IDs
    
    def list_messages(self, query: str = "is:unread", max_results: int = 10) -> List[Dict]:
        """List messages from Gmail.
        
        Args:
            query: Gmail search query (default: unread messages)
            max_results: Maximum number of results to return
            
        Returns:
            List of message metadata dictionaries
        """
        try:
            results = self.service.users().messages().list(
                userId=self.email_address,
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            return messages
            
        except HttpError as error:
            print(f"Error accessing Gmail: {error}")
            return []
    
    def get_message(self, message_id: str) -> Optional[Dict]:
        """Get a specific message by ID.
        
        Args:
            message_id: The Gmail message ID
            
        Returns:
            Message dictionary with content, or None if error
        """
        try:
            message = self.service.users().messages().get(
                userId=self.email_address,
                id=message_id,
                format='full'
            ).execute()
            
            return message
            
        except HttpError as error:
            print(f"Error getting message {message_id}: {error}")
            return None
    
    def extract_email_content(self, message: Dict) -> Dict:
        """Extract content from a Gmail message.
        
        Args:
            message: Gmail message dictionary
            
        Returns:
            Dictionary with subject, body, from, to, date
        """
        payload = message.get('payload', {})
        headers = payload.get('headers', [])
        
        # Extract headers
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        from_email = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        to_email = next((h['value'] for h in headers if h['name'] == 'To'), 'Unknown')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')
        
        # Extract body
        body = self._extract_body(payload)
        
        return {
            'subject': subject,
            'from': from_email,
            'to': to_email,
            'date': date,
            'body': body,
            'message_id': message['id'],
            'thread_id': message.get('threadId', '')
        }
    
    def _extract_body(self, payload: Dict) -> str:
        """Extract text body from message payload.
        
        Args:
            payload: Message payload dictionary
            
        Returns:
            Email body as string
        """
        body = ""
        
        # Check if message has parts (multipart)
        if 'parts' in payload:
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')
                if mime_type == 'text/plain':
                    data = part.get('body', {}).get('data', '')
                    if data:
                        body += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                elif mime_type == 'text/html' and not body:
                    # Fallback to HTML if no plain text
                    data = part.get('body', {}).get('data', '')
                    if data:
                        html_body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                        # Simple HTML stripping (for MVP)
                        body = html_body.replace('<br>', '\n').replace('<br/>', '\n')
                        # Remove other HTML tags (basic)
                        body = re.sub(r'<[^>]+>', '', body)
        else:
            # Single part message
            mime_type = payload.get('mimeType', '')
            if mime_type in ['text/plain', 'text/html']:
                data = payload.get('body', {}).get('data', '')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        
        return body.strip()
    
    def get_new_emails(self, query: str = "is:unread", max_age_minutes: Optional[int] = None) -> List[Dict]:
        """Get new emails that haven't been processed yet.
        
        Args:
            query: Gmail search query
            max_age_minutes: Optional. Only return emails from the last N minutes.
                           If None, returns all unread emails.
            
        Returns:
            List of email content dictionaries
        """
        from datetime import datetime, timedelta, timezone
        
        messages = self.list_messages(query)
        new_emails = []
        
        # Calculate cutoff time if max_age_minutes is specified
        cutoff_time = None
        if max_age_minutes:
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
        
        for msg in messages:
            message_id = msg['id']
            
            # Skip if already processed
            if message_id in self.processed_message_ids:
                continue
            
            # Get full message
            message = self.get_message(message_id)
            if message:
                email_content = self.extract_email_content(message)
                
                # Check if email is within time window
                if cutoff_time and email_content:
                    try:
                        # Parse email date
                        email_date_str = email_content.get('date', '')
                        if email_date_str:
                            # Try to parse various date formats
                            from email.utils import parsedate_to_datetime
                            email_date = parsedate_to_datetime(email_date_str)
                            
                            # Convert to UTC if needed
                            if email_date.tzinfo is None:
                                email_date = email_date.replace(tzinfo=timezone.utc)
                            
                            # Convert to UTC datetime for comparison
                            email_date_utc = email_date.astimezone(timezone.utc)
                            
                            # Skip if email is too old
                            if email_date_utc < cutoff_time:
                                continue
                    except Exception as e:
                        # If date parsing fails, include the email (better to include than exclude)
                        print(f"Warning: Could not parse email date, including email: {e}")
                
                new_emails.append(email_content)
        
        return new_emails
    
    def mark_email_processed(self, message_id: str):
        """Mark an email as processed.
        
        Args:
            message_id: The Gmail message ID
        """
        self.processed_message_ids.add(message_id)
    
    def mark_email_read(self, message_id: str):
        """Mark an email as read (remove unread label).
        
        Args:
            message_id: The Gmail message ID
        """
        try:
            self.service.users().messages().modify(
                userId=self.email_address,
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
        except HttpError as error:
            print(f"Error marking email as read: {error}")

