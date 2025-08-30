"""
This module handles subdomain-based preview management for local testing and VPS deployment.
Uses nginx virtual hosts instead of cloudflared tunnels for better performance and control.
"""
import asyncio
import os
import signal
import time
from pathlib import Path
from typing import Optional, Dict, Any

# --- Preview Configuration ---
ACTIVE_PREVIEWS = {}  # {project_name: {'created_at': ..., 'domain': ..., 'status': ...}}

class SubdomainPreviewManager:
    def __init__(self, base_domain: str = "vibecode.akshath.tech", projects_dir: str = "projects"):
        self.base_domain = base_domain
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(exist_ok=True)
    
    def get_preview_url(self, project_name: str) -> str:
        """Generate preview URL for a project."""
        return f"http://{project_name}.{self.base_domain}"
    
    async def create_preview(self, project_name: str) -> Dict[str, Any]:
        """
        Create a preview for a project by ensuring the project files exist.
        With nginx configuration, this just validates the project exists.
        """
        project_path = self.projects_dir / project_name
        
        if not project_path.exists() or not (project_path / "index.html").exists():
            return {
                "success": False,
                "error": f"Project '{project_name}' not found or missing index.html"
            }
        
        preview_url = self.get_preview_url(project_name)
        
        ACTIVE_PREVIEWS[project_name] = {
            "created_at": time.time(),
            "domain": preview_url,
            "status": "active",
            "project_path": str(project_path)
        }
        
        return {
            "success": True,
            "preview_url": preview_url,
            "project_name": project_name
        }
    
    async def stop_preview(self, project_name: str) -> bool:
        """
        Stop a preview by removing it from active previews.
        Files remain but preview is no longer tracked.
        """
        if project_name in ACTIVE_PREVIEWS:
            del ACTIVE_PREVIEWS[project_name]
            return True
        return False
    
    async def list_active_previews(self) -> Dict[str, Any]:
        """List all currently active previews."""
        return ACTIVE_PREVIEWS.copy()
    
    async def cleanup_old_previews(self, max_age_seconds: int = 3600) -> int:
        """
        Clean up previews older than max_age_seconds.
        Returns number of previews cleaned up.
        """
        current_time = time.time()
        to_remove = []
        
        for project_name, details in ACTIVE_PREVIEWS.items():
            if current_time - details.get("created_at", 0) > max_age_seconds:
                to_remove.append(project_name)
        
        for project_name in to_remove:
            await self.stop_preview(project_name)
        
        return len(to_remove)

async def reaper_task(preview_manager: SubdomainPreviewManager, 
                     cleanup_interval_seconds: int = 300, 
                     max_lifetime_seconds: int = 3600):
    """
    Background task to clean up old previews.
    """
    while True:
        await asyncio.sleep(cleanup_interval_seconds)
        try:
            cleaned = await preview_manager.cleanup_old_previews(max_lifetime_seconds)
            if cleaned > 0:
                print(f"🧹 Cleaned up {cleaned} old preview(s)")
        except Exception as e:
            print(f"⚠️ Error during preview cleanup: {e}")

# Global instance
preview_manager = SubdomainPreviewManager()

# Legacy compatibility functions
def find_available_port() -> Optional[str]:
    """Legacy function - now returns project name instead of port."""
    # For subdomain-based previews, we don't need ports
    # Return a placeholder that tools.py expects
    return "subdomain-preview"

async def start_tunnels():
    """Legacy function - now just prints info about subdomain setup."""
    print("🌐 Subdomain preview system initialized")
    print(f"📡 Base domain: {preview_manager.base_domain}")
    print("ℹ️  Make sure nginx is configured to serve subdomains")
    print("ℹ️  Add '127.0.0.1 vibecode.akshath.tech *.vibecode.akshath.tech' to /etc/hosts for local testing")
