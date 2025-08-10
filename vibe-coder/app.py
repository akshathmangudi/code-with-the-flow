import asyncio
from typing import Annotated, Optional
import os, re, json, time, subprocess, signal, httpx, uuid
from urllib.parse import urlparse
from dotenv import load_dotenv
from fastmcp import FastMCP, Context
from mcp import ErrorData, McpError
from mcp.types import TextContent, INVALID_PARAMS, INTERNAL_ERROR
from pydantic import BaseModel, Field
import vertexai
from vertexai.generative_models import GenerativeModel
from utils import generate_random_project_name, get_unique_project_name, is_port_in_use

# --- Load environment variables ---
load_dotenv()
TOKEN = os.environ.get("PUCH_AI_API_KEY", "28faaaa48cb3")
MY_NUMBER = os.environ.get("MY_NUMBER", "918106200629")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "refrakt-xai")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
assert TOKEN is not None
assert MY_NUMBER is not None

# --- Global State ---
SESSIONS = {}

# --- Vertex init (optional) ---
try:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    gemini_model = GenerativeModel("gemini-2.5-flash")
    print(f"✅ Vertex AI initialized with project: {PROJECT_ID}")
except Exception as e:
    print(f"⚠️ Vertex AI initialization failed: {e}")
    gemini_model = None

class RichToolDescription(BaseModel):
    description: str
    use_when: str
    side_effects: str | None = None

async def generate_single_page_app(user_prompt: str) -> str:
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
        html_content = response.text or ""
        if "```html" in html_content:
            m = re.search(r"```html\n(.*?)\n```", html_content, re.DOTALL)
            if m:
                html_content = m.group(1)
        print("✅ HTML content generated.")
        return html_content.strip()
    except Exception as e:
        print(f"❌ Single-page app generation error: {e}")
        return f"<h1>Error generating app</h1><p>{e}</p>"

async def modify_single_page_app(current_html: str, user_feedback: str) -> str:
    """Uses an LLM to modify the HTML based on user feedback."""
    if not gemini_model:
        return "<h1>Error: Gemini model not initialized</h1>"
    try:
        system_prompt = """You are an expert web developer. Your task is to modify an existing single-file HTML application based on user feedback.

IMPORTANT CONSTRAINTS:
- You will be given the current HTML code and a user's request for a change.
- You MUST return the complete, modified HTML code.
- All CSS and JavaScript MUST remain included inline within the HTML file.
- The application must remain fully functional as a single `.html` file.
- Do NOT include any explanations, comments, or markdown formatting around the code. ONLY return the raw HTML code."""
        prompt = f"{system_prompt}\n\nHere is the current HTML code:\n```html\n{current_html}\n```\n\nHere is the user's feedback on what to change:\n'{user_feedback}'\n\nNow, please provide the complete, updated HTML code with the requested changes."
        print(f"🔨 Applying modifications for: {user_feedback}...")
        response = await gemini_model.generate_content_async(prompt)
        html_content = response.text or ""
        if "```html" in html_content:
            m = re.search(r"```html\n(.*?)\n```", html_content, re.DOTALL)
            if m:
                html_content = m.group(1)
        print("✅ HTML content modified.")
        return html_content.strip()
    except Exception as e:
        print(f"❌ App modification error: {e}")
        return f"<h1>Error modifying app</h1><p>{e}</p>"

# --- MCP Server (no auth; transport = streamable-http) ---
mcp = FastMCP("Vibe Coder MCP Server")

PREVIEW_PORT_RANGE = range(9000, 9021)
ACTIVE_PREVIEWS = {} # {port: {'pid': ..., 'project_name': ..., 'creation_time': ..., 'public_url': ...}}

