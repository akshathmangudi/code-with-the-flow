"""
This module handles the creation and management of live application previews.
It manages a pool of ports, starts and stops local web servers, and handles
the lifecycle of preview environments, including automatic cleanup of old previews.
"""
import asyncio
import os
import signal
import time
import httpx
from urllib.parse import urlparse
import re
import json

# --- Preview Configuration ---
PREVIEW_PORT_RANGE = range(8000, 8021)
ACTIVE_PREVIEWS = {}  # {port: {'pid': ..., 'project_name': ..., 'creation_time': ..., 'public_url': ...}}

def find_available_port() -> int | None:
    """
    Finds an available port for a new preview.
    If all ports are in use, it returns the port of the oldest preview to be replaced.

    Returns:
        An integer representing the available port, or None if no ports are configured.
    """
    # First, look for a completely empty slot
    for port in PREVIEW_PORT_RANGE:
        if port not in ACTIVE_PREVIEWS or ACTIVE_PREVIEWS[port].get('project_name') is None:
            if port not in ACTIVE_PREVIEWS:
                 ACTIVE_PREVIEWS[port] = {}
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
    """
    A background task that periodically stops old and unused preview servers.

    Args:
        cleanup_interval_seconds: The interval at which to run the cleanup task.
        max_lifetime_seconds: The maximum time a preview can live before being cleaned up.
    """
    while True:
        await asyncio.sleep(cleanup_interval_seconds)
        now = time.time()
        for port, details in list(ACTIVE_PREVIEWS.items()):
            if details.get('project_name') and (now - details.get("creation_time", 0)) > max_lifetime_seconds:
                print(f"🧹 Reaper: stopping preview for {details['project_name']} on port {port} (PID {details['pid']})")
                try:
                    if details['pid']:
                        os.kill(details["pid"], signal.SIGTERM)
                        print(f"  -> Process {details['pid']} terminated.")
                except ProcessLookupError:
                    print(f"  -> Process {details['pid']} not found.")
                except Exception as e:
                    print(f"  -> Error killing process {details['pid']}: {e}")
                ACTIVE_PREVIEWS[port]['project_name'] = None
                ACTIVE_PREVIEWS[port]['pid'] = None
                ACTIVE_PREVIEWS[port]['creation_time'] = None
                
async def _start_one_cloudflared_tunnel(port: int):
    """
    Starts a single cloudflared tunnel and returns its public URL and process.
    """
    command = ["cloudflared", "tunnel", "--url", f"http://localhost:{port}", "--output", "json"]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    url_pattern = re.compile(r"https?://[a-zA-Z0-9-]+\.trycloudflare\.com")
    
    # Try to read the stderr for a few seconds to find the URL
    for _ in range(10):
        line_bytes = await process.stderr.readline()
        if not line_bytes:
            await asyncio.sleep(0.5)
            continue
        
        line = line_bytes.decode('utf-8').strip()
        # The URL is in a JSON log line
        try:
            log_entry = json.loads(line)
            if log_entry.get("message") == "Connected to":
                match = url_pattern.search(log_entry.get("url", ""))
                if match:
                    public_url = match.group(0)
                    print(f"✅ Started cloudflared tunnel for port {port} at {public_url}")
                    ACTIVE_PREVIEWS[port] = {
                        'public_url': public_url,
                        'project_name': None,
                        'pid': process.pid,
                        'creation_time': None
                    }
                    return
        except (json.JSONDecodeError, KeyError):
            # If we get a non-JSON line, it's probably an error.
            print(f"❌ cloudflared failed to start for port {port}.")
            print(f"   Error: {line}")
            
            # Check for common login issue
            if "failed to unmarshal quick Tunnel" in line:
                print("\n💡 Hint: This error often means you are not logged into Cloudflare.")
                print("   Please run `cloudflared tunnel login` in your terminal and follow the instructions.")

            # Ensure the process is terminated before returning
            if process.returncode is None:
                try:
                    process.terminate()
                    await process.wait()
                except ProcessLookupError:
                    pass # Process already terminated
            return # Exit the function for this port

    # If we get here, the tunnel failed to start (timeout)
    print(f"❌ Failed to start cloudflared tunnel for port {port} (timed out waiting for URL)")
    if process.returncode is None:
        try:
            process.terminate()
            await process.wait()
        except ProcessLookupError:
            pass # Process already terminated

async def start_tunnels():
    """
    Starts a cloudflared tunnel for each port in the configured preview range.
    """
    print("--- Starting Port Forwarding Tunnels (cloudflared) ---")
    
    # Create a task for each tunnel we need to start
    tasks = [_start_one_cloudflared_tunnel(port) for port in PREVIEW_PORT_RANGE]
    await asyncio.gather(*tasks)

    if any(p.get('public_url') for p in ACTIVE_PREVIEWS.values()):
        print(f"✅ Found {len([p for p in ACTIVE_PREVIEWS.values() if p.get('public_url')])} active port forwarding tunnels.")
    else:
        print("⚠️ No forwarding tunnels could be established. Previews will not be available.")
