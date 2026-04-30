"""
Real-time progress monitoring system for genealogy processing.
Provides WebSocket-based live updates and status tracking.
"""
import os
import json
import time
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProcessingStatus(Enum):
    """Processing job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class JobProgress:
    """Progress information for a single job."""
    job_id: str
    job_type: str  # 'ocr', 'indexing', 'upload', etc.
    status: str = "pending"
    current: int = 0
    total: int = 100
    message: str = ""
    percent: float = 0.0
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


@dataclass 
class SystemProgress:
    """Overall system progress."""
    total_jobs: int = 0
    pending_jobs: int = 0
    running_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    total_records: int = 0
    total_images: int = 0
    processed_images: int = 0
    start_time: Optional[str] = None
    last_update: Optional[str] = None
    estimated_completion: Optional[str] = None
    current_phase: str = "idle"


class ProgressEmitter:
    """Emits progress events to registered listeners."""
    
    def __init__(self):
        self.listeners: List[Callable] = []
        self.lock = threading.Lock()
    
    def subscribe(self, listener: Callable):
        """Subscribe a listener to progress updates."""
        with self.lock:
            self.listeners.append(listener)
            logger.info(f"Listener subscribed: {len(self.listeners)} total")
    
    def unsubscribe(self, listener: Callable):
        """Unsubscribe a listener."""
        with self.lock:
            if listener in self.listeners:
                self.listeners.remove(listener)
    
    def emit(self, event_type: str, data: Dict):
        """Emit an event to all listeners."""
        with self.lock:
            for listener in self.listeners:
                try:
                    listener(event_type, data)
                except Exception as e:
                    logger.error(f"Error in progress listener: {e}")


class RealTimeProgressMonitor:
    """Real-time progress monitoring with WebSocket support."""
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or os.environ.get('REDIS_URL')
        self.progress_file = 'progress_realtime.json'
        self.emitter = ProgressEmitter()
        self.jobs: Dict[str, JobProgress] = {}
        self.system_progress = SystemProgress()
        self.lock = threading.Lock()
        self._load_progress()
    
    def _load_progress(self):
        """Load persisted progress."""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.jobs = {k: JobProgress(**v) for k, v in data.get('jobs', {}).items()}
                    self.system_progress = SystemProgress(**data.get('system', {}))
            except Exception as e:
                logger.warning(f"Could not load progress: {e}")
    
    def _save_progress(self):
        """Persist progress to disk."""
        try:
            data = {
                'jobs': {k: asdict(v) for k, v in self.jobs.items()},
                'system': asdict(self.system_progress),
                'saved_at': datetime.now().isoformat()
            }
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Could not save progress: {e}")
    
    def _recalculate_system_progress(self):
        """Recalculate overall system progress."""
        self.system_progress.total_jobs = len(self.jobs)
        self.system_progress.pending_jobs = sum(
            1 for j in self.jobs.values() if j.status == "pending"
        )
        self.system_progress.running_jobs = sum(
            1 for j in self.jobs.values() if j.status == "running"
        )
        self.system_progress.completed_jobs = sum(
            1 for j in self.jobs.values() if j.status == "completed"
        )
        self.system_progress.failed_jobs = sum(
            1 for j in self.jobs.values() if j.status == "failed"
        )
        self.system_progress.last_update = datetime.now().isoformat()
        
        # Update current phase
        if self.system_progress.running_jobs > 0:
            running = [j for j in self.jobs.values() if j.status == "running"]
            if running:
                self.system_progress.current_phase = running[0].job_type
        else:
            self.system_progress.current_phase = "idle"
        
        # Estimate completion
        if self.system_progress.start_time and self.system_progress.processed_images > 0:
            from datetime import timedelta
            elapsed = datetime.now() - datetime.fromisoformat(self.system_progress.start_time)
            rate = self.system_progress.processed_images / elapsed.total_seconds()
            remaining = self.system_progress.total_images - self.system_progress.processed_images
            if rate > 0 and remaining > 0:
                eta_seconds = remaining / rate
                self.system_progress.estimated_completion = (
                    datetime.now() + timedelta(seconds=eta_seconds)
                ).isoformat()
        
        self._save_progress()
    
    def start_job(self, job_id: str, job_type: str, total: int = 100, metadata: Dict = None) -> JobProgress:
        """Start tracking a new job."""
        with self.lock:
            job = JobProgress(
                job_id=job_id,
                job_type=job_type,
                status="running",
                total=total,
                current=0,
                percent=0.0,
                started_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                metadata=metadata or {}
            )
            self.jobs[job_id] = job
            
            if not self.system_progress.start_time:
                self.system_progress.start_time = datetime.now().isoformat()
            
            self._recalculate_system_progress()
            self._emit_update('job_started', job)
            
            return job
    
    def update_job(self, job_id: str, current: int = None, message: str = None, 
                   metadata: Dict = None, error: str = None):
        """Update job progress."""
        with self.lock:
            if job_id not in self.jobs:
                logger.warning(f"Job {job_id} not found")
                return
            
            job = self.jobs[job_id]
            
            if current is not None:
                job.current = min(current, job.total)
                job.percent = (job.current / job.total * 100) if job.total > 0 else 0
            
            if message is not None:
                job.message = message
            
            if error is not None:
                job.error = error
                job.status = "failed"
            
            if metadata is not None:
                job.metadata.update(metadata)
            
            job.updated_at = datetime.now().isoformat()
            
            # Check if completed
            if job.current >= job.total and job.status == "running":
                job.status = "completed"
                job.completed_at = datetime.now().isoformat()
            
            self._recalculate_system_progress()
            self._emit_update('job_updated', job)
    
    def complete_job(self, job_id: str, success: bool = True, message: str = None):
        """Mark a job as completed."""
        with self.lock:
            if job_id not in self.jobs:
                return
            
            job = self.jobs[job_id]
            job.status = "completed" if success else "failed"
            job.completed_at = datetime.now().isoformat()
            
            if message:
                job.message = message
            
            self._recalculate_system_progress()
            self._emit_update('job_completed', job)
    
    def _emit_update(self, event_type: str, data: Dict):
        """Emit an update event."""
        self.emitter.emit(event_type, asdict(data))
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get status of a specific job."""
        with self.lock:
            if job_id in self.jobs:
                return asdict(self.jobs[job_id])
            return None
    
    def get_system_progress(self) -> Dict:
        """Get overall system progress."""
        with self.lock:
            return asdict(self.system_progress)
    
    def get_all_jobs(self, status: str = None) -> List[Dict]:
        """Get all jobs, optionally filtered by status."""
        with self.lock:
            jobs = list(self.jobs.values())
            if status:
                jobs = [j for j in jobs if j.status == status]
            return [asdict(j) for j in jobs]
    
    def cancel_job(self, job_id: str):
        """Cancel a running job."""
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id].status = "cancelled"
                self.jobs[job_id].completed_at = datetime.now().isoformat()
                self._recalculate_system_progress()
                self._emit_update('job_cancelled', self.jobs[job_id])
    
    def subscribe(self, listener: Callable):
        """Subscribe to progress updates."""
        self.emitter.subscribe(listener)
    
    def unsubscribe(self, listener: Callable):
        """Unsubscribe from progress updates."""
        self.emitter.unsubscribe(listener)