def find_available_port() -> int | None:
    # First, look for a completely empty slot
    for port, details in ACTIVE_PREVIEWS.items():
        if details.get('project_name') is None:
            return port

    # If all slots are full, find the oldest one to rotate
    oldest_port = None
    oldest_time = float('inf')
    for port, details in ACTIVE_PREVIEWS.items():
        if details.get('creation_time', float('inf')) < oldest_time:
            oldest_time = details['creation_time']
            oldest_port = port
    
    return oldest_port


async def reaper_task(cleanup_interval_seconds=60, max_lifetime_seconds=240):
    while True:
        await asyncio.sleep(cleanup_interval_seconds)
        now = time.time()
        for port, details in list(ACTIVE_PREVIEWS.items()):
            if details.get('project_name') and (now - details["creation_time"]) > max_lifetime_seconds:
                print(f"🧹 Reaper: stopping preview for {details['project_name']} on port {port} (PID {details['pid']})")
                try:
                    os.kill(details["pid"], signal.SIGTERM)
                    print(f"  -> Process {details['pid']} terminated.")
                except ProcessLookupError:
                    print(f"  -> Process {details['pid']} not found.")
                except Exception as e:
                    print(f"  -> Error killing process {details['pid']}: {e}")
                ACTIVE_PREVIEWS[port]['project_name'] = None
                ACTIVE_PREVIEWS[port]['pid'] = None
                ACTIVE_PREVIEWS[port]['creation_time'] = None

@mcp.tool
async def validate() -> str:
    return MY_NUMBER

