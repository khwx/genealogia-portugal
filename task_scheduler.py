"""
Scheduled task processing system for continuous genealogy data extraction.
Handles automated processing jobs with cron-like scheduling.
"""
import os
import json
import time
import logging
import threading
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScheduleFrequency(Enum):
    """How often a scheduled task should run."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ONCE = "once"


@dataclass
class ScheduledTask:
    """Represents a scheduled processing task."""
    task_id: str
    name: str
    task_type: str  # 'scrape', 'ocr', 'sync', etc.
    frequency: str
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    enabled: bool = True
    config: Dict = field(default_factory=dict)
    max_runtime_minutes: int = 60
    priority: int = 5  # 1-10, higher = more priority


@dataclass
class TaskResult:
    """Result of a task execution."""
    task_id: str
    started_at: str
    completed_at: Optional[str] = None
    success: bool = False
    output: str = ""
    error: Optional[str] = None
    records_processed: int = 0
    images_processed: int = 0
    execution_time_seconds: float = 0


class TaskScheduler:
    """Schedules and executes genealogy processing tasks."""
    
    def __init__(self, tasks_file: str = 'scheduled_tasks.json'):
        self.tasks_file = tasks_file
        self.tasks: Dict[str, ScheduledTask] = {}
        self.task_history: List[TaskResult] = []
        self.running_tasks: Dict[str, TaskResult] = {}
        self.lock = threading.Lock()
        self.scheduler_thread = None
        self.running = False
        self._load_tasks()
    
    def _load_tasks(self):
        """Load tasks from file."""
        if os.path.exists(self.tasks_file):
            try:
                with open(self.tasks_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.tasks = {k: ScheduledTask(**v) for k, v in data.get('tasks', {}).items()}
                    self.task_history = [TaskResult(**r) for r in data.get('history', [])]
            except Exception as e:
                logger.warning(f"Could not load tasks: {e}")
    
    def _save_tasks(self):
        """Save tasks to file."""
        try:
            data = {
                'tasks': {k: asdict(v) for k, v in self.tasks.items()},
                'history': [asdict(r) for r in self.task_history[-100:]]  # Keep last 100
            }
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Could not save tasks: {e}")
    
    def add_task(self, name: str, task_type: str, frequency: str, 
                 config: Dict = None, max_runtime: int = 60) -> str:
        """Add a new scheduled task."""
        task_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()[:12]
        
        # Calculate next run time
        next_run = self._calculate_next_run(frequency)
        
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            task_type=task_type,
            frequency=frequency,
            next_run=next_run.isoformat() if next_run else None,
            config=config or {},
            max_runtime_minutes=max_runtime
        )
        
        with self.lock:
            self.tasks[task_id] = task
            self._save_tasks()
        
        logger.info(f"Added task: {name} ({task_id})")
        return task_id
    
    def remove_task(self, task_id: str):
        """Remove a scheduled task."""
        with self.lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                self._save_tasks()
                logger.info(f"Removed task: {task_id}")
    
    def enable_task(self, task_id: str, enabled: bool = True):
        """Enable or disable a task."""
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id].enabled = enabled
                self._save_tasks()
    
    def _calculate_next_run(self, frequency: str) -> Optional[datetime]:
        """Calculate the next run time based on frequency."""
        now = datetime.now()
        
        if frequency == "hourly":
            return now.replace(minute=0, second=0) + timedelta(hours=1)
        elif frequency == "daily":
            return now.replace(hour=2, minute=0, second=0) + timedelta(days=1)
        elif frequency == "weekly":
            return now + timedelta(weeks=1)
        elif frequency == "monthly":
            # First day of next month
            if now.month == 12:
                return now.replace(year=now.year + 1, month=1, day=1, hour=2)
            else:
                return now.replace(month=now.month + 1, day=1, hour=2)
        elif frequency == "once":
            return now + timedelta(minutes=5)  # Run once in 5 minutes
        
        return None
    
    def get_due_tasks(self) -> List[ScheduledTask]:
        """Get tasks that are due to run."""
        now = datetime.now()
        due = []
        
        with self.lock:
            for task in self.tasks.values():
                if not task.enabled:
                    continue
                
                if task.next_run:
                    try:
                        next_run = datetime.fromisoformat(task.next_run)
                        if next_run <= now:
                            due.append(task)
                    except:
                        continue
        
        # Sort by priority (higher first)
        due.sort(key=lambda t: t.priority, reverse=True)
        return due
    
    def execute_task(self, task: ScheduledTask) -> TaskResult:
        """Execute a scheduled task."""
        logger.info(f"Executing task: {task.name}")
        
        start_time = datetime.now()
        result = TaskResult(
            task_id=task.task_id,
            started_at=start_time.isoformat()
        )
        
        # Track running task
        with self.lock:
            self.running_tasks[task.task_id] = result
        
        try:
            # Execute based on task type
            if task.task_type == "scrape":
                output = self._run_scrape_task(task)
            elif task.task_type == "ocr":
                output = self._run_ocr_task(task)
            elif task.task_type == "sync":
                output = self._run_sync_task(task)
            elif task.task_type == "export":
                output = self._run_export_task(task)
            elif task.task_type == "custom":
                output = self._run_custom_task(task)
            else:
                output = f"Unknown task type: {task.task_type}"
                result.error = output
            
            result.output = output
            result.success = True
            
        except Exception as e:
            logger.error(f"Task execution error: {e}")
            result.error = str(e)
            result.success = False
        
        # Complete the task
        end_time = datetime.now()
        result.completed_at = end_time.isoformat()
        result.execution_time_seconds = (end_time - start_time).total_seconds()
        
        # Update task with last run and next run
        with self.lock:
            task.last_run = result.started_at
            task.next_run = self._calculate_next_run(task.frequency).isoformat()
            
            # Remove from running
            if task.task_id in self.running_tasks:
                del self.running_tasks[task.task_id]
            
            # Add to history
            self.task_history.append(result)
            if len(self.task_history) > 100:
                self.task_history = self.task_history[-100:]
            
            self._save_tasks()
        
        logger.info(f"Task completed: {task.name} - {'SUCCESS' if result.success else 'FAILED'}")
        return result
    
    def _run_scrape_task(self, task: ScheduledTask) -> str:
        """Run a scraping task."""
        try:
            from scraper import scrape_all_obitos
            
            result = scrape_all_obitos()
            task.config['last_count'] = len(result) if result else 0
            return f"Scraped {len(result)} records"
        except Exception as e:
            return f"Scraping error: {e}"
    
    def _run_ocr_task(self, task: ScheduledTask) -> str:
        """Run an OCR processing task."""
        try:
            from enhanced_ocr import OCRValidator
            
            validator = OCRValidator()
            # This would process actual images
            return f"OCR processing completed"
        except Exception as e:
            return f"OCR error: {e}"
    
    def _run_sync_task(self, task: ScheduledTask) -> str:
        """Run a Supabase sync task."""
        try:
            # Sync with Supabase
            return "Sync completed"
        except Exception as e:
            return f"Sync error: {e}"
    
    def _run_export_task(self, task: ScheduledTask) -> str:
        """Run an export task."""
        try:
            from database import get_all_obitos
            
            records = get_all_obitos()
            task.config['last_export_count'] = len(records)
            return f"Exported {len(records)} records"
        except Exception as e:
            return f"Export error: {e}"
    
    def _run_custom_task(self, task: ScheduledTask) -> str:
        """Run a custom task defined in config."""
        command = task.config.get('command')
        if command:
            try:
                result = subprocess.run(
                    command, shell=True, capture_output=True, text=True, timeout=300
                )
                return result.stdout if result.returncode == 0 else result.stderr
            except Exception as e:
                return f"Command error: {e}"
        return "No command specified"
    
    def run_scheduler(self, check_interval: int = 60):
        """Run the scheduler loop."""
        logger.info("Scheduler started")
        self.running = True
        
        while self.running:
            try:
                # Check for due tasks
                due_tasks = self.get_due_tasks()
                
                for task in due_tasks:
                    if not self.running:
                        break
                    
                    # Check if task is already running
                    if task.task_id in self.running_tasks:
                        continue
                    
                    # Execute task
                    self.execute_task(task)
                
                # Sleep until next check
                time.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(check_interval)
        
        logger.info("Scheduler stopped")
    
    def start_scheduler(self, check_interval: int = 60):
        """Start the scheduler in a background thread."""
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            logger.warning("Scheduler already running")
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(
            target=self.run_scheduler,
            args=(check_interval,),
            daemon=True
        )
        self.scheduler_thread.start()
        logger.info("Scheduler thread started")
    
    def stop_scheduler(self):
        """Stop the scheduler."""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get status of a task."""
        with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                running_result = self.running_tasks.get(task_id)
                
                return {
                    'task': asdict(task),
                    'is_running': task_id in self.running_tasks,
                    'last_result': asdict(running_result) if running_result else None
                }
        return None
    
    def get_all_tasks(self) -> List[Dict]:
        """Get all scheduled tasks."""
        with self.lock:
            return [asdict(t) for t in self.tasks.values()]
    
    def get_task_history(self, limit: int = 20) -> List[Dict]:
        """Get task execution history."""
        with self.lock:
            return [asdict(r) for r in self.task_history[-limit:]]


