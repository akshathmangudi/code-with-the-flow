import asyncio
from typing import Annotated
import os
import re
import json
from dotenv import load_dotenv
from fastmcp import FastMCP, Context
from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
from mcp import ErrorData, McpError
from mcp.server.auth.provider import AccessToken
from mcp.types import TextContent, INVALID_PARAMS, INTERNAL_ERROR
from pydantic import BaseModel, Field
import vertexai
from vertexai.generative_models import GenerativeModel
import time
import subprocess
import signal
from utils import (
    generate_random_project_name,
    get_unique_project_name,
    is_port_in_use,
)


# --- Load environment variables ---
load_dotenv()

TOKEN = os.environ.get("PUCH_AI_API_KEY", "28faaaa48cb3")
MY_NUMBER = os.environ.get("MY_NUMBER", "918106200629")

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "refrakt-xai")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

assert TOKEN is not None, "Please set PUCH_AI_API_KEY in your .env file"
assert MY_NUMBER is not None, "Please set MY_NUMBER in your .env file"

# Initialize Vertex AI if project ID is available
try:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    gemini_model = GenerativeModel("gemini-2.5-flash")
    print(f"✅ Vertex AI initialized with project: {PROJECT_ID}")
except Exception as e:
    print(f"⚠️  Vertex AI initialization failed: {e}")
    gemini_model = None

# --- Auth Provider ---
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

# --- Rich Tool Description model ---
class RichToolDescription(BaseModel):
    description: str
    use_when: str
    side_effects: str | None = None

# --- New Simplified LLM Integration ---
async def generate_single_page_app(user_prompt: str) -> str:
    """Generates a single, self-contained HTML file for a web app."""
    if not gemini_model:
        return "<h1>Error: Gemini model not initialized</h1>"

    try:
        system_prompt = """You are an expert web developer. Your task is to create a complete, single-file, self-contained web application based on a user's prompt.

IMPORTANT CONSTRAINTS:
- You MUST return a single HTML file.
- All CSS and JavaScript MUST be included inline within the HTML file using `<style>` and `<script>` tags.
- Do NOT use any external frameworks or libraries unless you can include them from a CDN.
- The application must be fully functional as a single `.html` file.
- The code should be clean, well-formatted, and modern.
- Focus on functionality over complex design, but make it look presentable.
- Do NOT include any explanations, comments, or markdown formatting around the code. ONLY return the raw HTML code."""
        prompt = f"{system_prompt}\n\nNow, create a single-file web application for the following prompt: '{user_prompt}'"

        print(f"🔨 Generating single-page app for: {user_prompt}...")
        response = await gemini_model.generate_content_async(prompt)
        
        html_content = response.text
        if "```html" in html_content:
            html_content = re.search(r'```html\n(.*?)\n```', html_content, re.DOTALL).group(1)

        print("✅ HTML content generated.")
        return html_content.strip()

    except Exception as e:
        print(f"❌ Single-page app generation error: {e}")
        return f"<h1>Error generating app</h1><p>{e}</p>"


# --- MCP Server Setup ---
mcp = FastMCP(
    "Vibe Coder MCP Server",
    auth=SimpleBearerAuthProvider(TOKEN),
)

# --- Multi-User Preview Management ---
PREVIEW_PORT_RANGE = range(9000, 9021) # Ports for preview servers
ACTIVE_PREVIEWS = {} # In-memory store: {port: {'pid': ..., 'project_name': ..., 'creation_time': ...}}
# This is now the public ngrok domain that points to the VS Code proxy
PUBLIC_DOMAIN = "d6a80fc8cd55.ngrok-free.app" 

def find_available_port() -> int | None:
    """Finds and reserves an available port from the pool."""
    for port in PREVIEW_PORT_RANGE:
        if port not in ACTIVE_PREVIEWS and not is_port_in_use(port):
            return port
    return None

async def reaper_task(cleanup_interval_seconds=60, max_lifetime_seconds=240):
    """Periodically cleans up old preview servers."""
    while True:
        await asyncio.sleep(cleanup_interval_seconds)
        current_time = time.time()
        
        for port in list(ACTIVE_PREVIEWS.keys()):
            details = ACTIVE_PREVIEWS.get(port)
            if not details:
                continue

            if (current_time - details['creation_time']) > max_lifetime_seconds:
                print(f"🧹 Reaper: Cleaning up preview for '{details['project_name']}' on port {port} (PID: {details['pid']})...")
                try:
                    os.kill(details['pid'], signal.SIGTERM)
                    print(f"  -> Process {details['pid']} terminated.")
                except ProcessLookupError:
                    print(f"  -> Process {details['pid']} not found. Already terminated.")
                except Exception as e:
                    print(f"  -> Error terminating process {details['pid']}: {e}")
                
                del ACTIVE_PREVIEWS[port]
                print(f"  -> Port {port} is now free.")

# --- Tools ---

@mcp.tool
async def validate() -> str:
    """Required validate tool that returns your phone number."""
    return MY_NUMBER