@mcp.tool(description="Creates a simple, single-file web application from a prompt.")
async def vibecode(prompt: Annotated[str, Field(description="The prompt describing the app to create")], session_id: Annotated[Optional[str], Field(description="The session ID for the user.")] = None) -> str:
    if session_id and session_id in SESSIONS:
        pass
    else:
        session_id = str(uuid.uuid4())

    try:
        print("--- VIBECODE TRACE: START ---")
        print(f"🎯 vibecode called with prompt: {prompt}")
        
        html_content = await generate_single_page_app(prompt)
        print("--- VIBECODE TRACE: 1. HTML content generated ---")

        if not html_content or html_content.startswith("<h1>Error"):
            print("--- VIBECODE TRACE: ERROR - HTML generation failed ---")
            return f"❌ Failed to generate application content. Error: {html_content}"
        
        base_name = generate_random_project_name()
        print(f"--- VIBECODE TRACE: 2. Generated base_name: {base_name} ---")

        project_dir_base = os.path.join(os.path.dirname(__file__), "..")
        print(f"--- VIBECODE TRACE: 3. Project base dir: {project_dir_base} ---")

        os.makedirs(project_dir_base, exist_ok=True)
        print("--- VIBECODE TRACE: 4. Ensured base directory exists ---")

        project_name, project_dir = get_unique_project_name(base_name, project_dir_base)
        print(f"--- VIBECODE TRACE: 5. Generated unique project name '{project_name}' at path: {project_dir} ---")

        os.makedirs(project_dir, exist_ok=True)
        print("--- VIBECODE TRACE: 6. Ensured unique project directory exists ---")

        file_path = os.path.join(project_dir, "index.html")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"--- VIBECODE TRACE: 7. Saved index.html to {file_path} ---")

        readme_path = os.path.join(project_dir, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(f"# {project_name}\n\nPrompt:\n> {prompt}")
        print(f"--- VIBECODE TRACE: 8. Saved README.md to {readme_path} ---")
        
        SESSIONS[session_id] = project_name
        print(f"--- VIBECODE TRACE: SUCCESS (set SESSIONS['{session_id}']='{project_name}') ---")

        return json.dumps({
            "session_id": session_id,
            "project_name": project_name
        })

    except Exception as e:
        import traceback
        print(f"--- VIBECODE TRACE: EXCEPTION BLOCK ---")
        print(f"❌ An unexpected error occurred in vibecode: {e}")
        print(f"Full traceback: {traceback.format_exc()}")
        return f"❌ An internal error occurred while creating the application. Please check the server logs."



@mcp.tool(description="Creates a temporary, public URL to preview a generated application.")
async def preview_app(session_id: Annotated[Optional[str], Field(description="The session ID for the user.")] = None) -> str:
    print(f"--- PREVIEW TRACE: START ---")
    print(f"🎯 preview_app called with session_id: {session_id}")

    if not session_id or session_id not in SESSIONS:
        if len(SESSIONS) == 1:
            session_id = list(SESSIONS.keys())[0]
            print(f"✅ PREVIEW TRACE: No session ID provided, but found a single session. Using session ID: {session_id}")
        else:
            print(f"❌ PREVIEW TRACE: Session ID '{session_id}' not found in SESSIONS.")
            return f"❌ Error: Session ID '{session_id}' not found. Please start a new session by creating an app."
    
    p_name = SESSIONS[session_id]
    print(f"✅ PREVIEW TRACE: Found project '{p_name}' for session '{session_id}'.")

    project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", p_name))
    if not os.path.isdir(project_dir):
        print(f"❌ PREVIEW TRACE: Project directory '{project_dir}' not found.")
        return f"❌ Error: Project directory '{p_name}' not found."
    
    print(f"✅ PREVIEW TRACE: Project directory is '{project_dir}'.")

    port = find_available_port()
    if port is None:
        print(f"❌ PREVIEW TRACE: No available ports.")
        return "❌ Error: All preview slots are currently in use. Please try again later."

    print(f"✅ PREVIEW TRACE: Found available port: {port}")

    # If the selected port is already in use, terminate the old process
    if ACTIVE_PREVIEWS.get(port) and ACTIVE_PREVIEWS[port].get('pid'):
        old_pid = ACTIVE_PREVIEWS[port]['pid']
        print(f"✅ PREVIEW TRACE: Terminating old server process with PID: {old_pid}")
        try:
            os.kill(old_pid, signal.SIGTERM)
        except ProcessLookupError:
            print(f"  -> Process {old_pid} not found.")
        except Exception as e:
            print(f"  -> Error killing process {old_pid}: {e}")

    try:
        server_cmd = ["python3", "-m", "http.server", str(port), "--directory", str(project_dir)]
        print(f"✅ PREVIEW TRACE: Starting server with command: {' '.join(server_cmd)}")
        server_proc = subprocess.Popen(server_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"✅ PREVIEW TRACE: Server process started with PID: {server_proc.pid}")
        
        ACTIVE_PREVIEWS[port]['pid'] = server_proc.pid
        ACTIVE_PREVIEWS[port]['project_name'] = p_name
        ACTIVE_PREVIEWS[port]['creation_time'] = time.time()
        print(f"✅ PREVIEW TRACE: Updated ACTIVE_PREVIEWS for port {port}: {ACTIVE_PREVIEWS[port]}")

        public_url = ACTIVE_PREVIEWS[port]['public_url']
        print(f"✅ PREVIEW TRACE: Found public URL: {public_url}")
        return f"✅ Preview is live at: {public_url}"
    except Exception as e:
        print(f"❌ PREVIEW TRACE: An unexpected error occurred: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return f"❌ An unexpected error occurred during preview creation: {e}"

@mcp.tool(
    description=RichToolDescription(
        description="Modifies an existing application based on user feedback.",
        use_when="ALWAYS use this tool when the user provides feedback or asks for changes to the app they just previewed. Keywords: change, modify, add, remove, update, make it, can you, what if, how about.",
        side_effects="Reads the existing HTML file, uses an LLM to apply the requested changes, and overwrites the file with the new version.",
    ).model_dump_json()
)
async def modify_app(
    feedback: Annotated[str, Field(description="The user's feedback describing the changes to make.")],
    session_id: Annotated[str, Field(description="The session ID for the user.")],
) -> str:
    if session_id not in SESSIONS:
        return "❌ Error: No active session found. Please create an app first."
    p_name = SESSIONS[session_id]
    project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", p_name))
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
        if details["project_name"] == p_name:
            preview_url = details.get('public_url')
            break

    if preview_url:
        return f"✅ I've applied your changes to '{p_name}'. You can see the updated version at {preview_url}"
    else:
        return f"✅ I've applied your changes to '{p_name}'. You can preview the app to see the changes."

@mcp.tool(description="Deploys a web application to a permanent public URL using Surge.sh.")
async def deploy_app(session_id: Annotated[str, Field(description="The session ID for the user.")]) -> str:
    if session_id not in SESSIONS:
        return "❌ Error: No active session found. Please create an app first."
    p_name = SESSIONS[session_id]
    project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", p_name))
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

async def log_ngrok_output(process):
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        print(f"NGROK: {line.strip()}")

async def start_ngrok_tunnels():
    print("--- NGROK TRACE: START ---")
    config_path = os.path.join(os.path.dirname(__file__), "ngrok.yml")
    if not os.path.exists(config_path):
        print(f"❌ NGROK TRACE: ngrok.yml not found at {config_path}")
        return

    print(f"✅ NGROK TRACE: Found ngrok.yml at {config_path}")
    command = ["ngrok", "start", "--all", "--config", config_path, "--log=stdout"]
    print(f"✅ NGROK TRACE: Running command: {' '.join(command)}")
    
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    print(f"✅ NGROK TRACE: ngrok process started with PID: {process.pid}")
    
    asyncio.create_task(log_ngrok_output(process))

    # Give ngrok time to start and establish tunnels
    await asyncio.sleep(10)

    # Retry mechanism for fetching tunnels
    for i in range(3):
        try:
            print(f"✅ NGROK TRACE: Fetching tunnels from ngrok API (attempt {i+1}/3)...")
            async with httpx.AsyncClient() as client:
                response = await client.get("http://127.0.0.1:4040/api/tunnels")
                response.raise_for_status()
                tunnels_data = response.json()
            print(f"✅ NGROK TRACE: ngrok API response: {tunnels_data}")

            for tunnel in tunnels_data.get("tunnels", []):
                if tunnel.get('name') == 'mcp-server':
                    print(f"\n\n🚀 MCP Server is live at: {tunnel['public_url']}/mcp\n\n")
                if tunnel['proto'] == 'https' and tunnel['name'].startswith('preview-'):
                    try:
                        port = urlparse(tunnel['config']['addr']).port
                        if port:
                            ACTIVE_PREVIEWS[port] = {
                                'public_url': tunnel['public_url'],
                                'project_name': None,
                                'pid': None,
                                'creation_time': None
                            }
                    except Exception as e:
                        print(f"❌ NGROK TRACE: Error parsing tunnel address: {e}")
            print(f"✅ NGROK TRACE: Found {len(ACTIVE_PREVIEWS)} active ngrok tunnels.")
            if ACTIVE_PREVIEWS:
                return # Success

        except httpx.RequestError as e:
            print(f"❌ NGROK TRACE: Could not connect to ngrok API to get tunnel info: {e}")
            if i < 2:
                print("   Retrying in 5 seconds...")
                await asyncio.sleep(5)
            else:
                print("   Please ensure the ngrok agent is running.")
        except Exception as e:
            print(f"❌ NGROK TRACE: An error occurred while setting up ngrok tunnels: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            break # Don't retry on other exceptions

    print("⚠️ NGROK TRACE: No ngrok tunnels were found after multiple attempts. Previews will not be available.")


async def main():
    await start_ngrok_tunnels()
    print("🚀 Streamable HTTP on http://0.0.0.0:7000/mcp (expects Accept: application/json, text/event-stream)")
    reaper = asyncio.create_task(reaper_task())
    server = mcp.run_async(transport="streamable-http", host="0.0.0.0", port=7000)
    await asyncio.gather(reaper, server)

if __name__ == "__main__":
    asyncio.run(main())