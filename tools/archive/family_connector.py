"""
Family connection algorithms using Pinecone vector database.
Provides intelligent matching and relationship discovery.
"""
import os
import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import hashlib
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PersonRecord:
    """Represents a person for vector embedding."""
    id: str
    nome: str
    data_nascimento: Optional[str] = None
    data_obito: Optional[str] = None
    pai: Optional[str] = None
    mae: Optional[str] = None
    freguesia: str = ""
    ano: Optional[int] = None
    tipo: str = "obito"
    sobrenomes: List[str] = field(default_factory=list)

class PineconeFamilyConnector:
    """Uses Pinecone for intelligent family relationship discovery."""
    
    def __init__(self, api_key: Optional[str] = None, environment: Optional[str] = None):
        self.api_key = api_key or os.environ.get('PINECONE_API_KEY', '')
        self.environment = environment or os.environ.get('PINECONE_ENVIRONMENT', 'us-east-1')
        self.index_name = 'genealogy-portugal'
        self.vectors = {}
        self.dimension = 128  # Embedding dimension
        
        if self.api_key:
            self._init_pinecone()
        else:
            logger.warning("Pinecone API key not configured")
    
    def _init_pinecone(self):
        """Initialize Pinecone connection."""
        try:
            from pinecone import Pinecone, ServerlessSpec
            
            self.pc = Pinecone(api_key=self.api_key)
            
            # Create index if it doesn't exist
            existing = [idx['name'] for idx in self.pc.list_indexes()['indexes']]
            if self.index_name not in existing:
                self.pc.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    spec=ServerlessSpec(cloud='aws', region=self.environment)
                )
                logger.info(f"Created Pinecone index: {self.index_name}")
            
            self.index = self.pc.Index(self.index_name)
            logger.info("✅ Pinecone initialized successfully")
            
        except ImportError:
            logger.error("Pinecone library not installed. Run: pip install pinecone-client")
        except Exception as e:
            logger.error(f"Error initializing Pinecone: {e}")
    
    def _generate_embedding(self, person: PersonRecord) -> List[float]:
        """Generate a simple embedding for a person based on their attributes."""
        # Simple hashing-based embedding for demo purposes
        # In production, use proper embeddings from NVIDIA or OpenAI
        
        features = [
            person.nome.lower() if person.nome else "",
            str(person.ano) if person.ano else "",
            person.freguesia.lower() if person.freguesia else "",
            person.pai.lower() if person.pai else "",
            person.mae.lower() if person.mae else "",
        ]
        
        # Create a simple numeric representation
        embedding = []
        for i, feature in enumerate(features):
            hash_val = int(hashlib.md5(feature.encode()).hexdigest()[:8], 16)
            embedding.append((hash_val % 1000) / 1000.0)
        
        # Pad to dimension
        while len(embedding) < self.dimension:
            idx = len(embedding)
            hash_val = int(hashlib.md5(str(idx).encode()).hexdigest()[:8], 16)
            embedding.append((hash_val % 1000) / 1000.0)
        
        return embedding[:self.dimension]
    
    def index_person(self, person: PersonRecord) -> bool:
        """Index a person in Pinecone."""
        if not self.api_key:
            return False
        
        try:
            embedding = self._generate_embedding(person)
            vector_id = person.id
            
            metadata = {
                'nome': person.nome,
                'ano': person.ano,
                'freguesia': person.freguesia,
                'tipo': person.tipo,
                'pai': person.pai,
                'mae': person.mae
            }
            
            self.index.upsert(vectors=[{
                'id': vector_id,
                'values': embedding,
                'metadata': metadata
            }])
            
            logger.info(f"Indexed person: {person.nome}")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing person: {e}")
            return False
    
    def find_similar(self, person: PersonRecord, top_k: int = 10) -> List[Dict]:
        """Find similar people based on vector similarity."""
        if not self.api_key:
            return []
        
        try:
            embedding = self._generate_embedding(person)
            
            results = self.index.query(
                vector=embedding,
                top_k=top_k,
                include_metadata=True
            )
            
            similar = []
            for match in results.get('matches', []):
                if match['id'] != person.id:  # Exclude self
                    similar.append({
                        'id': match['id'],
                        'score': match['score'],
                        'nome': match['metadata'].get('nome'),
                        'ano': match['metadata'].get('ano'),
                        'freguesia': match['metadata'].get('freguesia'),
                        'tipo': match['metadata'].get('tipo')
                    })
            
            return similar
            
        except Exception as e:
            logger.error(f"Error finding similar: {e}")
            return []
    
    def find_potential_relatives(self, person: PersonRecord) -> Dict:
        """Find potential relatives for a person."""
        if not self.api_key:
            return {}
        
        relatives = {
            'person': person.nome,
            'potential_siblings': [],
            'potential_aunts_uncles': [],
            'potential_cousins': [],
            'same_surname': [],
            'same_location': [],
            'same_time_period': []
        }
        
        # Find similar people
        similar = self.find_similar(person, top_k=50)
        
        for match in similar:
            # Check for same surname
            if person.sobrenomes and any(s in match.get('nome', '').lower() for s in person.sobrenomes):
                relatives['same_surname'].append(match)
            
            # Check for same location
            if match.get('freguesia') == person.freguesia:
                relatives['same_location'].append(match)
            
            # Check for same time period (within 10 years)
            match_ano = match.get('ano')
            if match_ano and person.ano:
                if abs(match_ano - person.ano) <= 10:
                    relatives['same_time_period'].append(match)
            
            # Check for potential sibling (same parents, similar age)
            if match_ano and person.ano and abs(match_ano - person.ano) <= 3:
                # Could be siblings if we had parent info
                pass
        
        return relatives
    
    def batch_index(self, persons: List[PersonRecord]) -> int:
        """Batch index multiple people."""
        if not self.api_key or not persons:
            return 0
        
        vectors = []
        for person in persons:
            embedding = self._generate_embedding(person)
            vectors.append({
                'id': person.id,
                'values': embedding,
                'metadata': {
                    'nome': person.nome,
                    'ano': person.ano,
                    'freguesia': person.freguesia,
                    'tipo': person.tipo
                }
            })
        
        try:
            self.index.upsert(vectors=vectors)
            logger.info(f"Batch indexed {len(persons)} people")
            return len(persons)
        except Exception as e:
            logger.error(f"Error in batch indexing: {e}")
            return 0


