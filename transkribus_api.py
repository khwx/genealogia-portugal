"""
Transkribus API integration for handwritten text recognition.
Transcribes images of historical records.
"""
import requests
import json
import os
import time
from datetime import datetime

import config

# Transkribus API credentials (replace with your own)
TRANSKRIBUS_API_KEY = os.getenv("TRANSKRIBUS_API_KEY", "")
TRANSKRIBUS_USERNAME = os.getenv("TRANSKRIBUS_USERNAME", "")
TRANSKRIBUS_PASSWORD = os.getenv("TRANSKRIBUS_PASSWORD", "")

# API endpoints
TRANSKRIBUS_BASE_URL = "https://api.transkribus.eu/TrpServer/rest"
LOGIN_URL = f"{TRANSKRIBUS_BASE_URL}/auth/login"
COLLECTIONS_URL = f"{TRANSKRIBUS_BASE_URL}/collections"
DOCUMENTS_URL = f"{TRANSKRIBUS_BASE_URL}/documents"

class TranskribusAPI:
    def __init__(self):
        self.session = requests.Session()
        self.access_token = None
        self.user_id = None
        
    def login(self):
        """Login to Transkribus."""
        if not TRANSKRIBUS_API_KEY or not TRANSKRIBUS_USERNAME or not TRANSKRIBUS_PASSWORD:
            print("Transkribus credentials not set. Skipping login.")
            return False
            
        print("Logging into Transkribus...")
        
        data = {
            "key": TRANSKRIBUS_API_KEY,
            "username": TRANSKRIBUS_USERNAME,
            "password": TRANSKRIBUS_PASSWORD,
        }
        
        try:
            resp = self.session.post(LOGIN_URL, json=data)
            if resp.status_code == 200:
                result = resp.json()
                self.access_token = result["token"]
                self.user_id = result["userId"]
                self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})
                print("  Login successful")
                return True
            else:
                print(f"  Login failed: {resp.status_code}")
                return False
        except Exception as e:
            print(f"  Error during login: {e}")
            return False
    
    def get_collections(self):
        """Get user's collections."""
        if not self.access_token:
            print("Not authenticated. Skipping collections.")
            return []
        
        print("Getting collections...")
        
        try:
            resp = self.session.get(COLLECTIONS_URL)
            if resp.status_code == 200:
                result = resp.json()
                collections = result.get("collections", [])
                print(f"  Found {len(collections)} collections")
                return collections
            else:
                print(f"  Failed to get collections: {resp.status_code}")
                return []
        except Exception as e:
            print(f"  Error getting collections: {e}")
            return []
    
    def create_collection(self, name, description=""):
        """Create a new collection."""
        if not self.access_token:
            print("Not authenticated. Skipping collection creation.")
            return None
        
        print(f"Creating collection: {name}")
        
        data = {
            "name": name,
            "description": description,
            "isPublic": False,
        }
        
        try:
            resp = self.session.post(COLLECTIONS_URL, json=data)
            if resp.status_code == 200:
                result = resp.json()
                collection_id = result["id"]
                print(f"  Collection created: {collection_id}")
                return collection_id
            else:
                print(f"  Failed to create collection: {resp.status_code}")
                return None
        except Exception as e:
            print(f"  Error creating collection: {e}")
            return None
    
    def upload_document(self, collection_id, file_path, title=""):
        """Upload a document to a collection."""
        if not self.access_token:
            print("Not authenticated. Skipping upload.")
            return None
        
        print(f"Uploading document: {file_path}")
        
        files = {
            "file": open(file_path, "rb"),
        }
        
        data = {
            "title": title or os.path.basename(file_path),
            "collectionId": collection_id,
        }
        
        try:
            resp = self.session.post(DOCUMENTS_URL, files=files, data=data)
            if resp.status_code == 200:
                result = resp.json()
                document_id = result["id"]
                print(f"  Document uploaded: {document_id}")
                return document_id
            else:
                print(f"  Failed to upload document: {resp.status_code}")
                return None
        except Exception as e:
            print(f"  Error uploading document: {e}")
            return None
    
    def transcribe_document(self, document_id, model_id=None):
        """Transcribe a document."""
        if not self.access_token:
            print("Not authenticated. Skipping transcription.")
            return None
        
        print(f"Transcribing document: {document_id}")
        
        transcription_url = f"{DOCUMENTS_URL}/{document_id}/read"
        
        data = {
            "modelId": model_id or "portuguese-historical",
        }
        
        try:
            resp = self.session.post(transcription_url, json=data)
            if resp.status_code == 200:
                result = resp.json()
                print(f"  Transcription started")
                return result["id"]  # transcriptionId
            else:
                print(f"  Failed to start transcription: {resp.status_code}")
                return None
        except Exception as e:
            print(f"  Error starting transcription: {e}")
            return None
    
    def get_transcription_status(self, transcription_id):
        """Get transcription status."""
        if not self.access_token:
            print("Not authenticated. Skipping status check.")
            return None
        
        print(f"Checking transcription status: {transcription_id}")
        
        status_url = f"{TRANSKRIBUS_BASE_URL}/transcriptions/{transcription_id}"
        
        try:
            resp = self.session.get(status_url)
            if resp.status_code == 200:
                result = resp.json()
                return result
            else:
                print(f"  Failed to get status: {resp.status_code}")
                return None
        except Exception as e:
            print(f"  Error getting status: {e}")
            return None
    
    def get_transcription_result(self, transcription_id):
        """Get transcription result."""
        if not self.access_token:
            print("Not authenticated. Skipping result.")
            return None
        
        print(f"Getting transcription result: {transcription_id}")
        
        result_url = f"{TRANSKRIBUS_BASE_URL}/transcriptions/{transcription_id}/text"
        
        try:
            resp = self.session.get(result_url)
            if resp.status_code == 200:
                result = resp.json()
                return result["text"]
            else:
                print(f"  Failed to get result: {resp.status_code}")
                return None
        except Exception as e:
            print(f"  Error getting result: {e}")
            return None
    
    def process_images_in_directory(self, directory, model_id=None):
        """Process all images in a directory."""
        if not self.access_token:
            print("Not authenticated. Skipping directory processing.")
            return []
        
        print(f"Processing images in directory: {directory}")
        
        # Create collection
        collection_name = f"Celorico_da_Beira_Obitos_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        collection_id = self.create_collection(collection_name, "Genealogy records from Celorico da Beira")
        
        if not collection_id:
            return []
        
        results = []
        
        # Process each image
        for filename in os.listdir(directory):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')):
                file_path = os.path.join(directory, filename)
                
                # Upload document
                document_id = self.upload_document(collection_id, file_path, filename)
                
                if document_id:
                    # Transcribe document
                    transcription_id = self.transcribe_document(document_id, model_id)
                    
                    if transcription_id:
                        # Wait for transcription to complete
                        status = None
                        for _ in range(10):  # Try up to 10 times
                            status = self.get_transcription_status(transcription_id)
                            if status and status.get("status") == "FINISHED":
                                break
                            time.sleep(30)  # Wait 30 seconds
                        
                        if status and status.get("status") == "FINISHED":
                            # Get transcription result
                            text = self.get_transcription_result(transcription_id)
                            results.append({
                                "filename": filename,
                                "document_id": document_id,
                                "transcription_id": transcription_id,
                                "text": text,
                            })
                            print(f"  Processed: {filename}")
                        else:
                            print(f"  Transcription not finished for: {filename}")
                    else:
                        print(f"  Failed to start transcription for: {filename}")
                else:
                    print(f"  Failed to upload: {filename}")
                
                # Rate limiting
                time.sleep(5)
        
        return results


