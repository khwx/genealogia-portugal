"""
Advanced search and filtering system for genealogy records.
Provides multi-criteria search with real-time suggestions and notifications.
"""
import re
import json
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from functools import lru_cache
from functools import reduce
import threading
import hashlib
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SearchFilter:
    """Represents a search filter criterion."""
    field: str
    operator: str
    value: Any
    value2: Optional[Any] = None

@dataclass
class SearchQuery:
    """Represents a complete search query with multiple filters."""
    text: str = ""
    filters: List[SearchFilter] = field(default_factory=list)
    sort_by: str = "data_obito"
    sort_order: str = "desc"
    limit: int = 50
    offset: int = 0
    include_quality: bool = True
    min_quality: float = 0.0

class SearchSuggestions:
    """Provides real-time search suggestions based on query history."""
    
    def __init__(self, cache_size: int = 1000):
        self.cache_size = cache_size
        self.query_history = []
        self.suggestions_cache = {}
        self.lock = threading.Lock()
    
    def add_query(self, query: str):
        """Add a query to history for suggestions."""
        with self.lock:
            # Normalize query
            normalized = query.lower().strip()
            
            # Add to history (avoid duplicates)
            if normalized not in self.query_history:
                self.query_history.insert(0, normalized)
                if len(self.query_history) > self.cache_size:
                    self.query_history.pop()
    
    def get_suggestions(self, prefix: str, limit: int = 10) -> List[str]:
        """Get suggestions based on prefix."""
        prefix = prefix.lower().strip()
        
        if len(prefix) < 2:
            return []
        
        # Check cache
        cache_key = hashlib.md5(f"{prefix}_{limit}".encode()).hexdigest()
        if cache_key in self.suggestions_cache:
            return self.suggestions_cache[cache_key]
        
        with self.lock:
            suggestions = []
            seen = set()
            
            for query in self.query_history:
                if query.startswith(prefix) and query not in seen:
                    suggestions.append(query)
                    seen.add(query)
                    if len(suggestions) >= limit:
                        break
            
            # Also suggest common Portuguese names
            common_patterns = self._get_common_patterns(prefix)
            for pattern in common_patterns:
                if pattern not in seen:
                    suggestions.append(pattern)
                    seen.add(pattern)
                    if len(suggestions) >= limit:
                        break
            
            # Update cache
            self.suggestions_cache[cache_key] = suggestions[:limit]
            
            return suggestions[:limit]
    
    def _get_common_patterns(self, prefix: str) -> List[str]:
        """Get common name patterns for prefix."""
        common_prefixes = {
            'jo': ['joao', 'jose', 'joana', 'josé'],
            'an': ['antonio', 'ana', 'andré', 'anelisa'],
            'ma': ['manuel', 'maria', 'manuela', 'margarida'],
            'fr': ['francisco', 'francisca', 'francesco'],
            'pe': ['pedro', 'pereira', 'pinto'],
            'ca': ['carlos', 'carla', 'catarina', 'carolina'],
            'lu': ['luis', 'luisa', 'lucas', 'lucia'],
            'mi': ['miguel', 'mikael', 'milene'],
            'br': ['bruno', 'branca', 'brun0'],
            'fe': ['fernando', 'fernanda', 'felix'],
            'ag': ['agostinho', 'agueda', 'agostinho'],
            'ce': ['celia', 'celestino', 'cecilia'],
            'te': ['teresa', 'teddy', 'teofilo'],
        }
        
        return common_prefixes.get(prefix.lower()[:2], [])

