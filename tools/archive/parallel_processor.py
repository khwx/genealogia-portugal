"""
Parallel processing optimizer for handling all 1,077 books.
Implements multiprocessing, batching strategies, and progress tracking.
"""
import os
import json
import time
import logging
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from multiprocessing import Pool, cpu_count, Manager
import multiprocessing as mp
import threading
import queue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class BookProcessingJob:
    """Represents a book processing job."""
    book_id: str
    freguesia: str
    titulo: str
    data_inicio: str
    data_fim: str
    pages: List[Dict] = field(default_factory=list)
    status: str = "pending"  # pending, processing, completed, failed
    processed_pages: int = 0
    total_pages: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    quality_score: float = 0.0

@dataclass
class ProcessingProgress:
    """Tracks overall processing progress."""
    total_books: int = 0
    completed_books: int = 0
    failed_books: int = 0
    total_pages: int = 0
    processed_pages: int = 0
    total_records: int = 0
    start_time: Optional[str] = None
    last_update: Optional[str] = None
    current_job: Optional[str] = None
    estimated_completion: Optional[str] = None
    jobs: Dict[str, BookProcessingJob] = field(default_factory=dict)

class ProgressTracker:
    """Tracks processing progress with real-time updates."""
    
    def __init__(self, progress_file: str = 'processing_progress.json'):
        self.progress_file = progress_file
        self.progress = ProcessingProgress()
        self.lock = threading.Lock()
        self._load_progress()
    
    def _load_progress(self):
        """Load progress from file."""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.progress = ProcessingProgress(**data)
            except Exception as e:
                logger.warning(f"Could not load progress: {e}")
    
    def _save_progress(self):
        """Save progress to file."""
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.progress.__dict__, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Could not save progress: {e}")
    
    def update(self, job_id: str, updates: Dict):
        """Update progress for a specific job."""
        with self.lock:
            if job_id in self.progress.jobs:
                job = self.progress.jobs[job_id]
                for key, value in updates.items():
                    if hasattr(job, key):
                        setattr(job, key, value)
                
                # Update timestamps
                self.progress.last_update = datetime.now().isoformat()
                
                # Recalculate totals
                self._recalculate_totals()
                
                # Estimate completion time
                self._estimate_completion()
                
                self._save_progress()
    
    def _recalculate_totals(self):
        """Recalculate total progress."""
        self.progress.completed_books = sum(
            1 for j in self.progress.jobs.values() 
            if j.status == 'completed'
        )
        self.progress.failed_books = sum(
            1 for j in self.progress.jobs.values() 
            if j.status == 'failed'
        )
        self.progress.processed_pages = sum(
            j.processed_pages for j in self.progress.jobs.values()
        )
    
    def _estimate_completion(self):
        """Estimate time to completion."""
        if self.progress.start_time and self.progress.processed_pages > 0:
            elapsed = datetime.now() - datetime.fromisoformat(self.progress.start_time)
            pages_per_second = self.progress.processed_pages / max(elapsed.total_seconds(), 1)
            
            remaining_pages = self.progress.total_pages - self.progress.processed_pages
            if pages_per_second > 0 and remaining_pages > 0:
                seconds_remaining = remaining_pages / pages_per_second
                self.progress.estimated_completion = (
                    datetime.now() + timedelta(seconds=seconds_remaining)
                ).isoformat()
    
    def add_job(self, job: BookProcessingJob):
        """Add a new job to track."""
        with self.lock:
            self.progress.jobs[job.book_id] = job
            if not self.progress.start_time:
                self.progress.start_time = datetime.now().isoformat()
            self.progress.total_books = len(self.progress.jobs)
            self._save_progress()
    
    def get_progress(self) -> Dict:
        """Get current progress as dictionary."""
        with self.lock:
            return {
                'total_books': self.progress.total_books,
                'completed_books': self.progress.completed_books,
                'failed_books': self.progress.failed_books,
                'total_pages': self.progress.total_pages,
                'processed_pages': self.progress.processed_pages,
                'total_records': self.progress.total_records,
                'percent_complete': (
                    self.progress.completed_books / max(self.progress.total_books, 1) * 100
                ),
                'current_job': self.progress.current_job,
                'estimated_completion': self.progress.estimated_completion,
                'last_update': self.progress.last_update
            }

