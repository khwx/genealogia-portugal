"""
Caching system and image compression for genealogy records.
Provides efficient storage and retrieval of frequently accessed data.
"""
import os
import json
import time
import logging
import hashlib
import shutil
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from functools import wraps
import threading
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CacheManager:
    """Manages caching for API responses and search results."""
    
    def __init__(self, cache_dir: str = 'cache', max_size_mb: int = 100):
        self.cache_dir = cache_dir
        self.max_size_mb = max_size_mb
        self.memory_cache = {}
        self.cache_lock = threading.Lock()
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist."""
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(os.path.join(self.cache_dir, 'api'), exist_ok=True)
        os.makedirs(os.path.join(self.cache_dir, 'search'), exist_ok=True)
        os.makedirs(os.path.join(self.cache_dir, 'images'), exist_ok=True)
    
    def _get_cache_key(self, endpoint: str, params: Dict) -> str:
        """Generate a unique cache key for an API request."""
        param_str = json.dumps(params, sort_keys=True)
        key_str = f"{endpoint}:{param_str}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cache_path(self, key: str, category: str = 'api') -> str:
        """Get the file path for a cache key."""
        return os.path.join(self.cache_dir, category, f"{key}.json")
    
    def get(self, endpoint: str, params: Dict, category: str = 'api', max_age_minutes: int = 5) -> Optional[Any]:
        """Get a cached response if available and fresh."""
        key = self._get_cache_key(endpoint, params)
        cache_path = self._get_cache_path(key, category)
        
        with self.cache_lock:
            # Check memory cache first
            if key in self.memory_cache:
                cached = self.memory_cache[key]
                age = (datetime.now() - cached['timestamp']).total_seconds() / 60
                if age < max_age_minutes:
                    logger.debug(f"Memory cache hit: {endpoint}")
                    return cached['data']
            
            # Check file cache
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, 'r', encoding='utf-8') as f:
                        cached = json.load(f)
                    
                    age = (datetime.now() - datetime.fromisoformat(cached['timestamp'])).total_seconds() / 60
                    if age < max_age_minutes:
                        logger.debug(f"File cache hit: {endpoint}")
                        # Update memory cache
                        self.memory_cache[key] = cached
                        return cached['data']
                    else:
                        # Expired
                        os.remove(cache_path)
                except Exception as e:
                    logger.warning(f"Error reading cache: {e}")
        
        return None
    
    def set(self, endpoint: str, params: Dict, data: Any, category: str = 'api'):
        """Store a response in cache."""
        key = self._get_cache_key(endpoint, params)
        cache_path = self._get_cache_path(key, category)
        
        cached = {
            'endpoint': endpoint,
            'params': params,
            'data': data,
            'timestamp': datetime.now().isoformat()
        }
        
        with self.cache_lock:
            # Update memory cache
            self.memory_cache[key] = cached
            
            # Update file cache
            try:
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(cached, f)
            except Exception as e:
                logger.warning(f"Error writing cache: {e}")
        
        # Check cache size and cleanup if needed
        self._cleanup_if_needed()
    
    def _cleanup_if_needed(self):
        """Remove old cache entries if cache is too large."""
        try:
            total_size = 0
            cache_files = []
            
            for category in ['api', 'search', 'images']:
                category_dir = os.path.join(self.cache_dir, category)
                if not os.path.exists(category_dir):
                    continue
                
                for filename in os.listdir(category_dir):
                    filepath = os.path.join(category_dir, filename)
                    if os.path.isfile(filepath):
                        size = os.path.getsize(filepath)
                        total_size += size
                        cache_files.append((filepath, size, os.path.getmtime(filepath)))
            
            # Convert to MB
            total_size_mb = total_size / (1024 * 1024)
            
            if total_size_mb > self.max_size_mb:
                # Sort by modification time (oldest first)
                cache_files.sort(key=lambda x: x[2])
                
                # Remove oldest files until under limit
                for filepath, size, _ in cache_files:
                    if total_size_mb <= self.max_size_mb * 0.8:  # Keep some buffer
                        break
                    
                    try:
                        os.remove(filepath)
                        total_size_mb -= size / (1024 * 1024)
                        logger.debug(f"Removed cache file: {filepath}")
                    except Exception as e:
                        logger.warning(f"Error removing cache file: {e}")
                        
        except Exception as e:
            logger.warning(f"Error in cache cleanup: {e}")
    
    def invalidate(self, pattern: Optional[str] = None):
        """Invalidate cache entries matching a pattern."""
        with self.cache_lock:
            if pattern:
                # Remove from memory cache
                keys_to_remove = [k for k in self.memory_cache if pattern in k]
                for key in keys_to_remove:
                    del self.memory_cache[key]
                
                # Remove from file cache
                for category in ['api', 'search']:
                    category_dir = os.path.join(self.cache_dir, category)
                    if os.path.exists(category_dir):
                        for filename in os.listdir(category_dir):
                            if pattern in filename:
                                try:
                                    os.remove(os.path.join(category_dir, filename))
                                except:
                                    pass
            else:
                # Clear all
                self.memory_cache.clear()
                for category in ['api', 'search', 'images']:
                    category_dir = os.path.join(self.cache_dir, category)
                    if os.path.exists(category_dir):
                        shutil.rmtree(category_dir)
                        os.makedirs(category_dir)


def cached_api_call(cache_manager: CacheManager, category: str = 'api', max_age_minutes: int = 5):
    """Decorator for caching API calls."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Try to get from cache
            endpoint = func.__name__
            params = {'args': str(args), 'kwargs': str(kwargs)}
            
            cached = cache_manager.get(endpoint, params, category, max_age_minutes)
            if cached is not None:
                return cached
            
            # Call the function
            result = func(*args, **kwargs)
            
            # Store in cache
            cache_manager.set(endpoint, params, result, category)
            
            return result
        return wrapper
    return decorator


