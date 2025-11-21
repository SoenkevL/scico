"""The file to run the MCP server with the Tools"""

from dotenv import load_dotenv
from fastmcp import FastMCP

# Initializations
## load env
load_dotenv()
## Initialize the fastmcp class
mcp = FastMCP()

# Zotero
## Initialize the zotero_client
