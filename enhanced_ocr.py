"""
Enhanced OCR processor with post-processing, validation, and correction.
Implements quality control for Portuguese historical documents.
"""
import re
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OCRValidator:
    """Validates and corrects OCR results for Portuguese historical documents."""
    
    def __init__(self):
        # Common OCR errors in Portuguese documents
        self.ocr_corrections = {
            # Character replacements
            'ó': 'o', 'ò': 'o', 'ô': 'o', 'õ': 'o',
            'á': 'a', 'à': 'a', 'â': 'a', 'ã': 'a',
            'é': 'e', 'è': 'e', 'ê': 'e',
            'í': 'i', 'ì': 'i', 'î': 'i',
            'ú': 'u', 'ù': 'u', 'û': 'u',
            'ç': 'c', 'ñ': 'n',
            # Common OCR mistakes
            'rn': 'm', 'cl': 'd', 'vv': 'w',
            '«': '"', '»': '"', '``': '"', "''": '"',
            '—': '-', '–': '-', '―': '-',
            'º': 'o', 'ª': 'a',
            # Numbers
            '0': '0', 'O': '0', 'o': '0',
            '1': '1', 'l': '1', 'I': '1',
            '2': '2', 'Z': '2', 'z': '2',
            '5': '5', 'S': '5', 's': '5',
            '6': '6', 'G': '6', 'g': '6',
            '8': '8', 'B': '8', 'b': '8',
        }
        
        # Portuguese common names and surnames for validation
        self.common_surnames = {
            'silva', 'santos', 'pereira', 'costa', 'rodrigues',
            'martins', 'oliveira', 'ferreira', 'gomes', 'carvalho',
            'almeida', 'pinto', 'dias', 'moura', 'teixeira',
            'neto', 'fernandes', 'ramos', 'henriques', 'lima'
        }
        
        self.common_given_names = {
            'joao', 'jose', 'manuel', 'antonio', 'francisco',
            'carlos', 'fernando', 'luis', 'miguel', 'pedro',
            'ana', 'maria', 'isabel', 'catarina', 'teresa',
            'madalena', 'antonia', 'luisa', 'helena', 'ines'
        }

    def correct_text(self, text: str) -> str:
        """Apply OCR corrections to text."""
        if not text:
            return text
            
        # Apply character corrections
        for wrong, correct in self.ocr_corrections.items():
            text = text.replace(wrong, correct)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def validate_name(self, name: str) -> Tuple[bool, str]:
        """Validate and clean Portuguese names."""
        if not name or len(name.strip()) < 2:
            return False, ""
        
        # Clean the name
        name = self.correct_text(name)
        name = re.sub(r'[^a-zA-Z\s\-\.]', '', name).strip()
        
        # Split into parts
        parts = name.split()
        
        # Basic validation: should have at least name and surname
        if len(parts) < 2:
            return False, name
        
        # Check for common valid patterns
        if len(parts) >= 2:
            # Check if first part looks like a given name
            first_part = parts[0].lower()
            if (first_part in self.common_given_names or 
                len(first_part) >= 3):
                return True, name
        
        return True, name  # Accept if we can't definitively validate

    def validate_date(self, date_str: str) -> Tuple[bool, Optional[str]]:
        """Validate and normalize Portuguese dates."""
        if not date_str or not date_str.strip():
            return False, None
        
        date_str = self.correct_text(date_str)
        
        # Try different date formats
        patterns = [
            # DD de Mês de AAAA
            (r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})', 
             lambda m: f"{m.group(3)}-{self.month_to_number(m.group(2))}-{int(m.group(1)):02d}"),
            # DD/MM/AAAA
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', 
             lambda m: f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"),
            # AAAA-MM-DD
            (r'(\d{4})-(\d{2})-(\d{2})', 
             lambda m: f"{m.group(1)}-{m.group(2)}-{m.group(3)}"),
            # AAAA
            (r'(\d{4})', 
             lambda m: f"{m.group(1)}-01-01"),  # Default to January 1st
        ]
        
        for pattern, formatter in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    formatted_date = formatter(match)
                    # Validate the date is reasonable
                    year = int(formatted_date[:4])
                    if 1500 <= year <= 2025:  # Reasonable range for historical documents
                        return True, formatted_date
                    else:
                        return False, None
                except:
                    continue
        
        return False, None

    def month_to_number(self, month_name: str) -> str:
        """Convert Portuguese month name to number."""
        months = {
            "janeiro": "01", "jan": "01",
            "fevereiro": "02", "fev": "02",
            "março": "03", "marco": "03", "mar": "03",
            "abril": "04", "abr": "04",
            "maio": "05", "mai": "05",
            "junho": "06", "jun": "06",
            "julho": "07", "jul": "07",
            "agosto": "08", "ago": "08",
            "setembro": "09", "set": "09",
            "outubro": "10", "out": "10",
            "novembro": "11", "nov": "11",
            "dezembro": "12", "dez": "12",
        }
        return months.get(month_name.lower(), "01")

    def extract_and_validate_records(self, ocr_text: str) -> List[Dict]:
        """Extract and validate records from OCR text."""
        if not ocr_text:
            return []
        
        records = []
        lines = ocr_text.split('\n')
        
        # Pattern to match typical death record entries
        patterns = [
            # Number + Name + Date
            (r'^(\d+)\s+([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(faleceu\s+a|em)\s+(.+)$', 
             lambda m: {'numero': m.group(1), 'nome': m.group(2), 'evento': m.group(3), 'data': m.group(4)}),
            # Name + Date (more flexible)
            (r'^([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:faleceu\s+a|em)\s+(.+)$', 
             lambda m: {'nome': m.group(1), 'data': m.group(2)}),
            # Simple name + date
            (r'^([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})$', 
             lambda m: {'nome': m.group(1), 'data': m.group(2)}),
        ]
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            # Try each pattern
            matched = False
            for pattern, extractor in patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    try:
                        record = extractor(match)
                        
                        # Validate and clean the record
                        if 'nome' in record:
                            valid_name, clean_name = self.validate_name(record['nome'])
                            if valid_name:
                                record['nome'] = clean_name
                                
                                # Validate date if present
                                if 'data' in record:
                                    valid_date, clean_date = self.validate_date(record['data'])
                                    if valid_date:
                                        record['data_obito'] = clean_date
                                        record['fonte'] = f"OCR linha {line_num}"
                                        
                                        # Calculate year
                                        if clean_date:
                                            year = int(clean_date[:4])
                                            record['ano'] = year
                                        
                                        records.append(record)
                                        matched = True
                                        break
                                    else:
                                        logger.warning(f"Invalid date on line {line_num}: {record['data']}")
                        else:
                            logger.warning(f"No name found on line {line_num}: {line}")
                            
                    except Exception as e:
                        logger.error(f"Error processing line {line_num}: {e}")
                        continue
            
            if not matched and line:
                logger.debug(f"Line {line_num} did not match any pattern: {line}")
        
        return records

    def get_quality_score(self, record: Dict) -> float:
        """Calculate quality score for a record (0-1)."""
        score = 1.0
        
        # Name quality
        if 'nome' in record:
            name = record['nome']
            if len(name.split()) >= 2:
                score += 0.1
            if any(surname in name.lower() for surname in self.common_surnames):
                score += 0.1
        
        # Date quality
        if 'data_obito' in record:
            score += 0.2
            # Check if date is in expected range
            try:
                year = int(record['data_obito'][:4])
                if 1650 <= year <= 2020:
                    score += 0.1
            except:
                pass
        
        # Record number
        if 'numero' in record:
            score += 0.1
        
        return min(score, 1.0)

    def enhance_ocr_results(self, ocr_text: str, min_quality: float = 0.5) -> List[Dict]:
        """Extract and validate records with quality filtering."""
        records = self.extract_and_validate_records(ocr_text)
        
        # Add quality scores and filter by minimum quality
        enhanced_records = []
        for record in records:
            record['qualidade'] = self.get_quality_score(record)
            if record['qualidade'] >= min_quality:
                enhanced_records.append(record)
        
        # Sort by quality
        enhanced_records.sort(key=lambda x: x['qualidade'], reverse=True)
        
        return enhanced_records


def test_ocr_validator():
    """Test the OCR validator with sample text."""
    validator = OCRValidator()
    
    # Test text with common OCR errors
    test_text = """
    1 João da Silva faleceu a 15 de Janeiro de 1864
    2 Maria José Ferreira faleceu em 22/03/1864
    3 António Rodrigues faleceu a 5 de Junho de 1864
    4 Ana Costa faleceu a 10 de Ag0sto de 1864
    5 Manuei Pereira faleceu em 1865
    """
    
    print("=== Teste OCR Validator ===")
    records = validator.enhance_ocr_results(test_text)
    
    print(f"\n✅ {len(records)} registos extraídos (qualidade >= 0.5):")
    for i, record in enumerate(records, 1):
        print(f"  {i}. {record}")
        print(f"     Qualidade: {record['qualidade']:.2f}")
    
    return records


if __name__ == "__main__":
    test_ocr_validator()