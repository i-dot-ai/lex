"""Pipeline checkpoint system for resilient processing."""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Set, Optional, Any
import logging

from diskcache import Cache

logger = logging.getLogger(__name__)


class PipelineCheckpoint:
    """Manages checkpoint state for pipeline runs using mounted volume."""
    
    def __init__(self, checkpoint_id: str, base_dir: str = None):
        """
        Initialize checkpoint manager.
        
        Args:
            checkpoint_id: Unique identifier for this checkpoint
            base_dir: Base directory for checkpoints (auto-detected if None)
        """
        self.checkpoint_id = checkpoint_id
        
        # Use mounted volume in container or local data dir
        if base_dir is None:
            if os.path.exists("/app/data"):
                base_dir = "/app/data/checkpoints"
            else:
                base_dir = os.path.join(os.getcwd(), "data", "checkpoints")
        
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Use diskcache for atomic operations
        self.cache_dir = self.base_dir / checkpoint_id
        self.cache = Cache(str(self.cache_dir))
        
        logger.info(
            f"Checkpoint initialized: {checkpoint_id}",
            extra={
                "checkpoint_id": checkpoint_id,
                "checkpoint_path": str(self.cache_dir)
            }
        )
        
    def get_state(self) -> Dict[str, Any]:
        """Get current checkpoint state."""
        return {
            'processed_urls': set(self.cache.get('processed_urls', [])),
            'failed_urls': dict(self.cache.get('failed_urls', {})),
            'last_position': self.cache.get('last_position', 0),
            'metadata': self.cache.get('metadata', {}),
            'created_at': self.cache.get('created_at', datetime.now().isoformat()),
            'updated_at': self.cache.get('updated_at', datetime.now().isoformat())
        }
    
    def get_processed_urls(self) -> Set[str]:
        """Get set of processed URLs."""
        return set(self.cache.get('processed_urls', []))
    
    def mark_processed(self, url: str):
        """Mark a URL as successfully processed."""
        processed = set(self.cache.get('processed_urls', []))
        processed.add(url)
        self.cache.set('processed_urls', list(processed))
        self.cache.set('updated_at', datetime.now().isoformat())
        
    def mark_failed(self, url: str, error: str):
        """Mark a URL as failed with error details."""
        failed = dict(self.cache.get('failed_urls', {}))
        failed[url] = {
            'error': error,
            'timestamp': datetime.now().isoformat()
        }
        self.cache.set('failed_urls', failed)
        self.cache.set('updated_at', datetime.now().isoformat())
        
    def save_position(self, position: int):
        """Save current position in iteration."""
        self.cache.set('last_position', position)
        self.cache.set('updated_at', datetime.now().isoformat())
        
    def update_metadata(self, metadata: Dict[str, Any]):
        """Update checkpoint metadata."""
        current_metadata = self.cache.get('metadata', {})
        current_metadata.update(metadata)
        self.cache.set('metadata', current_metadata)
        self.cache.set('updated_at', datetime.now().isoformat())
    
    def mark_combination_complete(self, combination_key: str):
        """Mark a year/type combination as fully processed."""
        completed = set(self.cache.get('completed_combinations', []))
        completed.add(combination_key)
        self.cache.set('completed_combinations', list(completed))
        self.cache.set('updated_at', datetime.now().isoformat())
    
    def get_completed_combinations(self) -> Set[str]:
        """Get set of completed year/type combinations."""
        return set(self.cache.get('completed_combinations', []))
    
    def is_combination_complete(self, combination_key: str) -> bool:
        """Check if a year/type combination is complete."""
        completed = set(self.cache.get('completed_combinations', []))
        return combination_key in completed
        
    def clear(self):
        """Clear checkpoint data."""
        self.cache.clear()
        logger.info(f"Checkpoint cleared: {self.checkpoint_id}")
        
    def exists(self) -> bool:
        """Check if checkpoint has data."""
        return len(self.cache) > 0
    
    def get_summary(self) -> Dict[str, Any]:
        """Get checkpoint summary for logging."""
        state = self.get_state()
        failed_count = len(state['failed_urls'])
        processed_count = len(state['processed_urls'])
        
        return {
            'checkpoint_id': self.checkpoint_id,
            'processed_count': processed_count,
            'failed_count': failed_count,
            'last_position': state['last_position'],
            'created_at': state['created_at'],
            'updated_at': state['updated_at'],
            'has_failures': failed_count > 0
        }
    
    @classmethod
    def list_checkpoints(cls, base_dir: str = None) -> list[str]:
        """List all available checkpoints."""
        if base_dir is None:
            if os.path.exists("/app/data"):
                base_dir = "/app/data/checkpoints"
            else:
                base_dir = os.path.join(os.getcwd(), "data", "checkpoints")
                
        base_path = Path(base_dir)
        if not base_path.exists():
            return []
            
        return [d.name for d in base_path.iterdir() if d.is_dir()]
    
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure cache is closed."""
        # Diskcache handles cleanup automatically
        pass