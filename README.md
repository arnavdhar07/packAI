# Property Management MVP - Unified Knowledge Network

This MVP demonstrates a base system for creating a unified knowledge network that AI agents can operate on. It processes unstructured data from Google Drive, creates events, and uses a property management agent to handle maintenance requests.

## Features

- **Google Drive Integration**: Monitors a Google Drive folder for new files
- **Gmail Integration**: Monitors Gmail account for incoming emails and creates events
- **GPT-Powered Event Creation**: Automatically creates structured events from unstructured data
- **Event Storage**: Stores events in Google Spreadsheets
- **Property Management Agent**: Processes maintenance requests, analyzes events, selects maintenance companies, and generates emails
- **Case File System**: Tracks all agent actions and generated emails

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the following APIs:
   - Google Drive API
   - Google Sheets API
   - Gmail API (if using Gmail integration)
4. Create a Service Account:
   - Go to "IAM & Admin" > "Service Accounts"
   - Click "Create Service Account"
   - Give it a name (e.g., "property-management-mvp")
   - Grant it the following roles:
     - "Editor" (or more specific permissions for Drive and Sheets)
   - Click "Done"
5. Create and download credentials:
   - Click on the service account you just created
   - Go to "Keys" tab
   - Click "Add Key" > "Create new key"
   - Choose "JSON" format
   - Download the file and save it as `credentials.json` in the project root

### 3. Share Google Resources

1. **Google Drive Folder**:

   - Open your Google Drive folder
   - Click "Share"
   - Add the service account email (found in credentials.json as `client_email`)
   - Give it "Viewer" or "Editor" access

2. **Events Spreadsheet**:

   - Open the spreadsheet: https://docs.google.com/spreadsheets/d/1N-qww4KnhRZNmg0hIFbvT15ahV2TIc9GWuZ4WS82qkk
   - Click "Share"
   - Add the service account email
   - Give it "Editor" access

3. **Maintenance Companies Spreadsheet**:
   - Open the spreadsheet: https://docs.google.com/spreadsheets/d/1DB9AsEXePFCgTm0swVXDb6RwMN1POtuuy3Tm6RH5OMQ
   - Click "Share"
   - Add the service account email
   - Give it "Viewer" access (or "Editor" if you want the agent to modify it)

### 4. Get Google Drive Folder ID

1. Open your Google Drive folder in a web browser
2. The URL will look like: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`
3. Copy the `FOLDER_ID_HERE` part

### 4. Gmail Setup (Optional)

If you want to monitor Gmail for incoming emails:

1. In Google Cloud Console, enable Gmail API
2. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Desktop app" as application type
   - Download the credentials JSON file
   - Save it as `gmail_credentials.json` in the project root
3. On first run, the application will open a browser for you to authorize Gmail access
4. The token will be saved for future use

### 5. Configure Environment Variables

1. Create a `.env` file in the project root:

   ```bash
   touch .env
   ```

2. Add the following to your `.env` file:

   ```env
   # Google API Configuration
   GOOGLE_DRIVE_FOLDER_ID=your_drive_folder_id_here
   GOOGLE_SHEETS_EVENTS_ID=1MBKbE6ubsKcrrmP1EqdCK5mu0mAPba-Wm1cV1AnJsO0
   GOOGLE_SHEETS_MAINTENANCE_ID=13HD2FI-Cl3xNzlTC6pHYCyxY_cA7QwC4Sv548C58AHM

   # Gmail Configuration (Optional)
   GMAIL_ENABLED=true
   GMAIL_EMAIL_ADDRESS=your-email@gmail.com

   # OpenAI Configuration
   OPENAI_API_KEY=your_openai_api_key_here
   # Use 'gpt-3.5-turbo' for cheaper option or 'gpt-4' for better quality
   OPENAI_MODEL=gpt-3.5-turbo
   ```

3. Fill in the values:
   - `GOOGLE_DRIVE_FOLDER_ID`: Your Google Drive folder ID (from step 4)
   - `GMAIL_ENABLED`: Set to `true` to enable Gmail monitoring
   - `GMAIL_EMAIL_ADDRESS`: The Gmail address to monitor
   - `OPENAI_API_KEY`: Your OpenAI API key (get from https://platform.openai.com/api-keys)
   - `OPENAI_MODEL`: Model to use (default: `gpt-3.5-turbo` for cost efficiency)

The spreadsheet IDs are already configured above, but you can override them if needed.

## Usage

### Running the Main Application

Run the main application:

```bash
python3 main.py
```

### Running the Web UI

To view cases and integrations in a web interface:

1. Navigate to the UI directory:

   ```bash
   cd ui
   ```

2. Run the Flask app:

   ```bash
   python3 app.py
   ```

   **Note:** On macOS, use `python3` instead of `python`.

3. Open your browser to:
   ```
   http://localhost:5000
   ```

The UI provides:

- **Cases Page**: View all cases in a horizontal file list (like Google Drive)
- **Case Detail**: Click any case to see all actions taken by the agent
- **Integrations Page**: View Google Drive integration status

See `ui/README.md` for more details.

The application will:

1. Monitor Google Drive folder and/or Gmail account for new data
2. When new data is detected (file or email), extract its content
3. Create a basic event (event_id, source, timestamp, subscribed_agents) - event_type and details are empty
4. Save the event to the events spreadsheet
5. Property management agent processes the event:
   - Analyzes content to determine event_type and details
   - Updates event in spreadsheet with event_type and details
   - Determines repair type (if maintenance issue)
   - Selects appropriate maintenance company
   - Generates emails (to property manager, maintenance company, and tenant)
6. Save all actions to a case file

### Case Files

Case files are saved in the `case_files/` directory as JSON files. Each case file contains:

- Event data
- All actions taken by the agent
- All emails generated (not sent, just stored)

You can view case files to see what the agent has done for each event.

### Utility Scripts

**View Case Files:**

```bash
# List all case files
python view_case.py

