"""
Teste de OCR com Google Vision API para registos antigos.
"""
import os
import base64
import pytest
import requests
from dotenv import load_dotenv

load_dotenv()

GOOGLE_VISION_API_KEY = os.getenv("GOOGLE_VISION_API_KEY")
TEST_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "test_image.png")


@pytest.fixture
def image_path():
    """Provide path to test image."""
    if not os.path.exists(TEST_IMAGE_PATH):
        pytest.skip("Test image not found")
    return TEST_IMAGE_PATH


def _is_valid_api_key(key: str) -> bool:
    """Check if the key looks like a valid Google API key (not service account)."""
    if not key:
        return False
    # Service account keys start with AQ. or similar, API keys are typically different format
    return not key.startswith("AQ.") and len(key) > 20


@pytest.mark.skipif(
    not _is_valid_api_key(GOOGLE_VISION_API_KEY),
    reason="GOOGLE_VISION_API_KEY not set or is a service account key (requires OAuth2)"
)
def test_google_vision_ocr(image_path):
    """Testa OCR com Google Vision API."""
    # Ler imagem
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()
    
    # API endpoint
    url = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}"
    
    # Payload
    payload = {
        "requests": [
            {
                "image": {
                    "content": image_data
                },
                "features": [
                    {
                        "type": "TEXT_DETECTION",
                        "maxResults": 10
                    }
                ]
            }
        ]
    }
    
    # Fazer pedido
    resp = requests.post(url, json=payload, timeout=30)
    
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:500]}"
    
    result = resp.json()
    
    assert "responses" in result and result["responses"], "Invalid response structure"
    
    detections = result["responses"][0].get("textAnnotations", [])
    
    # Should find some text in the test image
    assert detections, "No text found in image"
    
    # First result is the full text
    full_text = detections[0].get("description", "")
    assert full_text, "Full text description is empty"
    
    # Verify structure of detections
    for det in detections:
        assert "description" in det
        assert "confidence" in det or "locale" in det
