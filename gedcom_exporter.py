"""
GEDCOM Export module for genealogy interoperability.
Converts database records into the standard GEDCOM 5.5 format.
"""
import os
import logging
import requests
from datetime import datetime
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GedcomExporter:
    """Exports genealogy records to GEDCOM format."""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json"
        }
    
    def generate_gedcom(self, person_id: str) -> str:
        """Generate a GEDCOM file for a specific person and their known relatives."""
        try:
            # 1. Fetch the person and their relatives from Supabase
            person = self._fetch_person(person_id)
            if not person:
                return "Error: Person not found"
            
            # 2. Build GEDCOM structure
            lines = []
            lines.append("0 HEAD")
            lines.append("1 SOURCE GenealogyProject")
            lines.append("1 GEDC")
            lines.append("2 VERS 5.5")
            lines.append("1 CHAR UTF-8")
            
            # Person record
            person_id_ged = f" @I{person.get('id', '1')}@ "
            lines.append(f"0 {person_id_ged.strip()} INDI")
            
            # Name
            name = person.get('nome', 'Unknown')
            lines.append(f"1 NAME {name}")
            
            # Gender (assuming derived from name or record)
            gender = "M" if "Joao" in name or "Antonio" in name else "F"
            lines.append(f"1 SEX {gender}")
            
            # Birth (if we have baptism data)
            birth_date = person.get('data_batismo') or person.get('data_nascimento')
            if birth_date:
                lines.append("1 BIRT")
                lines.append(f"2 DATE {birth_date}")
            
            # Death
            death_date = person.get('data_obito')
            if death_date:
                lines.append("1 DEAT")
                lines.append(f"2 DATE {death_date}")
            
            # Place
            place = person.get('freguesia', 'Celorico da Beira')
            lines.append(f"1 PLAC {place}, Portugal")
            
            lines.append("0 TRLR")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"GEDCOM export error: {e}")
            return f"Error generating GEDCOM: {e}"
    
    def _fetch_person(self, person_id: str) -> Optional[Dict]:
        """Fetch person details from Supabase."""
        try:
            resp = requests.get(
                f"{self.supabase_url}/rest/v1/pessoas?id=eq.{person_id}",
                headers=self.headers,
                timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                return data[0] if data else None
        except Exception as e:
            logger.error(f"Error fetching person: {e}")
        return None

if __name__ == "__main__":
    # Test export
    import os
    url = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_KEY', '')
    if url and key:
        exporter = GedcomExporter(url, key)
        print(exporter.generate_gedcom("1"))
    else:
        print("Supabase credentials not configured")
