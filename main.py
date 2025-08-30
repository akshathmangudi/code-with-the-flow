"""
This is the main entry point for the Vibe Coder application.
It starts the Model Context Protocol (MCP) server and all background tasks.
"""
import asyncio
from src.tools import mcp
from src.subdomain_preview import start_tunnels, reaper_task, preview_manager

async def main():
    """
    Initializes and runs the application, including the MCP server and background tasks.
    """
    # Start the subdomain preview system
    await start_tunnels()
    
    print("🚀 Starting MCP Server on http://vibecode.akshath.tech:8086/mcp")
    print("🌐 Preview URLs will be available at: http://<project-name>.vibecode.akshath.tech")
    
    # Create and start the reaper task to clean up old previews.
    reaper = asyncio.create_task(reaper_task(preview_manager))
    
    # Start the MCP server on port 8086 (Puch standard)
    server = mcp.run_async(transport="streamable-http", host="0.0.0.0", port=8086)
    
    # Wait for all tasks to complete.
    await asyncio.gather(reaper, server)

if __name__ == "__main__":
    asyncio.run(main())
