"""
Data Quality Dashboard for genealogy records.
Provides analytics on database integrity and OCR confidence.
"""
import os
import json
import logging
import requests
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class QualityMetrics:
    """Metrics for data quality analysis."""
    total_records: int = 0
    validated_records: int = 0
    avg_confidence: float = 0.0
    missing_dates: int = 0
    missing_names: int = 0
    quality_distribution: Dict[str, int] = field(
        default_factory=lambda: {"high": 0, "medium": 0, "low": 0}
    )
    validation_rate: float = 0.0

class QualityDashboard:
    """Analyzes and reports on the quality of the genealogy database."""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json"
        }
    
    def analyze_database(self) -> QualityMetrics:
        """Perform a comprehensive quality analysis of the database."""
        metrics = QualityMetrics()
        
        try:
            # 1. Total records and basic counts
            resp = requests.get(
                f"{self.supabase_url}/rest/v1/pessoas",
                headers=self.headers,
                params={"select": "id,nome,data_obito,qualidade,validado"},
                timeout=60
            )
            
            if resp.status_code != 200:
                logger.error(f"Error fetching records: {resp.status_code}")
                return metrics
                
            records = resp.json()
            metrics.total_records = len(records)
            
            if metrics.total_records == 0:
                return metrics
            
            sum_confidence = 0.0
            
            for r in records:
                # Confidência
                conf = r.get('qualidade', 0.0)
                sum_confidence += conf
                
                # Distribuição de qualidade
                if conf >= 0.8:
                    metrics.quality_distribution["high"] += 1
                elif conf >= 0.5:
                    metrics.quality_distribution["medium"] += 1
                else:
                    metrics.quality_distribution["low"] += 1
                
                # Validação
                if r.get('validado'):
                    metrics.validated_records += 1
                
                # Missings
                if not r.get('data_obito'):
                    metrics.missing_dates += 1
                if not r.get('nome'):
                    metrics.missing_names += 1
            
            metrics.avg_confidence = sum_confidence / metrics.total_records
            metrics.validation_rate = (metrics.validated_records / metrics.total_records) * 100
            
            return metrics
            
        except Exception as e:
            logger.error(f"Quality analysis error: {e}")
            return metrics
    
    def get_suspicious_records(self, min_confidence: float = 0.4) -> List[Dict]:
        """Find records that likely need human review."""
        try:
            resp = requests.get(
                f"{self.supabase_url}/rest/v1/pessoas",
                headers=self.headers,
                params={"qualidade": f"lt.{min_confidence}", "select": "*", "limit": 50},
                timeout=30
            )
            return resp.json() if resp.status_code == 200 else []
        except Exception as e:
            logger.error(f"Error fetching suspicious records: {e}")
            return []
    
    def generate_report(self, metrics: QualityMetrics) -> str:
        """Generate a human-readable quality report."""
        report = f"""
==================================================
RELATÓRIO DE QUALIDADE DE DADOS - {datetime.now().strftime('%Y-%m-%d')}
==================================================

Métricas Gerais:
- Total de Registos: {metrics.total_records}
- Taxa de Validação: {metrics.validation_rate:.1f}% ({metrics.validated_records} registos)
- Confiança Média: {metrics.avg_confidence:.2f}

Distribuição de Qualidade:
- Alta (>= 0.8): {metrics.quality_distribution['high']}
- Média (0.5 - 0.8): {metrics.quality_distribution['medium']}
- Baixa (< 0.5): {metrics.quality_distribution['low']}

Integridade de Dados:
- Registos sem data: {metrics.missing_dates}
- Registos sem nome: {metrics.missing_names}

Conclusão:
{"✅ Base de dados saudável" if metrics.avg_confidence > 0.7 else "⚠️ Base de dados requer revisão"}
==================================================
"""
        return report

if __name__ == "__main__":
    import os
    url = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_KEY', '')
    if url and key:
        dashboard = QualityDashboard(url, key)
        metrics = dashboard.analyze_database()
        print(dashboard.generate_report(metrics))
    else:
        print("Supabase credentials not configured")
