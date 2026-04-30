"""
Birth records (batismos) extraction module.
Complements death records for complete family tree construction.
"""
import re
import json
import time
import logging
import requests
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BaptismRecord:
    """Represents a baptism record."""
    id: Optional[str] = None
    nome: str = ""
    data_batismo: Optional[str] = None
    data_nascimento: Optional[str] = None
    ano: Optional[int] = None
    pai: Optional[str] = None
    mae: Optional[str] = None
    padrinhos: List[str] = field(default_factory=list)
    freguesia: str = ""
    livro: Optional[str] = None
    pagina: Optional[int] = None
    numero_registo: Optional[str] = None
    qualidade: float = 0.5

class BatismosExtractor:
    """Extracts baptism records from scanned documents."""
    
    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.headers = {}
        if supabase_url and supabase_key:
            self.headers = {
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json"
            }
    
    def extract_from_text(self, ocr_text: str) -> List[Dict]:
        """Extract baptism records from OCR text."""
        if not ocr_text:
            return []
        
        records = []
        lines = ocr_text.split('\n')
        
        # Pattern for baptism records
        # Format: Number + Name + Date + Parents
        patterns = [
            # Number + Name + Batismo Date + Birth Date + Parents
            r'^(\d+)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:foi\s+baptizado|baptizado)\s+(?:a|em)\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})\s*(?:filho?\s+de)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)?\s*(?:e\s+de)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)?',
            # Simpler format: Name + Date + Parents
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:foi\s+baptizado|baptizado)\s+(?:a|em)\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})\s*(?:filho?\s+de)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)?',
            # Portuguese baptism format with parents
            r'^(\d+)\s+([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(\d{1,2}/\d{1,2}/\d{4})\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\s+e\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
        ]
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            for pattern_idx, pattern in enumerate(patterns):
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    record = self._parse_baptism_match(match, pattern_idx, line_num)
                    if record:
                        records.append(record)
                    break
        
        return records
    
    def _parse_baptism_match(self, match: re.Match, pattern_idx: int, line_num: int) -> Optional[Dict]:
        """Parse a baptism record from regex match."""
        try:
            if pattern_idx == 0:
                # Full format with all fields
                numero = match.group(1)
                nome = match.group(2)
                data_batismo = match.group(3)
                pai = match.group(4) if match.group(4) else None
                mae = match.group(5) if match.group(5) else None
            elif pattern_idx == 1:
                # Simple format
                numero = str(line_num)
                nome = match.group(1)
                data_batismo = match.group(2)
                pai = None
                mae = None
            elif pattern_idx == 2:
                # Date format with parents
                numero = match.group(1)
                nome = match.group(2)
                data_batismo = match.group(3)
                pai = match.group(4)
                mae = match.group(5)
            else:
                return None
            
            # Clean and validate data
            record = {
                'numero': numero,
                'nome': self._clean_name(nome),
                'data_batismo': self._normalize_date(data_batismo),
                'pai': self._clean_name(pai) if pai else None,
                'mae': self._clean_name(mae) if mae else None,
                'qualidade': 0.7,
                'linha': line_num
            }
            
            # Extract year
            if record['data_batismo']:
                year_match = re.search(r'(\d{4})', record['data_batismo'])
                if year_match:
                    record['ano'] = int(year_match.group(1))
            
            return record
            
        except Exception as e:
            logger.warning(f"Error parsing line {line_num}: {e}")
            return None
    
    def _clean_name(self, name: str) -> Optional[str]:
        """Clean a person name."""
        if not name:
            return None
        
        name = re.sub(r'[^a-zA-Z\s\-\.]', '', name).strip()
        if len(name) < 2:
            return None
        
        return name
    
    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalize date to YYYY-MM-DD format."""
        if not date_str:
            return None
        
        months = {
            "janeiro": "01", "jan": "01",
            "fevereiro": "02", "fev": "02",
            "março": "03", "marco": "03", "mar": "03",
            "abril": "04", "abr": "04",
            "maio": "05", "mai": "05",
            "junho": "06", "jun": "06",
            "julho": "07", "jul": "07",
            "agosto": "08", "ago": "08",
            "setembro": "09", "set": "09",
            "outubro": "10", "out": "10",
            "novembro": "11", "nov": "11",
            "dezembro": "12", "dez": "12",
        }
        
        # Try format: DD de Mês de AAAA
        match = re.search(r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})', date_str)
        if match:
            day = match.group(1).zfill(2)
            month_name = match.group(2).lower()
            year = match.group(3)
            month = months.get(month_name, "01")
            return f"{year}-{month}-{day}"
        
        # Try format: DD/MM/AAAA
        match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', date_str)
        if match:
            day = match.group(1).zfill(2)
            month = match.group(2).zfill(2)
            year = match.group(3)
            return f"{year}-{month}-{day}"
        
        # Try format: AAAA-MM-DD
        match = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
        if match:
            return date_str[:10]
        
        return None
    
    def save_to_supabase(self, records: List[Dict], freguesia: str = "") -> int:
        """Save baptism records to Supabase."""
        if not self.supabase_url or not self.headers:
            logger.warning("Supabase not configured")
            return 0
        
        saved = 0
        for record in records:
            try:
                data = {
                    "nome": record.get('nome', ''),
                    "data_batismo": record.get('data_batismo'),
                    "data_nascimento": record.get('data_nascimento'),
                    "ano": record.get('ano'),
                    "pai": record.get('pai'),
                    "mae": record.get('mae'),
                    "padrinhos": record.get('padrinhos', []),
                    "freguesia": freguesia or record.get('freguesia', ''),
                    "tipo": "batismo",
                    "qualidade": record.get('qualidade', 0.5)
                }
                
                # Remove None values
                data = {k: v for k, v in data.items() if v is not None}
                
                response = requests.post(
                    f"{self.supabase_url}/rest/v1/batismos",
                    headers=self.headers,
                    json=data,
                    timeout=30
                )
                
                if response.status_code in [200, 201]:
                    saved += 1
                else:
                    logger.warning(f"Failed to save record: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Error saving record: {e}")
        
        return saved


class FamilyConnectionFinder:
    """Finds family connections between baptism and death records."""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json"
        }
    
    def find_family_connections(self, person_name: str) -> Dict:
        """Find family connections for a person."""
        connections = {
            'person': person_name,
            'births': [],
            'deaths': [],
            'possible_parents': [],
            'possible_children': [],
            'possible_siblings': []
        }
        
        # Search for births with this name
        births = self._search_baptisms(person_name)
        connections['births'] = births
        
        # Search for deaths with this name
        deaths = self._search_deaths(person_name)
        connections['deaths'] = deaths
        
        # If we found a birth record, look for parents
        if births:
            for birth in births:
                if birth.get('pai'):
                    connections['possible_parents'].append({
                        'name': birth['pai'],
                        'relationship': 'father',
                        'source': 'batismo'
                    })
                if birth.get('mae'):
                    connections['possible_parents'].append({
                        'name': birth['mae'],
                        'relationship': 'mother',
                        'source': 'batismo'
                    })
        
        # Look for children (people whose parents have similar names)
        if births:
            for birth in births:
                # Search for people born to same parents
                if birth.get('pai'):
                    children = self._search_children_of(birth['pai'])
                    connections['possible_children'].extend(children)
                if birth.get('mae'):
                    children = self._search_children_of(birth['mae'])
                    connections['possible_children'].extend(children)
        
        return connections
    
    def _search_baptisms(self, name: str) -> List[Dict]:
        """Search for baptism records with this name."""
        try:
            response = requests.get(
                f"{self.supabase_url}/rest/v1/batismos",
                headers=self.headers,
                params={'nome': f'ilike.*{name}*', 'limit': 10},
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Error searching baptisms: {e}")
        
        return []
    
    def _search_deaths(self, name: str) -> List[Dict]:
        """Search for death records with this name."""
        try:
            response = requests.get(
                f"{self.supabase_url}/rest/v1/pessoas",
                headers=self.headers,
                params={'nome': f'ilike.*{name}*', 'limit': 10},
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Error searching deaths: {e}")
        
        return []
    
    def _search_children_of(self, parent_name: str) -> List[Dict]:
        """Search for children of a parent."""
        try:
            response = requests.get(
                f"{self.supabase_url}/rest/v1/batismos",
                headers=self.headers,
                params={'pai': f'ilike.*{parent_name}*', 'limit': 10},
                timeout=30
            )
            
            if response.status_code == 200:
                return [{
                    'nome': b.get('nome'),
                    'data_batismo': b.get('data_batismo'),
                    'relationship': 'sibling'
                } for b in response.json()]
        except Exception as e:
            logger.error(f"Error searching children: {e}")
        
        return []


def test_batismos_extractor():
    """Test the baptism extractor."""
    print("=== Teste Batismos Extractor ===")
    
    test_text = """
    Indice de Baptismos da Freguesia de Celorico Santa Maria 1864
    1 João da Silva foi baptizado a 15 de Janeiro de 1864 filho de Manuel da Silva e de Maria Jose
    2 Maria José Ferreira foi baptizada em 22/03/1864 filha de António Ferreira e de Ana Costa
    3 António Rodrigues foi baptizado a 5 de Junho de 1864 filho de José Rodrigues
    4 Ana Costa foi baptizada a 10 de Agosto de 1864 filha de Francisco Costa e Teresa Costa
    5 Manuel Pereira foi baptizado em 1865 filho de João Pereira e de Teresa Santos
    """
    
    extractor = BatismosExtractor()
    records = extractor.extract_from_text(test_text)
    
    print(f"\n✅ {len(records)} registos de batismo extraídos:")
    for i, record in enumerate(records, 1):
        print(f"  {i}. {record}")
    
    return records


if __name__ == "__main__":
    test_batismos_extractor()