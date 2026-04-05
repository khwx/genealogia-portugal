"""
Processamento OCR de imagens de registos de óbitos.
Usa Tesseract para extrair texto de imagens digitalizadas.
"""
import os
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import glob

import config


def preprocess_image(image_path):
    """
    Pré-processa a imagem para melhorar o OCR.
    """
    img = Image.open(image_path)

    # Converter para escala de cinza
    img = img.convert("L")

    # Aumentar contraste
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)

    # Aumentar brilho
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(1.2)

    # Aplicar filtro de nitidez
    img = img.filter(ImageFilter.SHARPEN)

    # Binarização simples
    threshold = 128
    img = img.point(lambda x: 0 if x < threshold else 255, "1")

    return img


def extract_text_from_image(image_path, lang=config.OCR_LANGUAGE):
    """
    Extrai texto de uma imagem usando Tesseract OCR.
    """
    try:
        img = preprocess_image(image_path)

        # Configuração do Tesseract para português
        custom_config = f"--oem 3 --psm 6 -l {lang}"
        text = pytesseract.image_to_string(img, config=custom_config)

        return text.strip()
    except Exception as e:
        print(f"  Erro ao processar {image_path}: {e}")
        return ""


def extract_text_with_confidence(image_path, lang=config.OCR_LANGUAGE):
    """
    Extrai texto com informações de confiança por linha.
    """
    try:
        img = preprocess_image(image_path)

        # Obter dados detalhados
        data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)

        lines = []
        current_line = ""
        current_conf = []

        for i in range(len(data["text"])):
            if data["text"][i].strip():
                if data["block_num"][i] != (data["block_num"][i-1] if i > 0 else -1) or \
                   data["line_num"][i] != (data["line_num"][i-1] if i > 0 else -1):
                    if current_line:
                        avg_conf = sum(current_conf) / len(current_conf) if current_conf else 0
                        lines.append({
                            "text": current_line.strip(),
                            "confidence": avg_conf,
                        })
                    current_line = ""
                    current_conf = []

                current_line += data["text"][i] + " "
                current_conf.append(data["conf"][i])

        # Última linha
        if current_line:
            avg_conf = sum(current_conf) / len(current_conf) if current_conf else 0
            lines.append({
                "text": current_line.strip(),
                "confidence": avg_conf,
            })

        return lines
    except Exception as e:
        print(f"  Erro ao processar {image_path}: {e}")
        return []


def process_all_images(images_dir=None):
    """
    Processa todas as imagens num diretório.
    """
    if images_dir is None:
        images_dir = config.IMAGES_DIR

    if not os.path.exists(images_dir):
        print(f"Diretório de imagens não encontrado: {images_dir}")
        return []

    results = []
    image_files = sorted(glob.glob(os.path.join(images_dir, "*.png")) +
                         glob.glob(os.path.join(images_dir, "*.jpg")) +
                         glob.glob(os.path.join(images_dir, "*.jpeg")) +
                         glob.glob(os.path.join(images_dir, "*.tiff")) +
                         glob.glob(os.path.join(images_dir, "*.bmp")))

    print(f"Encontradas {len(image_files)} imagens para processar")

    for i, image_path in enumerate(image_files):
        print(f"  Processando imagem {i+1}/{len(image_files)}: {os.path.basename(image_path)}")

        text = extract_text_from_image(image_path)

        # Guardar texto extraído
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        text_file = os.path.join(config.TEXT_DIR, f"{base_name}.txt")
        os.makedirs(config.TEXT_DIR, exist_ok=True)
        with open(text_file, "w", encoding="utf-8") as f:
            f.write(text)

        results.append({
            "image": image_path,
            "text_file": text_file,
            "text": text,
        })

    return results


if __name__ == "__main__":
    results = process_all_images()
    print(f"\nTotal de imagens processadas: {len(results)}")