class WebSocketProgressServer:
    """WebSocket server for real-time progress updates."""
    
    def __init__(self, monitor: RealTimeProgressMonitor, port: int = 8765):
        self.monitor = monitor
        self.port = port
        self.clients = []
        self.server = None
        self.running = False
        self.lock = threading.Lock()
    
    def start(self):
        """Start the WebSocket server."""
        try:
            import websockets
            import asyncio
            
            self.running = True
            
            async def handle_client(websocket, path):
                client_id = str(hashlib.md5(str(time.time()).encode()).hexdigest()[:8])
                
                with self.lock:
                    self.clients.append(websocket)
                
                # Send initial state
                await websocket.send(json.dumps({
                    'type': 'initial_state',
                    'system': self.monitor.get_system_progress(),
                    'jobs': self.monitor.get_all_jobs()
                }))
                
                try:
                    async for message in websocket:
                        data = json.loads(message)
                        # Handle client messages
                        if data.get('action') == 'subscribe':
                            await websocket.send(json.dumps({
                                'type': 'subscribed'
                            }))
                        elif data.get('action') == 'get_jobs':
                            await websocket.send(json.dumps({
                                'type': 'jobs_list',
                                'jobs': self.monitor.get_all_jobs()
                            }))
                except Exception as e:
                    logger.error(f"WebSocket client error: {e}")
                finally:
                    with self.lock:
                        if websocket in self.clients:
                            self.clients.remove(websocket)
            
            async def broadcast_progress():
                while self.running:
                    system = self.monitor.get_system_progress()
                    for client in self.clients[:]:
                        try:
                            await client.send(json.dumps({
                                'type': 'progress_update',
                                'system': system
                            }))
                        except:
                            pass
                    await asyncio.sleep(1)
            
            async def main():
                async with websockets.serve(handle_client, '0.0.0.0', self.port) as ws:
                    await asyncio.gather(
                        ws.wait_closed(),
                        broadcast_progress()
                    )
            
            # Run in thread
            thread = threading.Thread(target=lambda: asyncio.run(main()))
            thread.daemon = True
            thread.start()
            
            logger.info(f"WebSocket server started on port {self.port}")
            
        except ImportError:
            logger.warning("websockets library not installed. WebSocket updates disabled.")
            logger.info("Install with: pip install websockets")
        except Exception as e:
            logger.error(f"Error starting WebSocket server: {e}")
    
    def stop(self):
        """Stop the WebSocket server."""
        self.running = False


def progress_listener(event_type: str, data: Dict):
    """Example progress listener callback."""
    print(f"[PROGRESS] {event_type}: Job {data.get('job_id')} - {data.get('percent', 0):.1f}% - {data.get('message', '')}")


def test_progress_monitor():
    """Test the progress monitoring system."""
    print("=== Teste Monitor de Progresso ===")
    
    monitor = RealTimeProgressMonitor()
    monitor.subscribe(progress_listener)
    
    # Simulate job processing
    job_id = "test_job_001"
    monitor.start_job(job_id, "ocr", total=100)
    
    # Simulate progress updates
    for i in range(0, 101, 10):
        monitor.update_job(job_id, current=i, message=f"Processing image {i}/100")
        time.sleep(0.1)
    
    monitor.complete_job(job_id, success=True, message="Job completed successfully")
    
    # Check final state
    print(f"\nSystem Progress: {monitor.get_system_progress()}")
    print(f"Job Status: {monitor.get_job_status(job_id)}")
    
    return monitor


if __name__ == "__main__":
    test_progress_monitor()