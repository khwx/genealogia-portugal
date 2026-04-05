"""
Configurações do projeto de extração de registos de óbitos.
"""
import os

# Diretórios
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
TEXT_DIR = os.path.join(OUTPUT_DIR, "text")
DB_PATH = os.path.join(OUTPUT_DIR, "obitos.db")

# URLs
TOMBO_URL = "https://tombo.pt/m/clb"
DIGITARQ_BASE = "https://digitarq.arquivos.pt"

# Paróquias de Celorico da Beira (freguesias)
# Formato: (código, nome)
PAROQUIAS = [
    ("clb01", "Açores"),
    ("clb02", "Aldeia da Serra"),
    ("clb03", "Baraçal"),
    ("clb04", "Cadafaz"),
    ("clb05", "Carrapichana"),
    ("clb06", "Casas do Rio"),
    ("clb27", "Casas do Soeiro"),
    ("clb19", "Celorico (Santa Maria)"),
    ("clb20", "Celorico (São Pedro)"),
    ("clb07", "Cortiçô da Serra"),
    ("clb08", "Forno Telheiro"),
    ("clb24", "Galisteu"),
    ("clb09", "Jejua"),
    ("clb10", "Lajeosa do Mondego"),
    ("clb11", "Linhares"),
    ("clb12", "Maçal do Chão"),
    ("clb13", "Mesquitela"),
    ("clb14", "Minhocal"),
    ("clb15", "Prados"),
    ("clb16", "Rapa"),
    ("clb17", "Ratoeira"),
    ("clb18", "Salgueirais"),
    ("clb25", "São Martinho de Celorico"),
    ("clb21", "Vale de Azares"),
    ("clb22", "Velosa"),
    ("clb23", "Vide Entre Vinhas"),
    ("clb26", "Vila Boa do Mondego"),
]

# Configurações de scraping
REQUEST_DELAY = 2  # segundos entre requests
REQUEST_TIMEOUT = 30  # segundos
MAX_RETRIES = 3
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Configurações de OCR
OCR_LANGUAGE = "por"  # Português
OCR_CONFIDENCE_THRESHOLD = 30

# Configurações de exportação
EXCEL_FILE = os.path.join(OUTPUT_DIR, "obitos.xlsx")
CSV_FILE = os.path.join(OUTPUT_DIR, "obitos.csv")
