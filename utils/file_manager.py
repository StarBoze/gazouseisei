"""
File Manager module for handling temporary files and zip creation
"""
import os
import shutil
import logging
import asyncio
import zipfile
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FileManager:
    def __init__(self, base_dir: str = 'static/temp'):
        """
        Initialize file manager
        
        Args:
            base_dir: Base directory for temporary files
        """
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
    
    def create_session_dir(self) -> str:
        """
        Create a new session directory
        
        Returns:
            Path to created session directory
        """
        # Create unique directory name using timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"session_{timestamp}"
        session_dir = os.path.join(self.base_dir, session_id)
        
        # Create directories
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(os.path.join(session_dir, "articles"), exist_ok=True)
        os.makedirs(os.path.join(session_dir, "images"), exist_ok=True)
        
        logger.info(f"Created session directory: {session_dir}")
        return session_dir
    
    def create_zip_archive(self, 
                        session_dir: str, 
                        article_files: List[str],
                        image_files: List[str],
                        combined_markdown_path: Optional[str] = None) -> str:
        """
        Create a ZIP archive of the generated content
        
        Args:
            session_dir: Session directory
            article_files: List of article file paths
            image_files: List of image file paths
            combined_markdown_path: Path to combined markdown file
            
        Returns:
            Path to the created ZIP file
        """
        # Create zip filename based on timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"article_package_{timestamp}.zip"
        zip_path = os.path.join(session_dir, zip_filename)
        
        # Create ZIP file
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add individual article files
            for file_path in article_files:
                if os.path.exists(file_path):
                    arcname = os.path.join("articles", os.path.basename(file_path))
                    zipf.write(file_path, arcname)
            
            # Add image files
            for file_path in image_files:
                if os.path.exists(file_path):
                    arcname = os.path.join("images", os.path.basename(file_path))
                    zipf.write(file_path, arcname)
            
            # Add combined markdown if provided
            if combined_markdown_path and os.path.exists(combined_markdown_path):
                zipf.write(combined_markdown_path, "article_combined.md")
                
        logger.info(f"Created ZIP archive: {zip_path}")
        return zip_path
    
    async def schedule_cleanup(self, session_dir: str, hours: int = 24):
        """
        Schedule cleanup of temporary files after specified time
        
        Args:
            session_dir: Path to session directory
            hours: Number of hours after which to delete files
        """
        logger.info(f"Scheduled cleanup for {session_dir} after {hours} hours")
        
        # Write cleanup info file
        cleanup_info = {
            "created_at": datetime.now().isoformat(),
            "cleanup_at": (datetime.now() + timedelta(hours=hours)).isoformat(),
            "session_dir": session_dir
        }
        
        info_path = os.path.join(session_dir, "cleanup_info.txt")
        with open(info_path, 'w') as f:
            for key, value in cleanup_info.items():
                f.write(f"{key}: {value}\n")
        
        # In a production system, we would use a proper task scheduler
        # For this MVP, we'll just log the scheduled time
        logger.info(f"Temp files in {session_dir} scheduled for deletion at {cleanup_info['cleanup_at']}")
    
    def clean_old_sessions(self, hours: int = 24):
        """
        Clean up session directories older than specified time
        
        Args:
            hours: Delete sessions older than this many hours
        """
        try:
            # Get current time
            now = datetime.now()
            cutoff_time = now - timedelta(hours=hours)
            
            # Check all directories in base_dir
            for session_name in os.listdir(self.base_dir):
                session_path = os.path.join(self.base_dir, session_name)
                
                # Skip if not a directory
                if not os.path.isdir(session_path):
                    continue
                
                # Check directory creation time
                try:
                    # Get directory creation timestamp
                    creation_time = datetime.fromtimestamp(os.path.getctime(session_path))
                    
                    # If older than cutoff time, delete it
                    if creation_time < cutoff_time:
                        logger.info(f"Cleaning up old session: {session_path}")
                        shutil.rmtree(session_path, ignore_errors=True)
                        
                except Exception as e:
                    logger.error(f"Error checking/removing session {session_path}: {e}")
        
        except Exception as e:
            logger.error(f"Error in clean_old_sessions: {e}")
            
    def get_relative_path(self, file_path: str) -> str:
        """
        Convert absolute path to path relative to the app root
        
        Args:
            file_path: Absolute file path
            
        Returns:
            Relative path suitable for web references
        """
        # Check if base_dir is in the path
        if self.base_dir in file_path:
            return file_path.split(self.base_dir)[-1].lstrip('/')
        
        # Otherwise, just return the filename
        return os.path.basename(file_path)