class NotificationManager:
    """Manages search result notifications."""
    
    def __init__(self):
        self.subscribers = {}
        self.notification_queue = []
        self.lock = threading.Lock()
    
    def subscribe(self, user_id: str, criteria: Dict):
        """Subscribe a user to notifications for specific criteria."""
        with self.lock:
            if user_id not in self.subscribers:
                self.subscribers[user_id] = []
            
            self.subscribers[user_id].append({
                'criteria': criteria,
                'subscribed_at': datetime.now().isoformat(),
                'last_notification': None
            })
            
            logger.info(f"User {user_id} subscribed to notifications")
    
    def unsubscribe(self, user_id: str, subscription_id: Optional[int] = None):
        """Unsubscribe a user from notifications."""
        with self.lock:
            if user_id in self.subscribers:
                if subscription_id is not None:
                    if 0 <= subscription_id < len(self.subscribers[user_id]):
                        self.subscribers[user_id].pop(subscription_id)
                else:
                    self.subscribers[user_id] = []
    
    def notify_match(self, user_id: str, record: Dict):
        """Notify a user about a matching record."""
        with self.lock:
            if user_id in self.subscribers:
                for subscription in self.subscribers[user_id]:
                    if self._matches_criteria(record, subscription['criteria']):
                        self.notification_queue.append({
                            'user_id': user_id,
                            'record': record,
                            'timestamp': datetime.now().isoformat()
                        })
    
    def _matches_criteria(self, record: Dict, criteria: Dict) -> bool:
        """Check if a record matches notification criteria."""
        if 'name_contains' in criteria:
            name = record.get('nome', '').lower()
            if criteria['name_contains'].lower() not in name:
                return False
        
        if 'year_from' in criteria:
            year = record.get('ano')
            if year and year < criteria['year_from']:
                return False
        
        if 'year_to' in criteria:
            year = record.get('ano')
            if year and year > criteria['year_to']:
                return False
        
        if 'freguesia' in criteria:
            if record.get('freguesia') != criteria['freguesia']:
                return False
        
        return True
    
    def get_pending_notifications(self, user_id: str) -> List[Dict]:
        """Get pending notifications for a user."""
        with self.lock:
            notifications = [
                n for n in self.notification_queue
                if n['user_id'] == user_id
            ]
            
            # Clear processed notifications
            self.notification_queue = [
                n for n in self.notification_queue
                if n['user_id'] != user_id
            ]
            
            return notifications

class AdvancedSearch:
    """Advanced search engine for genealogy records."""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.suggestions = SearchSuggestions()
        self.notifications = NotificationManager()
        self.headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json"
        }
        self._cache = {}
        self._cache_lock = threading.Lock()
    
    def search(self, query: SearchQuery) -> Dict:
        """Execute an advanced search query."""
        try:
            # Build the query
            params = self._build_params(query)
            
            # Execute search
            response = self._execute_search(params, query)
            
            # Add suggestions
            if query.text:
                self.suggestions.add_query(query.text)
            
            return response
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return {'error': str(e), 'results': [], 'total': 0}
    
    def _build_params(self, query: SearchQuery) -> Dict:
        """Build Supabase query parameters."""
        params = {
            'select': '*',
            'order': f"{query.sort_by}.{query.sort_order}",
            'limit': query.limit,
            'offset': query.offset
        }
        
        # Text search (name)
        if query.text:
            params['nome'] = f'ilike.*{query.text}*'
        
        # Apply filters
        for filter in query.filters:
            param_key = self._filter_to_param(filter)
            if param_key:
                params[param_key] = self._filter_value_to_param(filter)
        
        # Quality filter
        if query.include_quality and query.min_quality > 0:
            params['qualidade'] = f'gte.{query.min_quality}'
        
        return params
    
    def _filter_to_param(self, filter: SearchFilter) -> Optional[str]:
        """Convert a filter to a Supabase parameter."""
        field_mapping = {
            'nome': 'nome',
            'data_obito': 'data_obito',
            'ano': 'ano',
            'freguesia': 'freguesia',
            'concelho': 'concelho',
            'distrito': 'distrito',
            'qualidade': 'qualidade'
        }
        
        if filter.field not in field_mapping:
            return None
        
        base_field = field_mapping[filter.field]
        
        # Handle operators
        if filter.operator == 'eq':
            return base_field
        elif filter.operator == 'gt':
            return f"{base_field}.gt"
        elif filter.operator == 'lt':
            return f"{base_field}.lt"
        elif filter.operator == 'gte':
            return f"{base_field}.gte"
        elif filter.operator == 'lte':
            return f"{base_field}.lte"
        elif filter.operator == 'like':
            return base_field
        elif filter.operator == 'in':
            return f"{base_field}.in"
        
        return None
    
    def _filter_value_to_param(self, filter: SearchFilter) -> str:
        """Convert filter value to parameter value."""
        if filter.operator == 'like':
            return f'ilike.*{filter.value}*'
        elif filter.operator == 'in':
            if isinstance(filter.value, list):
                return f"({','.join(str(v) for v in filter.value)})"
            return str(filter.value)
        elif filter.operator == 'between':
            return f"{filter.value},{filter.value2}"
        
        return str(filter.value)
    
    def _execute_search(self, params: Dict, query: SearchQuery) -> Dict:
        """Execute search against Supabase."""
        # Check cache first
        cache_key = self._get_cache_key(params)
        with self._cache_lock:
            if cache_key in self._cache:
                cached = self._cache[cache_key]
                if datetime.now() - cached['timestamp'] < timedelta(minutes=5):
                    return cached['result']
        
        # Execute request
        response = requests.get(
            f"{self.supabase_url}/rest/v1/pessoas",
            headers=self.headers,
            params=params,
            timeout=30
        )
        
        if response.status_code == 200:
            results = response.json()
            total = len(results)
            
            result = {
                'results': results,
                'total': total,
                'query': query.text,
                'filters': [f"{f.field}_{f.operator}_{f.value}" for f in query.filters],
                'suggestions': self.suggestions.get_suggestions(query.text) if query.text else []
            }
            
            # Cache results
            with self._cache_lock:
                self._cache[cache_key] = {
                    'result': result,
                    'timestamp': datetime.now()
                }
            
            return result
        else:
            logger.error(f"Search failed: {response.status_code}")
            return {'error': f'Search failed: {response.status_code}', 'results': [], 'total': 0}
    
    def _get_cache_key(self, params: Dict) -> str:
        """Generate cache key for params."""
        param_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()
    
    def get_suggestions(self, prefix: str, limit: int = 10) -> List[str]:
        """Get search suggestions for a prefix."""
        return self.suggestions.get_suggestions(prefix, limit)
    
    def subscribe_to_updates(self, user_id: str, criteria: Dict):
        """Subscribe user to notification for matching records."""
        self.notifications.subscribe(user_id, criteria)
    
    def get_notifications(self, user_id: str) -> List[Dict]:
        """Get pending notifications for a user."""
        return self.notifications.get_pending_notifications(user_id)


