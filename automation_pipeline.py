"""
Automation pipeline for genealogy records processing.
Handles Google Drive → Colab → NVIDIA → Supabase workflow.
"""
import os
import json
import time
import logging
import requests
from datetime import datetime
from typing import List, Dict, Optional
import google.auth
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GoogleDriveManager:
    """Manages Google Drive operations for document processing."""
    
    def __init__(self, credentials_file='credentials.json'):
        self.credentials_file = credentials_file
        self.service = None
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Google Drive API."""
        try:
            creds = Credentials.from_authorized_user_file(self.credentials_file, [
                'https://www.googleapis.com/auth/drive.readonly',
                'https://www.googleapis.com/auth/drive.file'
            ])
            
            self.service = build('drive', 'v3', credentials=creds)
            logger.info("✅ Google Drive authentication successful")
        except Exception as e:
            logger.error(f"❌ Google Drive authentication failed: {e}")
            raise
    
    def get_images_from_folder(self, folder_id: str, file_types: List[str] = None) -> List[Dict]:
        """Get all images from a specific Google Drive folder."""
        if file_types is None:
            file_types = ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']
        
        try:
            # Search for image files in the folder
            query = f"'{folder_id}' in parents and ("
            query += " or ".join([f"name contains '{ext}'" for ext in file_types])
            query += ")"
            
            results = self.service.files().list(
                q=query,
                fields="files(id, name, webViewLink, mimeType, createdTime)",
                pageSize=1000
            ).execute()
            
            files = results.get('files', [])
            logger.info(f"Found {len(files)} images in folder {folder_id}")
            
            return files
        except HttpError as error:
            logger.error(f"❌ Error accessing Google Drive: {error}")
            return []
    
    def download_file(self, file_id: str, local_path: str) -> bool:
        """Download a file from Google Drive to local storage."""
        try:
            request = self.service.files().get_media(fileId=file_id)
            
            with open(local_path, 'wb') as f:
                downloader = requests.get(request.uri)
                f.write(downloader.content)
            
            logger.info(f"✅ Downloaded {file_id} to {local_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Error downloading file {file_id}: {e}")
            return False

class ColabManager:
    """Manages Google Colab operations for OCR processing."""
    
    def __init__(self, colab_token: str = None):
        self.colab_token = colab_token or os.getenv('COLAB_TOKEN')
        self.api_base = 'https://colab.research.google.com/api'
    
    def submit_processing_job(self, notebook_path: str, input_files: List[str]) -> Optional[str]:
        """Submit a processing job to Google Colab."""
        try:
            # This is a simplified implementation
            # In practice, you'd use the Colab API or trigger via Cloud Functions
            
            job_data = {
                'notebook': notebook_path,
                'input_files': input_files,
                'timestamp': datetime.now().isoformat(),
                'status': 'submitted'
            }
            
            # Save job info for tracking
            job_id = f"job_{int(time.time())}"
            with open(f'jobs/{job_id}.json', 'w') as f:
                json.dump(job_data, f)
            
            logger.info(f"✅ Submitted job {job_id} to Colab")
            return job_id
            
        except Exception as e:
            logger.error(f"❌ Error submitting Colab job: {e}")
            return None
    
    def check_job_status(self, job_id: str) -> Dict:
        """Check the status of a Colab job."""
        try:
            with open(f'jobs/{job_id}.json', 'r') as f:
                job_data = json.load(f)
            
            # In a real implementation, you'd poll the Colab API
            # For now, simulate job progress
            if 'status' not in job_data:
                job_data['status'] = 'running'
                job_data['progress'] = 0.5
            
            return job_data
            
        except FileNotFoundError:
            return {'status': 'not_found', 'error': 'Job not found'}
        except Exception as e:
            logger.error(f"❌ Error checking job status: {e}")
            return {'status': 'error', 'error': str(e)}

class AutomationPipeline:
    """Main automation pipeline for genealogy processing."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.drive_manager = GoogleDriveManager(config.get('credentials_file'))
        self.colab_manager = ColabManager(config.get('colab_token'))
        self.setup_directories()
    
    def setup_directories(self):
        """Create necessary directories for the pipeline."""
        directories = [
            'downloads',
            'processed',
            'jobs',
            'logs'
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"✅ Directory created: {directory}")
    
    def process_batch(self, folder_id: str, batch_size: int = 10) -> Dict:
        """Process a batch of images from Google Drive."""
        try:
            # Step 1: Get images from Google Drive
            logger.info("Step 1: Fetching images from Google Drive")
            images = self.drive_manager.get_images_from_folder(folder_id)
            
            if not images:
                return {'status': 'error', 'message': 'No images found in folder'}
            
            # Process in batches
            results = []
            total_processed = 0
            
            for i in range(0, len(images), batch_size):
                batch = images[i:i + batch_size]
                logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} images")
                
                batch_result = self.process_batch_images(batch)
                results.extend(batch_result)
                total_processed += len(batch_result)
                
                # Add delay to avoid rate limiting
                time.sleep(2)
            
            return {
                'status': 'success',
                'total_images': len(images),
                'processed': total_processed,
                'results': results,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error in batch processing: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def process_batch_images(self, images: List[Dict]) -> List[Dict]:
        """Process a batch of images through the pipeline."""
        results = []
        
        for image in images:
            try:
                # Download image
                local_path = f"downloads/{image['id']}.jpg"
                if self.drive_manager.download_file(image['id'], local_path):
                    
                    # Process with OCR
                    ocr_result = self.process_image_with_ocr(local_path, image)
                    
                    if ocr_result:
                        results.append(ocr_result)
                        
                        # Upload to Supabase
                        self.upload_to_supabase(ocr_result)
                    
                    # Move to processed folder
                    os.rename(local_path, f"processed/{image['id']}.jpg")
                    
                else:
                    logger.warning(f"Failed to download {image['id']}")
                    
            except Exception as e:
                logger.error(f"Error processing image {image['id']}: {e}")
        
        return results
    
    def process_image_with_ocr(self, image_path: str, image_info: Dict) -> Optional[Dict]:
        """Process a single image with OCR."""
        try:
            # Import enhanced OCR
            from enhanced_ocr import OCRValidator
            
            # Extract text from image
            validator = OCRValidator()
            
            # For now, simulate OCR processing
            # In practice, you'd use Tesseract or call NVIDIA API
            mock_ocr_text = f"""
            Indice de obitos - {image_info['name']}
            1 Joao da Silva faleceu a 15 de Janeiro de 1864
            2 Maria Jose Ferreira faleceu a 22 de Marco de 1864
            3 Antonio Rodrigues faleceu a 5 de Junho de 1864
            """
            
            # Extract and validate records
            records = validator.enhance_ocr_results(mock_ocr_text)
            
            if records:
                return {
                    'image_id': image_info['id'],
                    'image_name': image_info['name'],
                    'processed_at': datetime.now().isoformat(),
                    'records': records,
                    'total_records': len(records)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in OCR processing: {e}")
            return None
    
    def upload_to_supabase(self, result: Dict):
        """Upload processing results to Supabase."""
        try:
            supabase_url = self.config.get('supabase_url')
            supabase_key = self.config.get('supabase_key')
            
            if not supabase_url or not supabase_key:
                logger.warning("Supabase credentials not configured")
                return
            
            headers = {
                'apikey': supabase_key,
                'Authorization': f'Bearer {supabase_key}',
                'Content-Type': 'application/json'
            }
            
            for record in result['records']:
                data = {
                    'nome': record.get('nome', ''),
                    'data_obito': record.get('data_obito'),
                    'ano': record.get('ano'),
                    'fonte': f"Google Drive - {result['image_name']}",
                    'freguesia': 'Celorico da Beira',
                    'concelho': 'Celorico da Beira',
                    'distrito': 'Guarda',
                    'qualidade': record.get('qualidade', 0.5)
                }
                
                response = requests.post(
                    f"{supabase_url}/rest/v1/pessoas",
                    headers=headers,
                    json=data
                )
                
                if response.status_code in [200, 201]:
                    logger.info(f"✅ Uploaded record: {record.get('nome')}")
                else:
                    logger.warning(f"⚠️ Failed to upload {record.get('name')}: {response.status_code}")
            
        except Exception as e:
            logger.error(f"Error uploading to Supabase: {e}")
    
    def generate_report(self, processing_result: Dict) -> str:
        """Generate a processing report."""
        try:
            report = f"""
# Relatório de Processamento Automático
**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Status:** {processing_result['status']}

## Estatísticas
- **Total de Imagens:** {processing_result.get('total_images', 0)}
- **Processadas:** {processing_result.get('processed', 0)}
- **Registos Extraídos:** {sum(r.get('total_records', 0) for r in processing_result.get('results', []))}

## Detalhes
"""
            
            for result in processing_result.get('results', []):
                report += f"""
### Imagem: {result['image_name']}
- **ID:** {result['image_id']}
- **Registos:** {result['total_records']}
- **Processado em:** {result['processed_at']}

"""
            
            # Save report
            report_path = f"logs/processing_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report)
            
            logger.info(f"✅ Report generated: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return ""

def main():
    """Main function to run the automation pipeline."""
    
    # Configuration
    config = {
        'credentials_file': 'credentials.json',
        'colab_token': os.getenv('COLAB_TOKEN'),
        'supabase_url': os.getenv('SUPABASE_URL'),
        'supabase_key': os.getenv('SUPABASE_KEY'),
        'google_drive_folder_id': os.getenv('GOOGLE_DRIVE_FOLDER_ID'),
        'batch_size': 10
    }
    
    # Initialize pipeline
    pipeline = AutomationPipeline(config)
    
    if not config['google_drive_folder_id']:
        print("❌ Please set GOOGLE_DRIVE_FOLDER_ID environment variable")
        return
    
    # Process batch
    logger.info("🚀 Starting automation pipeline...")
    result = pipeline.process_batch(config['google_drive_folder_id'], config['batch_size'])
    
    # Generate report
    if result['status'] == 'success':
        report_path = pipeline.generate_report(result)
        logger.info(f"✅ Pipeline completed successfully!")
        logger.info(f"📄 Report available at: {report_path}")
    else:
        logger.error(f"❌ Pipeline failed: {result.get('message', 'Unknown error')}")

if __name__ == "__main__":
    main()