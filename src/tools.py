"""
This module defines the MCP (Model Context Protocol) tools for the Vibe Coder application.
These tools are the entry points for the user to interact with the application.
"""
import asyncio
import json
import os
import signal
import subprocess
import time
import uuid
from typing import Annotated, Optional

from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
from fastmcp.server.auth.auth import AccessToken
from pydantic import BaseModel, Field

from src.config import MY_NUMBER, SESSIONS, TOKEN
from src.llm import generate_single_page_app, modify_single_page_app
from src.subdomain_preview import preview_manager
from src.utils import generate_random_project_name, get_unique_project_name
from src.project_manager import project_manager

# --- Bearer Token Authentication ---
class SimpleBearerAuthProvider(BearerAuthProvider):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token

    async def load_access_token(self, token: str) -> AccessToken | None:
        if token == self.token:
            return AccessToken(
                token=token,
                client_id="puch-client",
                scopes=["*"],
                expires_at=None,
            )
        return None

# --- MCP Server ---
mcp = FastMCP("vibecode :)", auth=SimpleBearerAuthProvider(TOKEN))

class RichToolDescription(BaseModel):
    """A Pydantic model for providing rich descriptions for tools."""
    description: str
    use_when: str
    side_effects: str | None = None

@mcp.tool
async def validate() -> str:
    """A required tool for the MCP server to validate the connection."""
    return MY_NUMBER


@mcp.tool
async def about() -> dict:
    return {"name": mcp.name, "description": "build and deploy web apps in minutes with vibecode 🤖"}

@mcp.tool(description="Creates a simple, single-file web application from a prompt.")
async def vibecode(prompt: Annotated[str, Field(description="The prompt describing the app to create")], session_id: Annotated[Optional[str], Field(description="The session ID for the user.")] = None) -> str:
    """
    Generates a single-file web application based on the user's prompt.
    It creates a new project, generates the HTML, and saves it to a file.
    """
    if not session_id or session_id not in SESSIONS:
        session_id = str(uuid.uuid4())

    try:
        html_content = await generate_single_page_app(prompt)

        if not html_content or html_content.startswith("<h1>Error"):
            return f"❌ Failed to generate application content. Error: {html_content}"
        
        base_name = generate_random_project_name()
        project_name = get_unique_project_name(base_name, str(project_manager.local_projects_dir))

        # Save project using the project manager
        await project_manager.save_project_locally(
            project_name=project_name,
            html_content=html_content,
            prompt=prompt
        )
        
        SESSIONS[session_id] = project_name

        return json.dumps({
            "session_id": session_id,
            "project_name": project_name
        })

    except Exception as e:
        return f"❌ An internal error occurred while creating the application: {e}"

@mcp.tool(description="Creates a temporary, public URL to preview a generated application.")
async def preview_app(session_id: Annotated[Optional[str], Field(description="The session ID for the user.")] = None) -> str:
    """
    Creates a subdomain-based preview URL for the generated application.
    """
    if not session_id or session_id not in SESSIONS:
        if len(SESSIONS) == 1:
            session_id = list(SESSIONS.keys())[0]
        else:
            return f"❌ Error: Session ID '{session_id}' not found. Please start a new session."
    
    p_name = SESSIONS[session_id]
    
    try:
        # Create preview using subdomain system
        result = await preview_manager.create_preview(p_name)
        
        if result["success"]:
            preview_url = result["preview_url"]
            return f"✅ Preview is live at: {preview_url}\n\n🌐 Open this URL in your browser to see your app!"
        else:
            return f"❌ Error creating preview: {result['error']}"
            
    except Exception as e:
        return f"❌ An unexpected error occurred during preview creation: {e}"

@mcp.tool(
    description=RichToolDescription(
        description="Modifies an existing application based on user feedback.",
        use_when="ALWAYS use this tool when the user provides feedback or asks for changes to the app they just previewed.",
        side_effects="Reads the existing HTML file, uses an LLM to apply the requested changes, and overwrites the file.",
    ).model_dump_json()
)
async def modify_app(
    feedback: Annotated[str, Field(description="The user's feedback describing the changes to make.")],
    session_id: Annotated[str, Field(description="The session ID for the user.")],
) -> str:
    """
    Modifies an existing application based on user feedback.
    """
    if session_id not in SESSIONS:
        return "❌ Error: No active session found. Please create an app first."
    p_name = SESSIONS[session_id]
    project_dir = project_manager.get_local_project_path(p_name)
    file_path = project_dir / "index.html"

    if not file_path.exists():
        return f"❌ Error: Could not find the application file for project '{p_name}'."
    
    with open(file_path, "r", encoding="utf-8") as f:
        current_html = f.read()
    
    modified_html = await modify_single_page_app(current_html, feedback)
    
    if not modified_html or modified_html.startswith("<h1>Error"):
        return "❌ I wasn't able to apply those changes. Please try rephrasing."
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(modified_html)
    
    # Check if there's an active preview for this project
    active_previews = await preview_manager.list_active_previews()
    if p_name in active_previews:
        preview_url = active_previews[p_name]["domain"]
        return f"✅ I've applied your changes to '{p_name}'. You can see the updated version at {preview_url}"
    else:
        return f"✅ I've applied your changes to '{p_name}'. Use 'preview_app' to see the updated version."