def process_obitos_images_with_transkribus():
    """Process all obitos images with Transkribus."""
    api = TranskribusAPI()
    
    if not api.login():
        return []
    
    # Get Portuguese historical model ID
    # For simplicity, we'll assume a model ID is known
    # In practice, you'd need to query available models
    model_id = "portuguese-historical"  # Replace with actual model ID
    
    # Process images
    results = api.process_images_in_directory(
        config.IMAGES_DIR,
        model_id=model_id
    )
    
    return results


if __name__ == "__main__":
    # Test with a single image
    api = TranskribusAPI()
    
    if api.login():
        # Create collection
        collection_name = f"Test_Collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        collection_id = api.create_collection(collection_name, "Test collection")
        
        if collection_id:
            # Upload a test image (you'd need to provide an image path)
            test_image_path = "test_image.jpg"  # Replace with actual path
            
            if os.path.exists(test_image_path):
                document_id = api.upload_document(collection_id, test_image_path, "Test Image")
                
                if document_id:
                    transcription_id = api.transcribe_document(document_id)
                    
                    if transcription_id:
                        # Wait and get result
                        time.sleep(60)  # Wait 1 minute
                        text = api.get_transcription_result(transcription_id)
                        if text:
                            print(f"Transcription result: {text[:500]}...")
                        else:
                            print("No transcription result returned")
                    else:
                        print("Failed to start transcription")
                else:
                    print("Failed to upload document")
            else:
                print(f"Test image not found: {test_image_path}")
        else:
            print("Failed to create collection")
    else:
        print("Failed to login to Transkribus")
