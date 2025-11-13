"""Utility script to view case files."""
import sys
import os
import json
from case_file import CaseFile
import config

def view_case(event_id: str):
    """View a case file.
    
    Args:
        event_id: The event ID to view
    """
    case_file = CaseFile.load(event_id)
    
    if not case_file:
        print(f"Case file not found for event: {event_id}")
        return
    
    print("\n" + "="*80)
    print(case_file.get_summary())
    print("="*80)
    
    # Print full email content
    if case_file.emails:
        print("\n" + "-"*80)
        print("EMAILS GENERATED:")
        print("-"*80)
        for email in case_file.emails:
            print(f"\nTo: {email['recipient']}")
            print(f"Time: {email['timestamp']}")
            print(f"\n{email['content']}")
            print("\n" + "-"*80)

def list_all_cases():
    """List all case files."""
    if not os.path.exists(config.CASE_FILE_DIR):
        print(f"Case file directory not found: {config.CASE_FILE_DIR}")
        return
    
    case_files = [f for f in os.listdir(config.CASE_FILE_DIR) if f.endswith('.json')]
    
    if not case_files:
        print("No case files found.")
        return
    
    print(f"\nFound {len(case_files)} case file(s):\n")
    for case_file in sorted(case_files):
        event_id = case_file.replace('.json', '')
        print(f"  - {event_id}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        event_id = sys.argv[1]
        view_case(event_id)
    else:
        list_all_cases()
        print("\nUsage: python view_case.py <event_id>")