# View a specific case file
python view_case.py event_abc123
```

**Process Existing Events:**
If you have events in the spreadsheet that haven't been processed yet, you can process them:

```bash
python process_existing_events.py
```

## Spreadsheet Structure

### Events Spreadsheet

**Important:** Make sure the first row contains these exact column headers:

- `event_id`: Unique identifier for the event
- `timestamp`: When the event was created (ISO format)
- `event_type`: Type of event (e.g., "maintenance_request")
- `source`: Source of the event (e.g., file name)
- `entity_id`: Property/unit identifier
- `subscribed_agents`: Comma-separated list of agent IDs subscribed to this event

The application will automatically append new events to this spreadsheet.

### Maintenance Companies Spreadsheet

**Important:** Make sure the first row contains column headers. The agent looks for:

- `name` or `company_name`: Company name (required)
- `specialties`, `repair_types`, or `services`: Types of repairs they handle (helps with matching)
- `email`: Contact email (optional)
- Other relevant information

The agent will use this spreadsheet to select appropriate maintenance companies based on repair type. If the spreadsheet structure is complex, the agent will use GPT to intelligently select the best company.

## Architecture

**Core Application:**

- `main.py`: Main application orchestrator
- `google_drive_monitor.py`: Monitors Google Drive folder for new files
- `google_sheets_client.py`: Client for reading/writing to Google Sheets
- `event_creator.py`: GPT-powered event creation from unstructured data
- `property_agent.py`: Property management agent that processes events
- `case_file.py`: Case file management for tracking agent actions
- `config.py`: Configuration management

**Web UI** (`ui/` folder):

- `app.py`: Flask web application
- `templates/`: HTML templates for cases and integrations pages

## Notes

- Emails are **not actually sent** - they are stored in case files for the property manager to review
- The application polls the Google Drive folder every 30 seconds
- Files are marked as processed after being handled to avoid duplicate processing
- The agent automatically subscribes to all events it creates

## Troubleshooting

1. **"Credentials file not found"**: Make sure `credentials.json` is in the project root
2. **"Permission denied"**: Ensure the service account has access to the Drive folder and Spreadsheets
3. **"OPENAI_API_KEY not set"**: Check your `.env` file
4. **No files detected**: Verify the `GOOGLE_DRIVE_FOLDER_ID` is correct and the service account has access

## Future Enhancements

- Real email integration
- More sophisticated event extraction
- Multiple agent types
- Event knowledge graph visualization
- Webhook-based file monitoring instead of polling
- Support for more file types (PDFs, images, etc.)
