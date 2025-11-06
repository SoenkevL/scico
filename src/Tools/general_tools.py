import logging

from langchain.tools import tool

logger = logging.getLogger(__name__)


# ===== Tool Definitions =====

@tool
def final_answer(finalanswer: str) -> str:
    """Returns the final answer. Use this as the last message once every other step is done. You want to provide the last answer to the user"""
    return finalanswer


@tool
def think(thought: str) -> str:
    """Use this tool whenever you want to check your history and reason on what the best next step is. Take time to sort yourself out!"""
    return thought
