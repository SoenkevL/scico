"""The file to run the MCP server with the Tools"""

import Notion_MCP, Zotero_MCP, GitHub_MCP, TextSplitter, VectorStorage_MCP, PdfToMarkdown
from fastmcp import FastMCP
from dotenv import load_dotenv


#Initializations
## load env
load_dotenv()
## Initialize the fastmcp class
mcp = FastMCP()

# Zotero
## Initialize the zotero_client