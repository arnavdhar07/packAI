"""Property Management Agent that processes events."""
from openai import OpenAI
from typing import Dict, List, Optional
from google_sheets_client import GoogleSheetsClient
from case_file import CaseFile
import config
import json

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
    
    def analyze_event_content(self, content: str) -> Dict:
        """Analyze source content to determine event_type and details.
        
        Args:
            content: The source content to analyze
            
        Returns:
            Dictionary with event_type and details
        """
        prompt = f"""Analyze the following property management document and determine:
1. Event type (e.g., "maintenance_request", "repair_request", "emergency_repair", "routine_maintenance", "inquiry", "complaint")
2. A concise summary/details of the event (2-3 sentences)

Content:
{content}

Return your response as a JSON object with these keys: event_type, details.
The details should be a brief summary of what the event is about."""

        try:
            response = self.client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that analyzes property management documents. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Try to parse JSON from response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            analysis = json.loads(response_text)
            
            # Ensure fields exist
            analysis.setdefault('event_type', 'maintenance_request')
            analysis.setdefault('details', content[:500])  # Fallback to truncated content
            
            return analysis
            
        except Exception as e:
            print(f"Error analyzing event content: {e}")
            # Return default values if analysis fails
            return {
                'event_type': 'maintenance_request',
                'details': content[:500]
            }
    
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
    
    def process_event(self, event_id: str, content: str, source: str) -> CaseFile:
        """Process an event and create case file with all actions.
        
        First, the agent analyzes the content to determine event_type and details,
        then updates the event in Google Sheets, then processes it.
        
        Args:
            event_id: The event ID
            content: The source content to analyze
            source: The source identifier
            
        Returns:
            CaseFile object with all actions recorded
        """
        # Step 0: Analyze content to determine event_type and details
        print(f"Analyzing content for event {event_id}...")
        analysis = self.analyze_event_content(content)
        event_type = analysis.get('event_type', 'maintenance_request')
        details = analysis.get('details', content[:500])
        
        # Update the event in Google Sheets with event_type and details
        try:
            self.sheets_client.update_event(
                config.GOOGLE_SHEETS_EVENTS_ID,
                event_id,
                event_type,
                details
            )
            print(f"Updated event {event_id} with event_type: {event_type}")
        except Exception as e:
            print(f"Error updating event in spreadsheet: {e}")
        
        # Create event_data dict for case file (includes all info for processing)
        event_data = {
            'event_id': event_id,
            'event_type': event_type,
            'source': source,
            'details': details,
            'description': content,  # Keep full content for agent processing
        }
        
        case_file = CaseFile(event_id, event_data)
        case_file.add_action("analyzed_event", {
            "event_type": event_type,
            "details": details
        })
        
        # Step 1: Determine repair type
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

