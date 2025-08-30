"""
This module handles project storage, git operations, and deployment to the vibecode-deployed-projects repository.
"""
import asyncio
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

class ProjectManager:
    def __init__(self, 
                 local_projects_dir: str = "projects",
                 deployed_repo_path: str = "../vibecode-deployed-projects",
                 base_domain: str = "vibecode.akshath.tech"):
        """
        Initialize the ProjectManager.
        
        Args:
            local_projects_dir: Local directory for temporary project storage
            deployed_repo_path: Path to the cloned vibecode-deployed-projects repository
            base_domain: Base domain for preview URLs
        """
        self.local_projects_dir = Path(local_projects_dir)
        self.deployed_repo_path = Path(deployed_repo_path)
        self.deployed_projects_dir = self.deployed_repo_path / "projects"
        self.base_domain = base_domain
        
        # Ensure directories exist
        self.local_projects_dir.mkdir(exist_ok=True)
        self.deployed_projects_dir.mkdir(exist_ok=True)
    
    def get_local_project_path(self, project_name: str) -> Path:
        """Get the path to a project in local storage."""
        return self.local_projects_dir / project_name
    
    def get_deployed_project_path(self, project_name: str) -> Path:
        """Get the path to a project in the deployed repository."""
        return self.deployed_projects_dir / project_name
    
    async def save_project_locally(self, 
                                 project_name: str, 
                                 html_content: str, 
                                 prompt: str,
                                 metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Save a project to local storage.
        
        Args:
            project_name: Name of the project
            html_content: The generated HTML content
            prompt: The original user prompt
            metadata: Additional metadata to store
            
        Returns:
            Path to the saved project directory
        """
        project_dir = self.get_local_project_path(project_name)
        project_dir.mkdir(exist_ok=True)
        
        # Save HTML file
        html_path = project_dir / "index.html"
        html_path.write_text(html_content, encoding="utf-8")
        
        # Save README
        readme_path = project_dir / "README.md"
        readme_content = f"# {project_name}\n\n## Original Prompt\n> {prompt}\n\n## Generated\n{datetime.now().isoformat()}"
        readme_path.write_text(readme_content, encoding="utf-8")
        
        # Save metadata
        project_metadata = {
            "project_name": project_name,
            "prompt": prompt,
            "created_at": datetime.now().isoformat(),
            "status": "local",
            **(metadata or {})
        }
        
        metadata_path = project_dir / "metadata.json"
        metadata_path.write_text(json.dumps(project_metadata, indent=2), encoding="utf-8")
        
        return str(project_dir)
    
    async def deploy_project_to_repo(self, project_name: str, commit_message: Optional[str] = None) -> dict:
        """
        Deploy a project from local storage to the git repository.
        
        Args:
            project_name: Name of the project to deploy
            commit_message: Custom commit message
            
        Returns:
            Dictionary with deployment status and details
        """
        local_path = self.get_local_project_path(project_name)
        deployed_path = self.get_deployed_project_path(project_name)
        
        if not local_path.exists():
            return {"success": False, "error": f"Local project '{project_name}' not found"}
        
        try:
            # Copy project to deployed repository
            if deployed_path.exists():
                shutil.rmtree(deployed_path)
            shutil.copytree(local_path, deployed_path)
            
            # Update metadata
            metadata_path = deployed_path / "metadata.json"
            if metadata_path.exists():
                metadata = json.loads(metadata_path.read_text())
                metadata["status"] = "deployed"
                metadata["deployed_at"] = datetime.now().isoformat()
                metadata_path.write_text(json.dumps(metadata, indent=2))
            
            # Git operations
            await self._git_add_and_commit(project_name, commit_message)
            
            return {
                "success": True,
                "project_name": project_name,
                "deployed_path": str(deployed_path),
                "message": f"Project '{project_name}' deployed to repository"
            }
            
        except Exception as e:
            return {"success": False, "error": f"Deployment failed: {str(e)}"}
    
    async def _git_add_and_commit(self, project_name: str, commit_message: Optional[str] = None):
        """Perform git add and commit operations."""
        if not commit_message:
            commit_message = f"Add project: {project_name}"
        
        commands = [
            ["git", "add", f"projects/{project_name}"],
            ["git", "commit", "-m", commit_message]
        ]
        
        for cmd in commands:
            result = await asyncio.to_thread(
                subprocess.run, 
                cmd, 
                cwd=self.deployed_repo_path,
                capture_output=True, 
                text=True
            )
            
            if result.returncode != 0 and "nothing to commit" not in result.stdout:
                raise Exception(f"Git command failed: {result.stderr}")
    
    async def push_to_remote(self, branch: str = "main") -> dict:
        """
        Push all committed changes to the remote repository.
        
        Args:
            branch: Git branch to push to
            
        Returns:
            Dictionary with push status
        """
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "push", "origin", branch],
                cwd=self.deployed_repo_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                return {"success": True, "message": "Successfully pushed to remote repository"}
            else:
                return {"success": False, "error": f"Push failed: {result.stderr}"}
                
        except Exception as e:
            return {"success": False, "error": f"Push failed: {str(e)}"}
    
    async def list_deployed_projects(self) -> list:
        """List all projects in the deployed repository."""
        projects = []
        
        if not self.deployed_projects_dir.exists():
            return projects
        
        for project_dir in self.deployed_projects_dir.iterdir():
            if project_dir.is_dir():
                metadata_path = project_dir / "metadata.json"
                if metadata_path.exists():
                    try:
                        metadata = json.loads(metadata_path.read_text())
                        projects.append(metadata)
                    except json.JSONDecodeError:
                        pass
        
        return projects
    
    async def cleanup_local_project(self, project_name: str) -> bool:
        """
        Remove a project from local storage after successful deployment.
        
        Args:
            project_name: Name of the project to clean up
            
        Returns:
            True if cleanup was successful
        """
        try:
            local_path = self.get_local_project_path(project_name)
            if local_path.exists():
                shutil.rmtree(local_path)
            return True
        except Exception:
            return False

# Global instance
project_manager = ProjectManager()