@mcp.tool(description="Deploys a web application to a permanent public URL using Surge.sh.")
async def deploy_app(session_id: Annotated[str, Field(description="The session ID for the user.")]) -> str:
    """
    Deploys the application to a permanent public URL using Surge.sh.
    """
    if session_id not in SESSIONS:
        return "❌ Error: No active session found. Please create an app first."
    
    p_name = SESSIONS[session_id]
    project_dir = project_manager.get_local_project_path(p_name)
    
    if not project_dir.exists():
        return f"❌ Error: Project directory '{p_name}' not found."
    
    domain = f"{p_name}.surge.sh"
    cmd = ["npx", "surge", "--project", project_dir, "--domain", domain]
    
    try:
        result = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, check=True)
        return f"✅ Deployed '{p_name}'!\n\nLive at: https://{domain}" if domain in result.stdout else f"⚠️ Deployment maybe ok; output:\n{result.stdout}"
    except FileNotFoundError:
        return "❌ `npx` not found. Install Node.js."
    except subprocess.CalledProcessError as e:
        if "invalid token" in e.stderr.lower() or "login" in e.stderr.lower():
            return "⚠️ Run `npx surge login` first."
        return f"❌ Deployment failed:\n{e.stderr}"
    except Exception as e:
        return f"❌ Unexpected deploy error: {e}"


@mcp.tool(description="Deploy a project to the vibecode-deployed-projects git repository.")
async def save_to_repository(
    session_id: Annotated[str, Field(description="The session ID for the user.")],
    make_public: Annotated[bool, Field(description="Whether to make this project publicly visible in the repository")] = True
) -> str:
    """
    Saves the generated project to the vibecode-deployed-projects git repository.
    This creates a permanent backup of the project with version control.
    Users can choose whether to make their project publicly visible.
    """
    if session_id not in SESSIONS:
        return "❌ Error: No active session found. Please create an app first."
    
    p_name = SESSIONS[session_id]
    
    try:
        if make_public:
            # Deploy to repository
            result = await project_manager.deploy_project_to_repo(
                project_name=p_name,
                commit_message=f"Add public project: {p_name}"
            )
            
            if result["success"]:
                return f"✅ Project '{p_name}' saved to public repository! 📁🌍\n\nOthers can view it at: https://github.com/akshathmangudi/vibecode-deployed-projects\nYou can now deploy it to surge.sh or make further modifications."
            else:
                return f"❌ Failed to save to repository: {result['error']}"
        else:
            # Save locally only with privacy metadata
            local_path = project_manager.get_local_project_path(p_name)
            metadata_path = local_path / "metadata.json"
            
            if metadata_path.exists():
                import json
                metadata = json.loads(metadata_path.read_text())
                metadata["privacy"] = "private"
                metadata["public_repository"] = False
                metadata_path.write_text(json.dumps(metadata, indent=2))
            
            return f"✅ Project '{p_name}' saved privately! 🔒\n\nYour project is stored locally and won't be visible in the public repository.\nYou can still deploy it to surge.sh or make modifications."
            
    except Exception as e:
        return f"❌ Unexpected error saving project: {e}"


@mcp.tool(description="Push all saved projects to the remote GitHub repository.")
async def sync_repository() -> str:
    """
    Pushes all locally saved projects to the remote vibecode-deployed-projects repository.
    This syncs your local changes with GitHub.
    """
    try:
        result = await project_manager.push_to_remote()
        
        if result["success"]:
            return "✅ Successfully synced with GitHub! 🔄\n\nAll your projects are now backed up to: https://github.com/akshathmangudi/vibecode-deployed-projects"
        else:
            return f"❌ Failed to sync with GitHub: {result['error']}"
            
    except Exception as e:
        return f"❌ Unexpected error syncing repository: {e}"


@mcp.tool(description="List all projects stored in the repository.")
async def list_saved_projects() -> str:
    """
    Lists all projects that have been saved to the vibecode-deployed-projects repository.
    """
    try:
        projects = await project_manager.list_deployed_projects()
        
        if not projects:
            return "📂 No projects found in the repository yet.\n\nUse 'save_to_repository' after creating a project to start building your collection!"
        
        project_list = []
        for project in projects:
            created_at = project.get('created_at', 'Unknown')
            status = project.get('status', 'unknown')
            prompt = project.get('prompt', '')[:100] + "..." if len(project.get('prompt', '')) > 100 else project.get('prompt', '')
            
            project_list.append(f"• **{project['project_name']}** ({status})\n  📅 {created_at}\n  💭 {prompt}")
        
        return f"📁 **Saved Projects ({len(projects)} total):**\n\n" + "\n\n".join(project_list)
        
    except Exception as e:
        return f"❌ Error listing projects: {e}"
