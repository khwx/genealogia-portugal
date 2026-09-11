"""
Script para processar imagens com olmOCR no Google Colab
Execute este código num notebook do Colab com GPU ativada
"""

# Instalar dependências no Colab
"""
!pip install transformers accelerate pillow torch
!pip install git+https://github.com/allenai/olmocr.git  # se disponível
"""

from transformers import AutoProcessor, AutoModelForVision2Seq
from PIL import Image
import torch
import os
import glob
import json

# Carregar modelo olmOCR
model_name = "allenai/olmOCR-7B-0225-preview"
print(f"Carregando modelo: {model_name}")

# Usar quantização 4-bit para poupar memória (opcional)
try:
    from transformers import BitsAndBytesConfig
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16
    )
    model = AutoModelForVision2Seq.from_pretrained(
        model_name,
        quantization_config=quantization_config,
        device_map="auto",
        torch_dtype=torch.float16
    )
except:
    # Fallback para carregamento normal
    model = AutoModelForVision2Seq.from_pretrained(
        model_name,
        device_map="auto",
        torch_dtype=torch.float16
    )

processor = AutoProcessor.from_pretrained(model_name)

def process_image_olmocr(image_path):
    """Processa uma imagem com olmOCR e extrai texto estruturado"""
    try:
        image = Image.open(image_path).convert("RGB")
        
        # Prompt para extração de certidões de óbito
        prompt = """Extract all information from this Portuguese death certificate. 
        Return JSON with fields: nome, data_obito, idade, sexo, estado_civil, 
        causa_morte, local_obito, residencia, numero_assento"""
        
        inputs = processor(images=image, text=prompt, return_tensors="pt").to(model.device)
        
        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=512)
        
        result = processor.batch_decode(outputs, skip_special_tokens=True)[0]
        return result
    except Exception as e:
        return f"Erro: {str(e)}"

# Exemplo de uso
if __name__ == "__main__":
    images_dir = "/content/full_images"  # Ajustar para o Colab
    output_dir = "/content/ocr_results"
    os.makedirs(output_dir, exist_ok=True)
    
    image_files = glob.glob(os.path.join(images_dir, "*.png")) + \
                  glob.glob(os.path.join(images_dir, "*.tiff"))[:10]  # Testar com 10
    
    print(f"Processando {len(image_files)} imagens...")
    
    results = []
    for img_path in image_files:
        print(f"Processando: {os.path.basename(img_path)}")
        text = process_image_olmocr(img_path)
        results.append({
            "image": os.path.basename(img_path),
            "ocr_text": text
        })
    
    # Guardar resultados
    with open(os.path.join(output_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("Concluído! Resultados em:", output_dir)