class ParallelProcessor:
    """Handles parallel processing of books with multiple workers."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.max_workers = config.get('max_workers', cpu_count())
        self.batch_size = config.get('batch_size', 10)
        self.progress = ProgressTracker()
        self.results_queue = queue.Queue()
        self.stop_flag = threading.Event()
    
    def process_all_books(self, books: List[Dict]) -> Dict:
        """Process all books in parallel batches."""
        logger.info(f"Starting parallel processing of {len(books)} books")
        logger.info(f"Using {self.max_workers} workers")
        
        # Initialize jobs
        for book in books:
            job = BookProcessingJob(
                book_id=book.get('id', ''),
                freguesia=book.get('freguesia', ''),
                titulo=book.get('titulo', ''),
                data_inicio=book.get('data_inicio', ''),
                data_fim=book.get('data_fim', ''),
                total_pages=book.get('pages', 0)
            )
            self.progress.add_job(job)
        
        # Process in parallel batches
        results = []
        total_batches = (len(books) + self.batch_size - 1) // self.batch_size
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for batch_num in range(total_batches):
                batch_start = batch_num * self.batch_size
                batch_end = min(batch_start + self.batch_size, len(books))
                batch = books[batch_start:batch_end]
                
                logger.info(f"Processing batch {batch_num + 1}/{total_batches}")
                
                futures = {
                    executor.submit(self._process_single_book, book): book
                    for book in batch
                }
                
                for future in as_completed(futures):
                    book = futures[future]
                    try:
                        result = future.result()
                        results.append(result)
                        
                        # Update progress
                        self.progress.update(
                            book.get('id', ''),
                            {'status': 'completed', 'completed_at': datetime.now().isoformat()}
                        )
                        
                    except Exception as e:
                        logger.error(f"Error processing book {book.get('id')}: {e}")
                        self.progress.update(
                            book.get('id', ''),
                            {'status': 'failed', 'errors': [str(e)]}
                        )
        
        return {
            'status': 'success',
            'total_books': len(books),
            'results': results,
            'progress': self.progress.get_progress()
        }
    
    def _process_single_book(self, book: Dict) -> Dict:
        """Process a single book."""
        book_id = book.get('id', '')
        logger.info(f"Processing book: {book_id}")
        
        self.progress.update(book_id, {'status': 'processing', 'started_at': datetime.now().isoformat()})
        
        try:
            # Extract pages
            pages = self._extract_pages(book)
            
            # Process each page with OCR
            records = []
            for page in pages:
                page_records = self._process_page(page, book)
                records.extend(page_records)
                
                self.progress.update(book_id, {
                    'processed_pages': len(records)
                })
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(records)
            
            self.progress.update(book_id, {
                'status': 'completed',
                'completed_at': datetime.now().isoformat(),
                'quality_score': quality_score
            })
            
            return {
                'book_id': book_id,
                'records': records,
                'quality_score': quality_score,
                'pages_processed': len(pages)
            }
            
        except Exception as e:
            logger.error(f"Error in book processing: {e}")
            self.progress.update(book_id, {'status': 'failed', 'errors': [str(e)]})
            raise
    
    def _extract_pages(self, book: Dict) -> List[Dict]:
        """Extract page information from book."""
        # In a real implementation, this would fetch from Google Drive or local storage
        return book.get('pages', [])
    
    def _process_page(self, page: Dict, book: Dict) -> List[Dict]:
        """Process a single page with OCR."""
        # In a real implementation, this would use NVIDIA OCR or Tesseract
        # For now, simulate processing
        time.sleep(0.1)  # Simulate processing time
        
        return []
    
    def _calculate_quality_score(self, records: List[Dict]) -> float:
        """Calculate overall quality score for records."""
        if not records:
            return 0.0
        
        # Simple quality calculation
        total_quality = sum(r.get('qualidade', 0.5) for r in records)
        return total_quality / len(records)
    
    def stop(self):
        """Stop processing."""
        self.stop_flag.set()


class BookInventoryManager:
    """Manages the inventory of 1,077 books."""
    
    def __init__(self, inventory_file: str = 'output/obitos_inventario.json'):
        self.inventory_file = inventory_file
        self.books = []
        self._load_inventory()
    
    def _load_inventory(self):
        """Load book inventory from file."""
        if os.path.exists(self.inventory_file):
            try:
                with open(self.inventory_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and 'books' in data:
                        self.books = data['books']
                    elif isinstance(data, list):
                        self.books = data
            except Exception as e:
                logger.error(f"Could not load inventory: {e}")
                self.books = []
    
    def get_books_by_parish(self, freguesia: str) -> List[Dict]:
        """Get all books for a specific parish."""
        return [b for b in self.books if b.get('freguesia') == freguesia]
    
    def get_books_by_year_range(self, year_start: int, year_end: int) -> List[Dict]:
        """Get all books that overlap with a year range."""
        filtered = []
        for book in self.books:
            book_start = book.get('data_inicio', '')
            book_end = book.get('data_fim', '')
            
            # Simple year comparison
            try:
                bs = int(book_start[:4]) if book_start else 1500
                be = int(book_end[:4]) if book_end else 2025
                
                if bs <= year_end and be >= year_start:
                    filtered.append(book)
            except:
                continue
        
        return filtered
    
    def get_statistics(self) -> Dict:
        """Get inventory statistics."""
        parishes = set()
        year_min = 9999
        year_max = 0
        total_books = len(self.books)
        
        for book in self.books:
            parishes.add(book.get('freguesia', 'Unknown'))
            
            try:
                start = int(book.get('data_inicio', '1500')[:4])
                end = int(book.get('data_fim', '2025')[:4])
                year_min = min(year_min, start)
                year_max = max(year_max, end)
            except:
                continue
        
        return {
            'total_books': total_books,
            'total_parishes': len(parishes),
            'parishes': list(parishes),
            'year_range': (year_min, year_max),
            'books_by_parish': {
                p: len([b for b in self.books if b.get('freguesia') == p])
                for p in parishes
            }
        }


def process_book_worker(book_data: Dict) -> Dict:
    """Worker function for processing a single book in a separate process."""
    # This function runs in a separate process
    
    try:
        from enhanced_ocr import OCRValidator
        
        book_id = book_data.get('id', '')
        pages = book_data.get('pages', [])
        
        validator = OCRValidator()
        all_records = []
        
        for page in pages:
            # Simulate page processing
            ocr_text = f"""
            Pagina {page.get('page_num', 0)}
            1 Joao da Silva faleceu a 15 de Janeiro de 1864
            2 Maria Jose faleceu a 22 de Marco de 1864
            """
            
            records = validator.enhance_ocr_results(ocr_text)
            all_records.extend(records)
        
        return {
            'book_id': book_id,
            'records': all_records,
            'pages_processed': len(pages)
        }
        
    except Exception as e:
        return {
            'book_id': book_data.get('id', ''),
            'error': str(e),
            'records': []
        }


if __name__ == "__main__":
    # Test parallel processing
    print("=== Teste Processamento Paralelo ===")
    
    # Load inventory
    manager = BookInventoryManager()
    stats = manager.get_statistics()
    
    print(f"Total de livros: {stats['total_books']}")
    print(f"Total de freguesias: {stats['total_parishes']}")
    print(f"Intervalo de anos: {stats['year_range']}")
    
    # Test parallel processing with a small batch
    config = {
        'max_workers': 4,
        'batch_size': 10
    }
    
    processor = ParallelProcessor(config)
    
    # Process a small test batch
    test_books = [
        {
            'id': f'test_book_{i}',
            'freguesia': 'Celorico Santa Maria',
            'titulo': f'Livro de Óbitos {i}',
            'data_inicio': '1860-01-01',
            'data_fim': '1869-12-31',
            'pages': [{'page_num': j} for j in range(10)]
        }
        for i in range(3)
    ]
    
    print(f"\nProcessando {len(test_books)} livros de teste...")
    results = processor.process_all_books(test_books)
    
    print(f"\nProgresso: {results['progress']['percent_complete']:.1f}%")
    print(f"Concluídos: {results['progress']['completed_books']}")
    print(f"Falhas: {results['progress']['failed_books']}")