"""Configuration management for the MVP."""
import os
from dotenv import load_dotenv

load_dotenv()

# Google Drive Configuration
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")

# Google Sheets Configuration
GOOGLE_SHEETS_EVENTS_ID = os.getenv("GOOGLE_SHEETS_EVENTS_ID", "1N-qww4KnhRZNmg0hIFbvT15ahV2TIc9GWuZ4WS82qkk")
GOOGLE_SHEETS_MAINTENANCE_ID = os.getenv("GOOGLE_SHEETS_MAINTENANCE_ID", "1DB9AsEXePFCgTm0swVXDb6RwMN1POtuuy3Tm6RH5OMQ")

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

# Agent Configuration
PROPERTY_MANAGEMENT_AGENT_ID = "property_manager_agent_001"

# Case File Storage (using local JSON files for MVP)
CASE_FILE_DIR = "case_files"

