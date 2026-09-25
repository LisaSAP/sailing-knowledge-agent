"""Standalone MCP server for the sailing KG.

The DB lives next to this file (.cognee_system, .data_storage).
No imports from the MVP package needed.
"""
import asyncio
import os
import sys
import logging
import pathlib

# Redirect all stdout logging to stderr so stdio MCP protocol is not polluted
logging.getLogger().handlers = []
logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
os.environ.setdefault("LOG_LEVEL", "WARNING")

ROOT = pathlib.Path(__file__).resolve().parent   # knowledgegraph/

from dotenv import load_dotenv
load_dotenv(ROOT.parent / ".env", override=True)  # sailing-knowledge-agent/.env

os.environ["COGNEE_LOG_LEVEL"] = "ERROR"
import litellm
litellm.headers = {**(litellm.headers or {}), **{
    k: v for k, v in [
        h.split(":", 1) for h in os.environ.get("LITELLM_EXTRA_HEADERS_RAW", "").split(",") if ":" in h
    ]
}} if os.environ.get("LITELLM_EXTRA_HEADERS_RAW") else litellm.headers
_langfuse_tags = os.environ.get("LANGFUSE_TAGS_INJECT")
if _langfuse_tags:
    litellm.headers = {**(litellm.headers or {}), "x-langfuse-tags": _langfuse_tags}
import cognee
from cognee.api.v1.search import SearchType

# Point cognee at the DB directories next to this file
cognee.config.system_root_directory(str(ROOT / ".cognee_system"))
cognee.config.data_root_directory(str(ROOT / ".data_storage"))

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("sailing-kg")


def query_kg(question: str) -> str:
    async def _search():
        results = await cognee.search(
            query_type=SearchType.GRAPH_COMPLETION,
            query_text=question,
        )
        return "\n".join(
            r if isinstance(r, str) else getattr(r, "text", str(r))
            for r in results
        )
    return asyncio.run(_search())


@mcp.tool()
def search_kg(question: str) -> str:
    """Search the sailing knowledge graph for race performance insights.

    Args:
        question: A natural-language question about sailing race data,
                  e.g. "Why did Burling perform well on Leg 2?"
    """
    return query_kg(question)


if __name__ == "__main__":
    mcp.run(transport="stdio")
