"""
Teste de OCR com Google Vision API para registos antigos.
"""
import requests
import json
import base64
import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_VISION_API_KEY = os.getenv("GOOGLE_VISION_API_KEY")

def test_google_vision_ocr(image_path):
    """Testa OCR com Google Vision API."""
    print(f"=== TESTE GOOGLE VISION API ===")
    print(f"Imagem: {image_path}")
    
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
    print("Enviando para Google Vision...")
    resp = requests.post(url, json=payload)
    
    if resp.status_code == 200:
        result = resp.json()
        
        if "responses" in result and result["responses"]:
            detections = result["responses"][0].get("textAnnotations", [])
            
            if detections:
                print(f"\n✅ Texto encontrado!")
                print(f"{'='*60}")
                
                # Primeiro resultado é o texto completo
                full_text = detections[0].get("description", "")
                print(full_text)
                print(f"{'='*60}")
                
                # Detalhes por palavra
                print(f"\nDetalhes ({len(detections)-1} palavras):")
                for det in detections[1:]:  # Skip first (full text)
                    word = det.get("description", "")
                    confidence = det.get("confidence", 0)
                    print(f"  '{word}' (confiança: {confidence:.2f})")
                
                return full_text
            else:
                print("❌ Nenhum texto encontrado na imagem")
                return None
        else:
            print(f"❌ Resposta inválida: {result}")
            return None
    else:
        print(f"❌ Erro HTTP {resp.status_code}: {resp.text[:500]}")
        return None


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        print("Uso: python test_google_vision.py <caminho_para_imagem>")
        print("Ou descarrega uma imagem de exemplo do digitarq.arquivos.pt")
        sys.exit(1)
    
    if os.path.exists(image_path):
        test_google_vision_ocr(image_path)
    else:
        print(f"Imagem não encontrada: {image_path}")