class SurnameAnalyzer:
    """Analyzes surname patterns to identify family groups."""
    
    def __init__(self):
        self.surname_groups = {}
        self.common_surnames = {
            'silva', 'santos', 'pereira', 'costa', 'rodrigues',
            'martins', 'oliveira', 'ferreira', 'gomes', 'carvalho',
            'almeida', 'pinto', 'dias', 'moura', 'teixeira',
            'neto', 'fernandes', 'ramos', 'henriques', 'lima'
        }
    
    def extract_surnames(self, name: str) -> List[str]:
        """Extract surnames from a full name."""
        if not name:
            return []
        
        parts = name.lower().split()
        surnames = []
        
        # Portuguese naming: first name + middle names + surname(s)
        # Typically: FirstName [MiddleName(s)] [Surname(s)]
        # Surnames often contain "da", "de", "dos", "das"
        
        for i, part in enumerate(parts):
            # Check for preposition
            if part in ['da', 'de', 'do', 'das', 'dos']:
                if i + 1 < len(parts):
                    surnames.append(f"{part} {parts[i + 1]}")
            # Common surnames
            elif part in self.common_surnames:
                surnames.append(part)
            # Last names typically are surnames
            elif i >= 2:
                surnames.append(part)
        
        return surnames
    
    def group_by_surname(self, records: List[Dict]) -> Dict[str, List[Dict]]:
        """Group records by surname."""
        groups = {}
        
        for record in records:
            nome = record.get('nome', '')
            surnames = self.extract_surnames(nome)
            
            for surname in surnames:
                if surname not in groups:
                    groups[surname] = []
                groups[surname].append(record)
        
        return groups
    
    def find_family_groups(self, records: List[Dict]) -> List[Dict]:
        """Find potential family groups based on surname and time."""
        surname_groups = self.group_by_surname(records)
        
        families = []
        for surname, members in surname_groups.items():
            if len(members) >= 2:
                # Group by approximate time period (within 20 years)
                members.sort(key=lambda x: x.get('ano', 0))
                
                current_group = [members[0]]
                for member in members[1:]:
                    last_year = current_group[-1].get('ano', 0)
                    current_year = member.get('ano', 0)
                    
                    if current_year - last_year <= 20:
                        current_group.append(member)
                    else:
                        if len(current_group) >= 2:
                            families.append({
                                'surname': surname,
                                'members': current_group,
                                'count': len(current_group),
                                'year_range': (
                                    current_group[0].get('ano', 0),
                                    current_group[-1].get('ano', 0)
                                )
                            })
                        current_group = [member]
                
                # Don't forget the last group
                if len(current_group) >= 2:
                    families.append({
                        'surname': surname,
                        'members': current_group,
                        'count': len(current_group),
                        'year_range': (
                            current_group[0].get('ano', 0),
                            current_group[-1].get('ano', 0)
                        )
                    })
        
        # Sort by count
        families.sort(key=lambda x: x['count'], reverse=True)
        
        return families


