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

# --- Preview Configuration ---
PREVIEW_PORT_RANGE = range(9000, 9002)
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

async def log_tunnel_output(process):
    """Logs the output of the tunnel process."""
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        print(f"TUNNEL: {line.decode().strip()}")

async def start_tunnels():
    """
    Starts tunnels to expose local servers to the internet.
    This function assumes a tunneling client is configured in the environment
    to start multiple tunnels.
    """
    print("--- Starting Port Forwarding Tunnels ---")

    command = ["ngrok", "start", "--all", "--log=stdout"]
    
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    asyncio.create_task(log_tunnel_output(process))

    # Give the tunneling service time to start and establish tunnels
    await asyncio.sleep(10)

    # Retry mechanism for fetching tunnels
    for i in range(3):
        try:
            async with httpx.AsyncClient() as client:
                # The ngrok agent API runs on localhost:4040 by default
                response = await client.get("http://127.0.0.1:4040/api/tunnels")
                response.raise_for_status()
                tunnels_data = response.json()

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
                        print(f"❌ Error parsing tunnel address: {e}")
            
            if ACTIVE_PREVIEWS:
                print(f"✅ Found {len(ACTIVE_PREVIEWS)} active port forwarding tunnels.")
                return # Success

        except httpx.RequestError as e:
            print(f"❌ Could not connect to forwarding agent API to get tunnel info: {e}")
            if i < 2:
                await asyncio.sleep(5)
            else:
                print("   Please ensure the forwarding agent is running and configured.")
        except Exception as e:
            print(f"❌ An error occurred while setting up forwarding tunnels: {e}")
            break

    print("⚠️ No forwarding tunnels were found after multiple attempts. Previews will not be available.")
