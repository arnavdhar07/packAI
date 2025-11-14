"""Configuration management for the MVP."""
import os
from dotenv import load_dotenv

load_dotenv()

# Google Drive Configuration
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")

# Gmail Configuration
GMAIL_EMAIL_ADDRESS = os.getenv("GMAIL_EMAIL_ADDRESS", "")
GMAIL_ENABLED = os.getenv("GMAIL_ENABLED", "false").lower() == "true"

# Google Sheets Configuration
GOOGLE_SHEETS_EVENTS_ID = os.getenv("GOOGLE_SHEETS_EVENTS_ID", "1MBKbE6ubsKcrrmP1EqdCK5mu0mAPba-Wm1cV1AnJsO0")
GOOGLE_SHEETS_MAINTENANCE_ID = os.getenv("GOOGLE_SHEETS_MAINTENANCE_ID", "13HD2FI-Cl3xNzlTC6pHYCyxY_cA7QwC4Sv548C58AHM")

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

# Agent Configuration
PROPERTY_MANAGEMENT_AGENT_ID = "property_manager_agent_001"

# Case File Storage (using local JSON files for MVP)
CASE_FILE_DIR = "case_files"