class ImageCompressor:
    """Compresses images for efficient storage."""
    
    def __init__(self, output_dir: str = 'compressed', quality: int = 85):
        self.output_dir = output_dir
        self.quality = quality
        os.makedirs(output_dir, exist_ok=True)
    
    def compress_image(self, input_path: str, output_path: Optional[str] = None) -> Optional[str]:
        """Compress a single image."""
        try:
            from PIL import Image
            
            if output_path is None:
                filename = os.path.basename(input_path)
                name, ext = os.path.splitext(filename)
                output_path = os.path.join(self.output_dir, f"{name}_compressed.jpg")
            
            # Open, compress, and save
            with Image.open(input_path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Resize if too large (max 2000px on longest side)
                max_size = 2000
                if max(img.size) > max_size:
                    ratio = max_size / max(img.size)
                    new_size = tuple(int(dim * ratio) for dim in img.size)
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Save with compression
                img.save(output_path, 'JPEG', quality=self.quality, optimize=True)
            
            # Return paths
            original_size = os.path.getsize(input_path)
            compressed_size = os.path.getsize(output_path)
            savings = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
            
            logger.info(f"Compressed {os.path.basename(input_path)}: {savings:.1f}% savings")
            
            return output_path
            
        except ImportError:
            logger.error("PIL not installed. Run: pip install Pillow")
            return None
        except Exception as e:
            logger.error(f"Error compressing image: {e}")
            return None
    
    def compress_batch(self, image_paths: List[str], max_workers: int = 4) -> List[str]:
        """Compress multiple images in parallel."""
        from concurrent.futures import ThreadPoolExecutor
        
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.compress_image, path): path for path in image_paths}
            
            for future in futures:
                result = future.result()
                if result:
                    results.append(result)
        
        return results
    
    def get_compression_stats(self, image_paths: List[str]) -> Dict:
        """Get compression statistics for a list of images."""
        stats = {
            'total_images': len(image_paths),
            'total_original_size': 0,
            'total_compressed_size': 0,
            'average_savings': 0
        }
        
        for path in image_paths:
            compressed_path = self._get_compressed_path(path)
            if os.path.exists(compressed_path):
                stats['total_original_size'] += os.path.getsize(path)
                stats['total_compressed_size'] += os.path.getsize(compressed_path)
            elif os.path.exists(path):
                stats['total_original_size'] += os.path.getsize(path)
        
        if stats['total_original_size'] > 0:
            stats['average_savings'] = (
                1 - stats['total_compressed_size'] / stats['total_original_size']
            ) * 100
        
        return stats
    
    def _get_compressed_path(self, original_path: str) -> str:
        """Get the compressed version path for an original image."""
        filename = os.path.basename(original_path)
        name, ext = os.path.splitext(filename)
        return os.path.join(self.output_dir, f"{name}_compressed.jpg")


class SearchResultCache:
    """Specialized cache for search results with invalidation patterns."""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.popular_searches = {}
        self.popular_lock = threading.Lock()
    
    def cache_search_result(self, query: str, results: List[Dict], filters: Dict = None):
        """Cache a search result."""
        params = {
            'q': query,
            'filters': json.dumps(filters or {}, sort_keys=True)
        }
        self.cache.set('search', params, results, category='search')
        
        # Update popular searches
        with self.popular_lock:
            query_normalized = query.lower().strip()
            if query_normalized not in self.popular_searches:
                self.popular_searches[query_normalized] = 0
            self.popular_searches[query_normalized] += 1
    
    def get_cached_search(self, query: str, filters: Dict = None) -> Optional[List[Dict]]:
        """Get cached search results."""
        params = {
            'q': query,
            'filters': json.dumps(filters or {}, sort_keys=True)
        }
        return self.cache.get('search', params, category='search', max_age_minutes=10)
    
    def get_popular_searches(self, limit: int = 10) -> List[str]:
        """Get the most popular search queries."""
        with self.popular_lock:
            sorted_searches = sorted(
                self.popular_searches.items(),
                key=lambda x: x[1],
                reverse=True
            )
            return [s[0] for s in sorted_searches[:limit]]
    
    def invalidate_for_new_records(self, freguesia: str = None):
        """Invalidate cache when new records are added."""
        if freguesia:
            self.cache.invalidate(pattern=freguesia)
        else:
            # Invalidate all search cache
            self.cache.invalidate(pattern='search')


def test_cache_system():
    """Test the cache system."""
    print("=== Teste Sistema de Cache ===")
    
    cache = CacheManager(max_size_mb=50)
    
    # Test basic caching
    cache.set('test_endpoint', {'param': 'value'}, {'result': 'test data'})
    
    cached = cache.get('test_endpoint', {'param': 'value'})
    print(f"Cached result: {cached}")
    
    # Test with compression
    compressor = ImageCompressor()
    
    # Note: This would need actual image files to test
    print(f"\nCache directory: {cache.cache_dir}")
    print(f"Compression output: {compressor.output_dir}")
    
    # Test popular searches
    search_cache = SearchResultCache(cache)
    search_cache.cache_search_result("João Silva", [{'nome': 'João da Silva'}])
    search_cache.cache_search_result("Maria Costa", [{'nome': 'Maria Costa'}])
    search_cache.cache_search_result("João Silva", [{'nome': 'João da Silva'}])
    
    popular = search_cache.get_popular_searches()
    print(f"\nPesquisas populares: {popular}")
    
    return cache, compressor


if __name__ == "__main__":
    test_cache_system()