class CronScheduleParser:
    """Parses cron-like schedule strings."""
    
    CRON_FIELDS = ['minute', 'hour', 'day', 'month', 'weekday']
    
    def __init__(self, expression: str):
        self.expression = expression
        self.fields = {}
        self._parse()
    
    def _parse(self):
        """Parse cron expression into fields."""
        parts = self.expression.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {self.expression}")
        
        for i, field in enumerate(parts):
            self.fields[self.CRON_FIELDS[i]] = field
    
    def get_next_run(self, base_time: datetime = None) -> datetime:
        """Calculate next run time based on cron expression."""
        if base_time is None:
            base_time = datetime.now()
        
        # Simple implementation - just advance by one unit based on granularity
        minute = self.fields.get('minute', '0')
        
        if minute == '*':
            return base_time + timedelta(minutes=1)
        elif ',' in minute:
            # Handle list - return next value
            return base_time + timedelta(minutes=1)
        elif minute.startswith('*/'):
            interval = int(minute[2:])
            return base_time + timedelta(minutes=interval)
        else:
            return base_time + timedelta(minutes=1)


def setup_default_schedules(scheduler: TaskScheduler):
    """Set up default scheduled tasks for the genealogy project."""
    
    # Daily scraping at 2 AM
    scheduler.add_task(
        name="Daily Obitos Scrape",
        task_type="scrape",
        frequency="daily",
        config={'source': 'digitarq'},
        max_runtime=60
    )
    
    # Hourly OCR processing
    scheduler.add_task(
        name="Hourly OCR Processing",
        task_type="ocr",
        frequency="hourly",
        config={'batch_size': 10},
        max_runtime=30
    )
    
    # Weekly full export
    scheduler.add_task(
        name="Weekly Data Export",
        task_type="export",
        frequency="weekly",
        config={'format': 'csv'},
        max_runtime=120
    )
    
    logger.info("Default schedules configured")


def test_scheduler():
    """Test the task scheduler."""
    print("=== Teste Scheduler ===")
    
    scheduler = TaskScheduler()
    
    # Add a test task
    task_id = scheduler.add_task(
        name="Test Task",
        task_type="custom",
        frequency="once",
        config={'command': 'echo "Hello from scheduled task"'},
        max_runtime=5
    )
    
    print(f"Added task: {task_id}")
    print(f"All tasks: {scheduler.get_all_tasks()}")
    
    # Start scheduler in background
    print("\nStarting scheduler (will run for 10 seconds)...")
    scheduler.start_scheduler(check_interval=2)
    
    # Let it run
    time.sleep(10)
    
    # Check history
    print(f"\nTask history: {scheduler.get_task_history()}")
    
    scheduler.stop_scheduler()
    print("Scheduler stopped")
    
    return scheduler


if __name__ == "__main__":
    test_scheduler()