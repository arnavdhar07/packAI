# UI for Property Management MVP

Simple web interface to view cases and integrations.

## Running the UI

1. Make sure you have Flask installed:

   ```bash
   pip install -r ../requirements.txt
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

## Pages

- **Cases** (`/cases`): View all cases in a horizontal file list view
- **Case Detail** (`/cases/<event_id>`): View detailed actions for a specific case
- **Integrations** (`/integrations`): View integration status (Google Drive)

## Features

- Simple, MVP-style interface
- Horizontal file list view (like Google Drive)
- Click on any case to see all actions taken
- View all generated emails
- Check integration status