@mcp.tool(description="Creates a simple, single-file web application from a prompt.")
async def vibecode(prompt: Annotated[str, Field(description="The prompt describing the app to create")]) -> str:
    """Generates a single-file web application based on the user's prompt."""
    try:
        print(f"🎯 vibecode called with prompt: {prompt}")
        html_content = await generate_single_page_app(prompt)
        if not html_content or html_content.startswith("<h1>Error"):
             return f"❌ Failed to generate application content. Error: {html_content}"

        base_name = generate_random_project_name()
        project_dir_base = os.path.join(os.path.dirname(__file__), '..', 'akshath')
        os.makedirs(project_dir_base, exist_ok=True)
        
        project_name, project_dir = get_unique_project_name(base_name, project_dir_base)
        os.makedirs(project_dir, exist_ok=True)
        print(f"📁 Created project directory: {project_dir}")

        file_path = os.path.join(project_dir, 'index.html')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✅ Saved application to {file_path}")

        readme_content = f"# {project_name}\n\nPrompt:\n> {prompt}"
        readme_path = os.path.join(project_dir, 'README.md')
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        return f"✅ Okay, I've created the '{project_name}' application! You can now preview it by saying \"preview the app\"."
    except Exception as e:
        return f"❌ An unexpected error occurred in vibecode: {e}"

@mcp.tool(description="Creates a temporary, public URL to preview a generated application.")
async def preview_app(project_name: Annotated[str, Field(description="The name of the project to preview.")]) -> str:
    """Starts a dedicated server and creates a public dev tunnel URL for the preview."""
    if not project_name:
        return "❌ Error: No project name provided."

    project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'akshath', project_name))
    if not os.path.isdir(project_dir):
        return f"❌ Error: Project directory '{project_name}' not found in '/akshath'."

    for port, details in ACTIVE_PREVIEWS.items():
        if details['project_name'] == project_name:
            details['creation_time'] = time.time() # Reset timer on re-preview
            url = f"https://{PUBLIC_DOMAIN}/proxy/{port}/"
            return f"✅ This project already has a live preview:\n{url}"

    port = find_available_port()
    if port is None:
        return "❌ Error: All preview slots are currently in use. Please try again later."

    try:
        server_command = ["python3", "-m", "http.server", str(port), "--directory", str(project_dir)]
        print(f"Starting server for '{project_name}' on port {port}...")
        server_process = subprocess.Popen(server_command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        ACTIVE_PREVIEWS[port] = {
            'pid': server_process.pid,
            'project_name': project_name,
            'creation_time': time.time()
        }
        print(f"✅ Started preview for '{project_name}' (PID: {server_process.pid}) on port {port}")

        url = f"https://{PUBLIC_DOMAIN}/proxy/{port}/"
        return f"✅ Preview is live at: {url}"
    except Exception as e:
        if port in ACTIVE_PREVIEWS:
            del ACTIVE_PREVIEWS[port]
        return f"❌ An unexpected error occurred while starting the preview: {e}"

@mcp.tool(description="Modifies an existing application based on user feedback.")
async def modify_app(
    feedback: Annotated[str, Field(description="The user's feedback describing the changes.")],
    project_name: Annotated[str, Field(description="The name of the project to modify.")],
) -> str:
    """Reads, modifies, and saves the application's HTML file based on feedback."""
    if not project_name:
        return "❌ Error: No project name provided."

    project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'akshath', project_name))
    file_path = os.path.join(project_dir, 'index.html')
    if not os.path.exists(file_path):
        return f"❌ Error: Could not find the application file for project '{project_name}'."

    with open(file_path, 'r', encoding='utf-8') as f:
        current_html = f.read()

    modified_html = await modify_single_page_app(current_html, feedback)
    if not modified_html or modified_html.startswith("<h1>Error"):
        return "❌ I wasn't able to apply those changes. Please try rephrasing."

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(modified_html)

    return f"✅ I've applied your changes to '{project_name}'. You can see the updated version at the same preview link."

@mcp.tool(description="Deploys a web application to a permanent public URL using Surge.sh.")
async def deploy_app(project_name: Annotated[str, Field(description="The name of the project to deploy.")]) -> str:
    """Deploys the specified project to a public URL using surge.sh."""
    if not project_name:
        return "❌ Error: No project name provided."

    project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'akshath', project_name))
    if not os.path.isdir(project_dir):
        return f"❌ Error: Project directory '{project_name}' not found."

    domain = f"{project_name}.surge.sh"
    command = ["npx", "surge", "--project", project_dir, "--domain", domain]

    try:
        result = await asyncio.to_thread(
            subprocess.run, command, capture_output=True, text=True, check=True
        )
        if domain in result.stdout:
            return f"✅ Successfully deployed '{project_name}'!\n\nYour app is live at: https://{domain}"
        else:
            return f"⚠️ Deployment may have succeeded, but I couldn't confirm the URL. Output:\n{result.stdout}"
    except FileNotFoundError:
        return "❌ Error: `npx` not found. Please ensure Node.js is installed."
    except subprocess.CalledProcessError as e:
        if "invalid token" in e.stderr.lower() or "login" in e.stderr.lower():
            return "⚠️ Deployment requires login. Please run `npx surge login` in your terminal first."
        return f"❌ Deployment failed.\n\nError:\n{e.stderr}"
    except Exception as e:
        return f"❌ An unexpected error occurred during deployment: {e}"

# --- Run MCP Server ---
async def main():
    print("🚀 Starting Vibe Coder MCP server on http://0.0.0.0:7000")
    reaper = asyncio.create_task(reaper_task())
    server = mcp.run_async("streamable-http", host="0.0.0.0", port=7000)
    await asyncio.gather(reaper, server)

if __name__ == "__main__":
    asyncio.run(main())