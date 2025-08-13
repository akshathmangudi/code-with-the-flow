"""
This is the main entry point for the Vibe Coder application.
It starts the Model Context Protocol (MCP) server and all background tasks.
"""
import asyncio
from src.tools import mcp
from src.preview import start_tunnels, reaper_task

async def main():
    """
    Initializes and runs the application, including the MCP server and background tasks.
    """
    # Start the port forwarding tunnels.
    await start_tunnels()
    
    print("🚀 Starting MCP Server on http://0.0.0.0:8000/mcp")
    
    # Create and start the reaper task to clean up old previews.
    reaper = asyncio.create_task(reaper_task())
    
    # Start the MCP server.
    server = mcp.run_async(transport="streamable-http", host="0.0.0.0", port=8000)
    
    # Wait for all tasks to complete.
    await asyncio.gather(reaper, server)

if __name__ == "__main__":
    asyncio.run(main())
