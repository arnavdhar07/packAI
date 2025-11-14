"""Property Management Agent that processes events."""
from openai import OpenAI
from typing import Dict, List, Optional
from google_sheets_client import GoogleSheetsClient
from case_file import CaseFile
import config
import json
import re

class PropertyManagementAgent:
    """Agent that processes maintenance events and coordinates responses."""
    
    def __init__(self, sheets_client: GoogleSheetsClient):
        """Initialize the property management agent.
        
        Args:
            sheets_client: Google Sheets client instance
        """
        self.sheets_client = sheets_client
        self.agent_id = config.PROPERTY_MANAGEMENT_AGENT_ID
        if not config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in environment variables")
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
    
    def get_maintenance_companies(self) -> List[Dict]:
        """Get list of approved maintenance companies from spreadsheet.
        
        Returns:
            List of maintenance company dictionaries
        """
        try:
            companies = self.sheets_client.read_as_dicts(config.GOOGLE_SHEETS_MAINTENANCE_ID)
            return companies
        except Exception as e:
            print(f"Error reading maintenance companies: {e}")
            return []
    
    def is_maintenance_related(self, event_type: str) -> bool:
        """Check if an event type is maintenance-related.
        
        Args:
            event_type: The event type to check
            
        Returns:
            True if the event is maintenance-related, False otherwise
        """
        maintenance_types = [
            'maintenance_request',
            'repair_request',
            'emergency_repair',
            'routine_maintenance',
            'maintenance_issue',
            'repair_needed',
            'maintenance',
            'repair'
        ]
        return event_type.lower() in [mt.lower() for mt in maintenance_types]
    
    # Note: analyze_event_content method removed - event creator now handles analysis
    # This agent only processes events that have already been analyzed
    
    def determine_repair_type_from_summary(self, summary: str, location: str) -> str:
        """Determine repair type from metadata summary (fast path).
        
        Args:
            summary: One-sentence summary from metadata
            location: Location information
            
        Returns:
            Repair type string
        """
        prompt = f"""Based on this maintenance request summary, determine the repair type.

Summary: {summary}
Location: {location}

Return ONLY the repair type (e.g., "plumbing", "hvac", "electrical", "appliance", "general").
Be concise - one word."""

        try:
            response = self.client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a property management assistant. Return only the repair type, one word."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )
            
            repair_type = response.choices[0].message.content.strip().lower()
            # Clean up response
            repair_type = repair_type.replace('"', '').replace('.', '').strip()
            return repair_type
            
        except Exception as e:
            print(f"Error determining repair type: {e}")
            return "general"
    
    def determine_repair_type(self, event_data: Dict) -> str:
        """Determine the repair type from event data.
        
        Args:
            event_data: Event data dictionary
            
        Returns:
            Repair type string
        """
        # If repair_type is already in event_data, use it
        if 'repair_type' in event_data and event_data['repair_type'] != 'unknown':
            return event_data['repair_type']
        
        # Otherwise, use GPT to determine from description or details
        description = event_data.get('description', event_data.get('details', ''))
        
        prompt = f"""Based on the following maintenance request description, determine the repair type.

Description: {description}

Choose the most appropriate repair type from: plumbing, electrical, hvac, appliance, structural, painting, flooring, other.

Respond with only the repair type (single word)."""

        try:
            response = self.client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that categorizes maintenance requests. Respond with only the repair type."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            repair_type = response.choices[0].message.content.strip().lower()
            return repair_type
        except Exception as e:
            print(f"Error determining repair type: {e}")
            return "other"
    
    def select_maintenance_company(self, repair_type: str, event_data: Dict) -> Optional[Dict]:
        """Select the best maintenance company for the repair type.
        
        Args:
            repair_type: The type of repair needed
            event_data: Event data dictionary
            
        Returns:
            Selected maintenance company dictionary, or None if none found
        """
        companies = self.get_maintenance_companies()
        
        if not companies:
            return None
        
        # Filter companies by repair type
        # Assuming the spreadsheet has columns that indicate what types of repairs each company handles
        # We'll use GPT to help select the best company if the spreadsheet structure is complex
        
        # Simple matching: look for companies that handle this repair type
        # This assumes the spreadsheet has columns like "specialties", "repair_types", or similar
        matching_companies = []
        
        for company in companies:
            # Check if company handles this repair type
            # We'll look for common column names
            specialties = str(company.get('specialties', '') or company.get('repair_types', '') or company.get('services', '')).lower()
            company_name = company.get('name', '') or company.get('company_name', '')
            
            if repair_type.lower() in specialties or not specialties:
                matching_companies.append(company)
        
        if not matching_companies:
            # If no matches, use GPT to select from all companies
            return self._gpt_select_company(companies, repair_type, event_data)
        
        # If multiple matches, use GPT to select the best one
        if len(matching_companies) > 1:
            return self._gpt_select_company(matching_companies, repair_type, event_data)
        
        return matching_companies[0]
    
    def _gpt_select_company(self, companies: List[Dict], repair_type: str, event_data: Dict) -> Optional[Dict]:
        """Use GPT to select the best maintenance company.
        
        Args:
            companies: List of candidate companies
            repair_type: Type of repair needed
            event_data: Event data dictionary
            
        Returns:
            Selected company dictionary
        """
        companies_str = json.dumps(companies, indent=2)
        description = event_data.get('description', '')
        
        prompt = f"""Select the best maintenance company for this repair request.

Repair Type: {repair_type}
Description: {description}

Available Companies:
{companies_str}

Select the most appropriate company based on the repair type and description. 
Respond with only the company name (exactly as it appears in the list)."""

        try:
            response = self.client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that selects maintenance companies. Respond with only the company name."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            selected_name = response.choices[0].message.content.strip()
            
            # Find the company by name
            for company in companies:
                company_name = company.get('name', '') or company.get('company_name', '')
                if selected_name.lower() in company_name.lower() or company_name.lower() in selected_name.lower():
                    return company
            
            # If exact match not found, return first company
            return companies[0] if companies else None
            
        except Exception as e:
            print(f"Error selecting company with GPT: {e}")
            return companies[0] if companies else None
    
    def generate_email(self, recipient_type: str, event_data: Dict, company: Optional[Dict] = None) -> str:
        """Generate an email using GPT.
        
        Args:
            recipient_type: "property_manager", "maintenance_company", or "tenant"
            event_data: Event data dictionary
            company: Selected maintenance company (if applicable)
            
        Returns:
            Generated email content
        """
        event_type = event_data.get('event_type', 'maintenance_request')
        entity_id = event_data.get('entity_id', 'Unknown')
        description = event_data.get('description', '')
        repair_type = event_data.get('repair_type', 'unknown')
        urgency = event_data.get('urgency', 'normal')
        
        if recipient_type == "property_manager":
            prompt = f"""Write a professional email to a property manager summarizing a maintenance request.

Event Type: {event_type}
Property/Unit: {entity_id}
Repair Type: {repair_type}
Urgency: {urgency}
Description: {description}

Write a concise summary email that the property manager can quickly review."""

        elif recipient_type == "maintenance_company":
            company_name = company.get('name', 'Maintenance Company') if company else 'Maintenance Company'
            prompt = f"""Write a professional email to a maintenance company requesting availability for a repair.

Company: {company_name}
Property/Unit: {entity_id}
Repair Type: {repair_type}
Urgency: {urgency}
Description: {description}

Request that they provide available times to come inspect the issue and provide a consultation."""

        elif recipient_type == "tenant":
            prompt = f"""Write a professional email to a tenant notifying them about an upcoming maintenance visit.

Property/Unit: {entity_id}
Repair Type: {repair_type}
Description: {description}

Inform them that a maintenance company will be contacting them shortly to schedule a time to visit and assess the issue."""

        else:
            return ""
        
        try:
            response = self.client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a professional property management assistant. Write clear, professional emails."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error generating email: {e}")
            return f"Error generating email: {e}"
    
    def check_and_process_subscribed_events(self) -> List[CaseFile]:
        """Check for events this agent is subscribed to and process them.
        
        Fast path: Uses metadata from spreadsheet for quick decisions (no API calls).
        Only processes maintenance-related events with status='new'.
        
        Returns:
            List of CaseFile objects created
        """
        case_files = []
        
        try:
            # Get all events from spreadsheet
            events = self.sheets_client.read_as_dicts(config.GOOGLE_SHEETS_EVENTS_ID)
            
            for event_row in events:
                event_id = event_row.get('event_id', '')
                if not event_id:
                    continue
                
                # Check if already processed (case file exists)
                existing_case = CaseFile.load(event_id)
                if existing_case:
                    continue  # Already processed
                
                # Check status - only process 'new' events
                status = event_row.get('status', 'new')
                if status != 'new':
                    continue
                
                # Check if this agent is subscribed
                subscribed_agents = event_row.get('subscribed_agents', '')
                if self.agent_id not in subscribed_agents:
                    continue  # Not subscribed to this event
                
                # Fast path: Read metadata directly from spreadsheet (no API calls)
                event_type = event_row.get('event_type', '')
                urgency = event_row.get('urgency', 'routine')
                location = event_row.get('location', 'unknown')
                summary = event_row.get('summary', '')
                source_type = event_row.get('source_type', 'unknown')
                source_id = event_row.get('source_id', '')
                
                # Check if this is a maintenance-related event
                if not self.is_maintenance_related(event_type):
                    print(f"Event {event_id} is not maintenance-related (type: {event_type}). Skipping.")
                    continue
                
                # Process the event using metadata (fast path)
                print(f"Processing subscribed event: {event_id} (type: {event_type}, urgency: {urgency}, location: {location})")
                case_file = self.process_event_fast(event_id, event_type, urgency, location, summary, source_type, source_id)
                
                if case_file:
                    case_files.append(case_file)
                    # Update event status to 'processing' or 'processed'
                    self._update_event_status(event_id, 'processing')
                    print(f"Created case for event {event_id}")
        
        except Exception as e:
            print(f"Error checking subscribed events: {e}")
            import traceback
            traceback.print_exc()
        
        return case_files
    
    def _update_event_status(self, event_id: str, status: str):
        """Update event status in spreadsheet.
        
        Args:
            event_id: The event ID
            status: New status ('new', 'processing', 'processed', 'closed')
        """
        try:
            # Find the row and update status column (last column, column 10)
            sheet = self.sheets_client.get_sheet(config.GOOGLE_SHEETS_EVENTS_ID)
            all_values = sheet.get_all_values()
            
            for i, row in enumerate(all_values, start=1):
                if row and len(row) > 0 and row[0] == event_id:
                    # Status is in column 10 (index 9, 1-indexed)
                    # Columns: event_id, timestamp, event_type, source_type, source_id, urgency, location, summary, subscribed_agents, status
                    try:
                        sheet.update_cell(i, 10, status)
                        return
                    except Exception as e:
                        # If column doesn't exist yet, try to append it or skip
                        print(f"Warning: Could not update status column: {e}")
                        return
        except Exception as e:
            print(f"Warning: Could not update event status: {e}")
    
    def process_event_fast(self, event_id: str, event_type: str, urgency: str, location: str, summary: str, source_type: str, source_id: str) -> Optional[CaseFile]:
        """Process an event using lightweight metadata (fast path - no API calls).
        
        Uses metadata from spreadsheet for quick decisions. Only fetches full source
        if needed for complex cases.
        
        Args:
            event_id: The event ID
            event_type: The event type
            urgency: Urgency level (urgent/routine)
            location: Location (unit number, etc.)
            summary: One-sentence summary
            source_type: Type of source (gmail, google_drive, etc.)
            source_id: Source identifier
            
        Returns:
            CaseFile object with all actions recorded, or None if not maintenance-related
        """
        # Fast decision: Check urgency for immediate alerts
        if urgency == 'urgent':
            print(f"URGENT event detected: {event_id} at {location}")
            # Could send immediate alert here
        
        # Create event_data dict for case file
        event_data = {
            'event_id': event_id,
            'event_type': event_type,
            'urgency': urgency,
            'location': location,
            'summary': summary,
            'source_type': source_type,
            'source_id': source_id,
            'description': summary,  # Use summary as description
        }
        
        case_file = CaseFile(event_id, event_data)
        case_file.add_action("detected_subscription", {
            "event_type": event_type,
            "urgency": urgency,
            "location": location,
            "summary": summary,
            "is_maintenance": True
        })
        
        # Step 1: Determine repair type (fast path - use summary from metadata)
        if summary and len(summary) > 20:
            # Use metadata summary for repair type determination (fast path)
            repair_type = self.determine_repair_type_from_summary(summary, location)
        else:
            # Fallback: Use full event_data
            repair_type = self.determine_repair_type(event_data)
        
        event_data['repair_type'] = repair_type
        case_file.add_action("determined_repair_type", {"repair_type": repair_type})
        
        # Step 2: Get maintenance companies and select one
        company = self.select_maintenance_company(repair_type, event_data)
        if company:
            case_file.add_action("selected_maintenance_company", {"company": company})
        else:
            case_file.add_action("selected_maintenance_company", {"company": None, "error": "No company found"})
        
        # Step 3: Generate emails
        # Email to property manager
        pm_email = self.generate_email("property_manager", event_data, company)
        case_file.add_email("property_manager", pm_email)
        
        # Email to maintenance company
        if company:
            mc_email = self.generate_email("maintenance_company", event_data, company)
            case_file.add_email("maintenance_company", mc_email)
        else:
            mc_email = "No maintenance company selected."
            case_file.add_email("maintenance_company", mc_email)
        
        # Email to tenant
        tenant_email = self.generate_email("tenant", event_data, company)
        case_file.add_email("tenant", tenant_email)
        
        # Save case file
        case_file.save()
        
        print(f"Processed event {event_id} - Case file created")
        return case_file