def build_search_from_params(params: Dict) -> SearchQuery:
    """Build a SearchQuery from request parameters."""
    query = SearchQuery()
    
    # Text search
    if 'q' in params:
        query.text = params['q'].strip()
    
    # Filters
    filter_specs = [
        ('freguesia', 'freguesia', 'eq'),
        ('concelho', 'concelho', 'eq'),
        ('distrito', 'distrito', 'eq'),
        ('ano_min', 'ano', 'gte'),
        ('ano_max', 'ano', 'lte'),
        ('qualidade_min', 'qualidade', 'gte'),
    ]
    
    for param_name, field, operator in filter_specs:
        if param_name in params and params[param_name]:
            query.filters.append(SearchFilter(
                field=field,
                operator=operator,
                value=params[param_name]
            ))
    
    # Sort
    if 'sort' in params:
        query.sort_by = params['sort']
    if 'order' in params:
        query.sort_order = params['order']
    
    # Pagination
    if 'limit' in params:
        query.limit = min(int(params['limit']), 100)
    if 'offset' in params:
        query.offset = int(params['offset'])
    
    return query


if __name__ == "__main__":
    # Test advanced search
    import os
    
    supabase_url = os.environ.get('SUPABASE_URL', '')
    supabase_key = os.environ.get('SUPABASE_KEY', '')
    
    if supabase_url and supabase_key:
        search = AdvancedSearch(supabase_url, supabase_key)
        
        # Simple search
        query = SearchQuery(text="silva")
        result = search.search(query)
        print(f"Found {result['total']} results for 'silva'")
        
        # Search with filters
        query = SearchQuery(
            text="",
            filters=[
                SearchFilter(field='ano', operator='gte', value=1860),
                SearchFilter(field='ano', operator='lte', value=1870),
            ],
            sort_by='ano',
            sort_order='asc'
        )
        result = search.search(query)
        print(f"Found {result['total']} results for 1860-1870")
        
        # Get suggestions
        suggestions = search.get_suggestions("jo")
        print(f"Suggestions for 'jo': {suggestions}")
    else:
        print("Supabase credentials not configured")