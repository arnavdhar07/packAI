"""Monitor Google Drive folder for new files."""
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import os
from typing import List, Dict, Optional
from datetime import datetime

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

class GoogleDriveMonitor:
    """Monitor a Google Drive folder for new files."""
    
    def __init__(self, credentials_path: str = "credentials.json"):
        """Initialize the Google Drive monitor.
        
        Args:
            credentials_path: Path to Google service account credentials JSON file
        """
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(
                f"Credentials file not found at {credentials_path}. "
                "Please download your service account credentials from Google Cloud Console."
            )
        
        creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
        self.service = build('drive', 'v3', credentials=creds)
        self.processed_files = set()  # Track processed file IDs
    
    def list_files_in_folder(self, folder_id: str) -> List[Dict]:
        """List all files in a Google Drive folder.
        
        Args:
            folder_id: The ID of the Google Drive folder
            
        Returns:
            List of file metadata dictionaries
        """
        query = f"'{folder_id}' in parents and trashed=false"
        results = self.service.files().list(
            q=query,
            fields="files(id, name, mimeType, createdTime, modifiedTime)"
        ).execute()
        
        return results.get('files', [])
    
    def get_new_files(self, folder_id: str) -> List[Dict]:
        """Get files that haven't been processed yet.
        
        Args:
            folder_id: The ID of the Google Drive folder
            
        Returns:
            List of unprocessed file metadata dictionaries
        """
        all_files = self.list_files_in_folder(folder_id)
        new_files = [f for f in all_files if f['id'] not in self.processed_files]
        return new_files
    
    def download_file_content(self, file_id: str) -> Optional[str]:
        """Download and read the content of a file.
        
        Args:
            file_id: The ID of the file to download
            
        Returns:
            File content as string, or None if file type is not supported
        """
        try:
            file_metadata = self.service.files().get(fileId=file_id).execute()
            mime_type = file_metadata.get('mimeType', '')
            
            # Handle text-based files
            if 'text' in mime_type or mime_type in [
                'application/json',
                'application/vnd.google-apps.document'  # Google Docs
            ]:
                if mime_type == 'application/vnd.google-apps.document':
                    # Export Google Docs as plain text
                    request = self.service.files().export_media(
                        fileId=file_id,
                        mimeType='text/plain'
                    )
                else:
                    # Download regular files
                    request = self.service.files().get_media(fileId=file_id)
                
                file_content = io.BytesIO()
                downloader = MediaIoBaseDownload(file_content, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                
                file_content.seek(0)
                return file_content.read().decode('utf-8')
            
            # For other file types, return None (could be extended to handle PDFs, images, etc.)
            return None
            
        except Exception as e:
            print(f"Error downloading file {file_id}: {e}")
            return None
    
    def mark_file_processed(self, file_id: str):
        """Mark a file as processed.
        
        Args:
            file_id: The ID of the file to mark as processed
        """
        self.processed_files.add(file_id)

