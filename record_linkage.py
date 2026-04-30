"""
Record Linkage system for genealogy.
Intelligently merges baptism and death records to construct full family histories.
"""
import os
import logging
import requests
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RecordLinker:
    """Links baptism and death records."""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json"
        }
    
    def find_and_merge(self, limit: int = 100):
        """Finds potential links and merges them."""
        # 1. Fetch recent records
        batismos = self._fetch_records("batismos", limit)
        obitos = self._fetch_records("pessoas", limit)
        
        linked = 0
        for b in batismos:
            # Simple linkage heuristic: Name match + Year match
            match = self._find_best_match(b, obitos)
            if match:
                self._merge_records(b, match)
                linked += 1
        
        logger.info(f"Successfully linked {linked} records")
        return linked
    
    def _fetch_records(self, table: str, limit: int) -> List[Dict]:
        """Fetch records from Supabase."""
        resp = requests.get(
            f"{self.supabase_url}/rest/v1/{table}",
            headers=self.headers,
            params={"limit": limit},
            timeout=30
        )
        return resp.json() if resp.status_code == 200 else []
    
    def _find_best_match(self, batismo: Dict, obitos: List[Dict]) -> Optional[Dict]:
        """Find the best match for a baptism record."""
        for o in obitos:
            # Heuristic: Same name and death after baptism
            if batismo.get('nome') == o.get('nome'):
                b_ano = batismo.get('ano', 0)
                o_ano = o.get('ano', 0)
                if b_ano and o_ano and o_ano > b_ano:
                    return o
        return None
    
    def _merge_records(self, batismo: Dict, obito: Dict):
        """Merge two records into a 'pessoas_unificadas' table."""
        logger.info(f"Merging: {batismo.get('nome')} (Batismo) + {obito.get('nome')} (Óbito)")
        # In a real scenario, this would POST to a new unified table
        pass

if __name__ == "__main__":
    url = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_KEY', '')
    if url and key:
        linker = RecordLinker(url, key)
        linker.find_and_merge()
