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
from pydantic import BaseModel, Field

from src.config import MY_NUMBER, SESSIONS
from src.llm import generate_single_page_app, modify_single_page_app
from src.preview import ACTIVE_PREVIEWS, find_available_port
from src.utils import generate_random_project_name, get_unique_project_name

# --- MCP Server ---
mcp = FastMCP("vibecode :)")

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
        project_dir_base = os.path.join(os.path.dirname(__file__), "..", "projects")
        os.makedirs(project_dir_base, exist_ok=True)
        project_name, project_dir = get_unique_project_name(base_name, project_dir_base)
        os.makedirs(project_dir, exist_ok=True)

        file_path = os.path.join(project_dir, "index.html")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        readme_path = os.path.join(project_dir, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(f"# {project_name}\n\nPrompt:\n> {prompt}")
        
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
    Starts a local web server to preview the generated application and provides a public URL.
    """
    if not session_id or session_id not in SESSIONS:
        if len(SESSIONS) == 1:
            session_id = list(SESSIONS.keys())[0]
        else:
            return f"❌ Error: Session ID '{session_id}' not found. Please start a new session."
    
    p_name = SESSIONS[session_id]
    project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "projects", p_name))
    if not os.path.isdir(project_dir):
        return f"❌ Error: Project directory '{p_name}' not found."
    
    port = find_available_port()
    if port is None:
        return "❌ Error: All preview slots are currently in use. Please try again later."

    if ACTIVE_PREVIEWS.get(port) and ACTIVE_PREVIEWS[port].get('pid'):
        old_pid = ACTIVE_PREVIEWS[port]['pid']
        try:
            os.kill(old_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass # Process already gone

    try:
        server_cmd = ["python3", "-m", "http.server", str(port), "--directory", str(project_dir)]
        server_proc = subprocess.Popen(server_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        ACTIVE_PREVIEWS[port]['pid'] = server_proc.pid
        ACTIVE_PREVIEWS[port]['project_name'] = p_name
        ACTIVE_PREVIEWS[port]['creation_time'] = time.time()

        public_url = ACTIVE_PREVIEWS[port].get('public_url', 'No public URL found.')
        return f"✅ Preview is live at: {public_url}"
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
    project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "projects", p_name))
    file_path = os.path.join(project_dir, "index.html")

    if not os.path.exists(file_path):
        return f"❌ Error: Could not find the application file for project '{p_name}'."
    
    with open(file_path, "r", encoding="utf-8") as f:
        current_html = f.read()
    
    modified_html = await modify_single_page_app(current_html, feedback)
    
    if not modified_html or modified_html.startswith("<h1>Error"):
        return "❌ I wasn't able to apply those changes. Please try rephrasing."
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(modified_html)
    
    preview_url = None
    for port, details in ACTIVE_PREVIEWS.items():
        if details.get("project_name") == p_name:
            preview_url = details.get('public_url')
            break

    if preview_url:
        return f"✅ I've applied your changes to '{p_name}'. You can see the updated version at {preview_url}"
    else:
        return f"✅ I've applied your changes to '{p_name}'. You can preview the app to see the changes."

@mcp.tool(description="Deploys a web application to a permanent public URL using Surge.sh.")
async def deploy_app(session_id: Annotated[str, Field(description="The session ID for the user.")]) -> str:
    """
    Deploys the application to a permanent public URL using Surge.sh.
    """
    if session_id not in SESSIONS:
        return "❌ Error: No active session found. Please create an app first."
    
    p_name = SESSIONS[session_id]
    project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "projects", p_name))
    
    if not os.path.isdir(project_dir):
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
