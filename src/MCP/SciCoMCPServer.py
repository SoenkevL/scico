"""
SciCo MCP Server
Exposes SciCo tools via the Model Context Protocol for integration with LLMs.

Based on MCP best practices from:
- https://towardsdatascience.com/model-context-protocol-mcp-tutorial
- https://builder.aws.com/mcp-with-uv-in-python
"""

import asyncio
import json
from typing import Any, Callable
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import our tool classes
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.Tools.Zotero import Zotero
from src.utils.Logger import setup_logging

# Initialize logger
logger = logging.Logger(__name__)

class SciCoMCPServer:
    """
    Main MCP Server class that exposes SciCo tools following the Model Context Protocol.
    
    The MCP architecture enables AI models to interact with external tools through
    a standardized interface, maintaining context across interactions.
    """
    
    def __init__(self) -> None:
        """Initialize the MCP server and tool instances"""
        self.server = Server("scico-mcp-server")
        self.tool_instances: dict[str, Any] = {}
        self._initialize_tools()
        self._register_handlers()
        logger.info("SciCo MCP Server initialized")
    
    def _initialize_tools(self) -> None:
        """
        Initialize all tool instances.
        
        This method creates instances of all available tools that will be
        exposed through the MCP interface.
        """
        try:
            self.tool_instances['zotero'] = Zotero()
            logger.info("Zotero tool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Zotero tool: {e}")
            raise
    
    def _register_handlers(self) -> None:
        """
        Register MCP protocol handlers using decorators.
        
        This follows the MCP pattern of using decorators to define
        server capabilities (list_tools, call_tool, etc.)
        """
        
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """
            List all available tools.
            
            Returns tool definitions with JSON schemas that describe
            their inputs and outputs to the AI model.
            """
            logger.info("Listing available tools")
            return [
                Tool(
                    name="zotero_get_item_count",
                    description=(
                        "Returns the total number of items in the user's Zotero library. "
                        "Useful for getting an overview of the library size."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                Tool(
                    name="zotero_get_all_collections",
                    description=(
                        "Returns a dictionary of all collections in the Zotero Library. "
                        "The dictionary maps collection names (keys) to their IDs (values). "
                        "Useful for navigating the library structure."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """
            Execute a tool and return results.
            
            This is an async handler that processes tool calls from the AI model,
            executes the appropriate function, and returns structured results.
            
            Args:
                name: The name of the tool to execute
                arguments: Dictionary of arguments to pass to the tool
                
            Returns:
                List of TextContent with JSON-encoded results
            """
            logger.info(f"Executing tool: {name} with arguments: {arguments}")
            
            zotero_instance = self.tool_instances['zotero']
            
            try:
                if name == "zotero_get_item_count":
                    result = zotero_instance.get_item_count()
                    logger.info(f"Retrieved item count: {result}")
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "success": True,
                            "item_count": result,
                            "message": f"Found {result} items in Zotero library"
                        })
                    )]
                
                elif name == "zotero_get_all_collections":
                    result = zotero_instance.get_all_collections()
                    logger.info(f"Retrieved {len(result)} collections")
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "success": True,
                            "collections": result,
                            "count": len(result),
                            "message": f"Found {len(result)} collections"
                        })
                    )]
                
                else:
                    error_msg = f"Unknown tool: {name}"
                    logger.error(error_msg)
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "success": False,
                            "error": error_msg
                        })
                    )]
                    
            except Exception as e:
                error_msg = f"Error executing {name}: {str(e)}"
                logger.error(error_msg)
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": error_msg
                    })
                )]
    
    async def run(self) -> None:
        """
        Run the MCP server using stdio transport.
        
        This follows the standard MCP pattern of using stdin/stdout for
        communication, which is the recommended approach for MCP servers.
        """
        logger.info("Starting SciCo MCP Server...")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main() -> None:
    """Main entry point for the MCP server"""
    try:
        server = SciCoMCPServer()
        await server.run()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
