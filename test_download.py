#!/usr/bin/env python3
"""
Test downloading images from Digitarq using requests.
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re

DOC_IDS = [
    "fd0cf2bc50b14e739e362b44c64dc194",  # Celorico (São Pedro) 1746-1772
    "39131ac29f214a4f8a65ff2d860a9084",  # Celorico (São Pedro) 1772-1802
    "23e05c58b0114891b0099e638e8e3f79",  # Celorico (São Pedro) 1811-1856
]

# Try common API endpoints
API_PATTERNS = [
    "https://digitarq.arquivos.pt/api/v1/records/{doc_id}",
    "https://digitarq.arquivos.pt/api/v1/search?q={doc_id}",
    "https://digitarq.arquivos.pt/api/records/{doc_id}",
    "https://digitarq.arquivos.pt/api/document/{doc_id}",
    "https://digitarq.arquivos.pt/api/v1/representations/{doc_id}",
    "https://digitarq.arquivos.pt/iiif/manifest/{doc_id}",
    "https://digitarq.arquivos.pt/api/v2/records/{doc_id}",
    "https://digitarq.arquivos.pt/content/{doc_id}",
]


def create_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    return session


def get_image_urls_from_viewer(session, doc_id):
    """Try to get image URLs from the viewer page."""
    urls = []
    
    # Try the viewer page
    viewer_url = f"https://digitarq.arquivos.pt/fileViewer/{doc_id}"
    print(f"Trying: {viewer_url}")
    
    try:
        resp = session.get(viewer_url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if resp.status_code == 200:
            content = resp.text
            print(f"  Page size: {len(content)} chars")
            
            # Look for image URLs in the page source
            img_patterns = re.findall(r'(https?://[^\s"\'<]+\.(?:jpg|jpeg|png|gif|tiff?|webp))', content, re.I)
            urls.extend(img_patterns)
            
            # Look for IIIF URLs
            iiif_patterns = re.findall(r'(https?://[^\s"\'<]+/iiif/[^\s"\'<]+)', content, re.I)
            urls.extend(iiif_patterns)
            
            # Look for API endpoints
            api_patterns = re.findall(r'(https?://api[^\s"\'<]+)', content, re.I)
            urls.extend(api_patterns)
            
            # Look for JSON data in the page
            json_patterns = re.findall(r'(dataUrl|imageUrl|src|href)["\']?\s*:\s*["\']([^"\']+)["\']', content, re.I)
            for match in json_patterns[:10]:
                urls.append(match[1] if len(match) > 1 else match[0])
            
            print(f"  Found {len(urls)} potential URLs in page")
            print(f"  First 500 chars: {content[:500]}")
            
        else:
            print(f"  HTTP {resp.status_code}")
            
    except Exception as e:
        print(f"  Error: {e}")
    
    return list(set(urls))  # Remove duplicates


def try_known_patterns(session, doc_id):
    """Try known patterns for Digitarq image URLs."""
    urls = []
    
    # Common patterns for archival image servers
    patterns = [
        f"https://digitarq.arquivos.pt/content/delivery/{doc_id}",
        f"https://digitarq.arquivos.pt/api/v1/images/{doc_id}",
        f"https://digitarq.arquivos.pt/api/images/{doc_id}",
    ]
    
    for url in patterns:
        try:
            resp = session.head(url, timeout=10)
            if resp.status_code < 400:
                print(f"  HEAD {url}: {resp.status_code}")
                urls.append(url)
        except Exception as e:
            print(f"  HEAD {url}: {e}")
    
    return urls


def main():
    session = create_session()
    
    for doc_id in DOC_IDS:
        print(f"\n=== Document: {doc_id} ===")
        
        # Try viewer page
        urls = get_image_urls_from_viewer(session, doc_id)
        
        if not urls:
            # Try known patterns
            print("Trying known patterns...")
            urls = try_known_patterns(session, doc_id)
        
        if urls:
            print(f"\nFound {len(urls)} URLs:")
            for url in urls[:5]:
                print(f"  {url[:80]}...")
        else:
            print("No image URLs found - trying API endpoints...")
            try_api_endpoints(session, doc_id)


def try_api_endpoints(session, doc_id):
    """Try known API endpoints."""
    for url_template in API_PATTERNS:
        url = url_template.replace('{doc_id}', doc_id)
        try:
            resp = session.get(url, timeout=15)
            print(f"  {url[:60]}... -> {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else resp.text
                print(f"    Data: {str(data)[:200]}...")
        except Exception as e:
            print(f"  Error: {e}")


if __name__ == "__main__":
    main()