class RelationshipInferrer:
    """Infers potential family relationships based on records."""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json"
        }
        self.surname_analyzer = SurnameAnalyzer()
    
    def infer_relationships(self, person_name: str) -> Dict:
        """Infer all possible relationships for a person."""
        result = {
            'name': person_name,
            'surnames': self.surname_analyzer.extract_surnames(person_name),
            'potential_parents': [],
            'potential_children': [],
            'potential_siblings': [],
            'potential_spouses': [],
            'family_groups': []
        }
        
        # Search for records with similar surnames
        for surname in result['surnames']:
            records = self._search_by_surname(surname)
            
            for record in records:
                if record.get('nome') == person_name:
                    continue
                
                relationship = self._determine_relationship(person_name, record)
                if relationship:
                    result[relationship].append(record)
        
        return result
    
    def _search_by_surname(self, surname: str) -> List[Dict]:
        """Search for records with this surname."""
        try:
            # Search obitos
            resp1 = requests.get(
                f"{self.supabase_url}/rest/v1/pessoas",
                headers=self.headers,
                params={'nome': f'ilike.*{surname}*', 'limit': 50},
                timeout=30
            )
            
            records = []
            if resp1.status_code == 200:
                records.extend(resp1.json())
            
            # Search batismos
            resp2 = requests.get(
                f"{self.supabase_url}/rest/v1/batismos",
                headers=self.headers,
                params={'nome': f'ilike.*{surname}*', 'limit': 50},
                timeout=30
            )
            
            if resp2.status_code == 200:
                records.extend(resp2.json())
            
            return records
            
        except Exception as e:
            logger.error(f"Error searching by surname: {e}")
            return []
    
    def _determine_relationship(self, person_name: str, other_record: Dict) -> Optional[str]:
        """Determine the likely relationship type."""
        person_year = self._get_year(person_name)
        other_year = other_record.get('ano')
        
        if not other_year:
            return None
        
        # If person is older, other could be child
        if person_year and other_year > person_year:
            if other_year - person_year >= 15:
                return 'potential_children'
        
        # If person is younger, other could be parent
        if person_year and other_year < person_year:
            if person_year - other_year >= 15:
                return 'potential_parents'
        
        # Similar age could be sibling
        if person_year and other_year:
            if abs(person_year - other_year) <= 5:
                return 'potential_siblings'
        
        return None
    
    def _get_year(self, name: str) -> Optional[int]:
        """Extract year from a name string (if stored somewhere)."""
        # This would need to look up the record
        return None


def test_pinecone_family():
    """Test the Pinecone family connector."""
    print("=== Teste Pinecone Family Connector ===")
    
    connector = PineconeFamilyConnector()
    
    if not connector.api_key:
        print("⚠️  Pinecone API key not configured. Running in simulation mode.")
    
    # Test with sample person
    person = PersonRecord(
        id="test_001",
        nome="João da Silva",
        ano=1864,
        freguesia="Celorico Santa Maria",
        tipo="obito",
        sobrenomes=["silva"]
    )
    
    # Test embedding
    embedding = connector._generate_embedding(person)
    print(f"Embedding dimension: {len(embedding)}")
    
    # Test surname analyzer
    analyzer = SurnameAnalyzer()
    surnames = analyzer.extract_surnames("João da Silva")
    print(f"Surnames extracted: {surnames}")
    
    # Test family grouping
    test_records = [
        {'nome': 'João da Silva', 'ano': 1860, 'freguesia': 'Celorico'},
        {'nome': 'Maria da Silva', 'ano': 1862, 'freguesia': 'Celorico'},
        {'nome': 'Manuel da Silva', 'ano': 1865, 'freguesia': 'Celorico'},
        {'nome': 'António Costa', 'ano': 1860, 'freguesia': 'Celorico'},
        {'nome': 'José da Silva', 'ano': 1880, 'freguesia': 'Celorico'},
    ]
    
    families = analyzer.find_family_groups(test_records)
    print(f"\nFound {len(families)} family groups:")
    for family in families[:5]:
        print(f"  - {family['surname']}: {family['count']} members, {family['year_range']}")
    
    return families


if __name__ == "__main__":
    test_pinecone_family()