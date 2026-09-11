"""
FamilySearch API integration for genealogical records.
Extracts names from FamilySearch indexes of Portuguese records.
"""
import requests
import json
import os
import time
from datetime import datetime

import config

# FamilySearch API credentials (replace with your own)
FAMILYSEARCH_API_KEY = os.getenv("FAMILYSEARCH_API_KEY", "")
FAMILYSEARCH_USERNAME = os.getenv("FAMILYSEARCH_USERNAME", "")
FAMILYSEARCH_PASSWORD = os.getenv("FAMILYSEARCH_PASSWORD", "")

# API endpoints
FAMILYSEARCH_BASE_URL = "https://api.familysearch.org"
AUTH_URL = f"{FAMILYSEARCH_BASE_URL}/platform/users/login"
SEARCH_URL = f"{FAMILYSEARCH_BASE_URL}/platform/tree/search"

class FamilySearchAPI:
    def __init__(self):
        self.session = requests.Session()
        self.access_token = None
        self.user_id = None
        
    def authenticate(self):
        """Authenticate with FamilySearch API."""
        if not FAMILYSEARCH_API_KEY or not FAMILYSEARCH_USERNAME or not FAMILYSEARCH_PASSWORD:
            print("FamilySearch credentials not set. Skipping authentication.")
            return False
            
        print("Authenticating with FamilySearch...")
        
        data = {
            "clientId": FAMILYSEARCH_API_KEY,
            "username": FAMILYSEARCH_USERNAME,
            "password": FAMILYSEARCH_PASSWORD,
        }
        
        try:
            resp = self.session.post(AUTH_URL, json=data)
            if resp.status_code == 200:
                result = resp.json()
                self.access_token = result["access_token"]
                self.user_id = result["user_id"]
                self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})
                print("  Authentication successful")
                return True
            else:
                print(f"  Authentication failed: {resp.status_code}")
                return False
        except Exception as e:
            print(f"  Error during authentication: {e}")
            return False
    
    def search_records(self, query_params):
        """Search for records in FamilySearch."""
        if not self.access_token:
            print("Not authenticated. Skipping search.")
            return []
        
        print(f"Searching FamilySearch with query: {query_params}")
        
        try:
            resp = self.session.get(SEARCH_URL, params=query_params)
            if resp.status_code == 200:
                result = resp.json()
                print(f"  Found {result.get('totalHits', 0)} records")
                return result.get("entries", [])
            else:
                print(f"  Search failed: {resp.status_code}")
                return []
        except Exception as e:
            print(f"  Error during search: {e}")
            return []
    
    def extract_names_from_records(self, records):
        """Extract names from search results."""
        names = []
        
        for record in records:
            entry = record.get("content", {})
            
            # Extract name components
            name = {}
            
            # Given name
            given = entry.get("givenName", "")
            if given:
                name["givenName"] = given
            
            # Surname
            surname = entry.get("surname", "")
            if surname:
                name["surname"] = surname
            
            # Full name
            full_name = entry.get("fullName", "")
            if full_name:
                name["fullName"] = full_name
            
            # Birth and death info
            birth = entry.get("birthDate", "")
            death = entry.get("deathDate", "")
            
            if birth:
                name["birthDate"] = birth
            if death:
                name["deathDate"] = death
            
            # Place
            place = entry.get("place", "")
            if place:
                name["place"] = place
            
            # Record ID
            record_id = entry.get("id", "")
            if record_id:
                name["recordId"] = record_id
            
            # Source
            source = entry.get("source", "")
            if source:
                name["source"] = source
            
            if name:
                names.append(name)
        
        return names
    
    def search_portuguese_death_records(self, name, location=None, start_year=None, end_year=None):
        """Search for Portuguese death records."""
        query_params = {
            "q": f"death {name}",
            "collection": "death-records",
            "country": "Portugal",
            "type": "death",
            "limit": 50,
        }
        
        if location:
            query_params["location"] = location
        
        if start_year:
            query_params["startYear"] = start_year
        
        if end_year:
            query_params["endYear"] = end_year
        
        records = self.search_records(query_params)
        return self.extract_names_from_records(records)
    
    def search_portuguese_records_by_location(self, location, record_type="death", start_year=None, end_year=None):
        """Search for records by location."""
        query_params = {
            "q": location,
            "collection": f"{record_type}-records",
            "country": "Portugal",
            "type": record_type,
            "limit": 100,
        }
        
        if start_year:
            query_params["startYear"] = start_year
        
        if end_year:
            query_params["endYear"] = end_year
        
        records = self.search_records(query_params)
        return self.extract_names_from_records(records)


def get_familysearch_names_for_freguesia(freguesia_name, years_range=None):
    """Get names from FamilySearch for a specific freguesia."""
    api = FamilySearchAPI()
    
    if not api.authenticate():
        return []
    
    print(f"Searching for {freguesia_name}...")
    
    # Search by location
    records = api.search_portuguese_records_by_location(
        location=freguesia_name,
        record_type="death",
        start_year=years_range[0] if years_range else None,
        end_year=years_range[1] if years_range else None
    )
    
    return records


def get_all_familysearch_names():
    """Get names from FamilySearch for all freguesias."""
    # List of freguesias to search
    freguesias = [
        "Açores",
        "Aldeia da Serra", 
        "Baraçal",
        "Cadafaz",
        "Carrapichana",
        "Casas do Rio",
        "Casas do Soeiro",
        "Celorico (Santa Maria)",
        "Celorico (São Pedro)",
        "Cortiçô da Serra",
        "Forno Telheiro",
        "Galisteu",
        "Jejua",
        "Lajeosa do Mondego",
        "Linhares",
        "Maçal do Chão",
        "Mesquitela",
        "Minhocal",
        "Prados",
        "Rapa",
        "Ratoeira",
        "Salgueirais",
        "São Martinho de Celorico",
        "Vale de Azares",
        "Velosa",
        "Vide Entre Vinhas",
        "Vila Boa do Mondego",
    ]
    
    all_names = []
    
    for freguesia in freguesias:
        print(f"Processing: {freguesia}")
        names = get_familysearch_names_for_freguesia(freguesia, years_range=(1860, 1911))
        all_names.extend(names)
        print(f"  Found {len(names)} records")
        
        # Rate limiting
        time.sleep(1)
    
    return all_names


if __name__ == "__main__":
    # Test with a single freguesia
    names = get_familysearch_names_for_freguesia("Açores", years_range=(1860, 1911))
    
    print(f"\n=== TEST RESULTS ===")
    print(f"Found {len(names)} records")
    
    for name in names[:10]:
        print(f"  {name.get('fullName', 'Unknown')} - {name.get('deathDate', 'Unknown')} - {name.get('place', 'Unknown')}")
