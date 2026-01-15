"""
Web Search Tool

Allows the agent to search the web for current information.
Uses SerpAPI for Google search results.
"""

import json
from typing import Dict, Any, Optional
from urllib.parse import quote_plus
from .base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    """
    Tool for searching the web.

    Supports:
    - Google web search via SerpAPI
    - Result summarization
    - Safe search filtering

    Requires SerpAPI API key set in WEB_SEARCH_API_KEY environment variable.
    """

    def __init__(self, api_key: str = None):
        """
        Initialize the web search tool.

        Args:
            api_key: SerpAPI API key. If not provided, tool will be disabled.
        """
        self.api_key = api_key
        self.enabled = bool(api_key)

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return """Search the web for current information.
Use this to find up-to-date documentation, news, or answers to questions.

Parameters:
- query: Search query string
- num_results: Number of results to return (default: 5, max: 10)

Returns summarized search results with titles, URLs, and snippets.
Only use when you need information not in your training data."""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5, max: 10)",
                    "minimum": 1,
                    "maximum": 10
                }
            },
            "required": ["query"]
        }

    def _search_with_serpapi(self, query: str, num_results: int = 5) -> ToolResult:
        """
        Perform search using SerpAPI.

        Args:
            query: Search query
            num_results: Number of results to return

        Returns:
            ToolResult with search results
        """
        try:
            import requests

            # SerpAPI endpoint
            url = "https://serpapi.com/search"
            params = {
                "q": query,
                "api_key": self.api_key,
                "num": num_results,
                "engine": "google"
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Extract organic results
            results = data.get("organic_results", [])
            if not results:
                return ToolResult.ok(
                    "No search results found.",
                    metadata={"query": query, "total_results": 0}
                )

            # Format results
            formatted_results = []
            for i, result in enumerate(results[:num_results], 1):
                title = result.get("title", "No title")
                link = result.get("link", "")
                snippet = result.get("snippet", "No description")
                formatted_results.append(
                    f"{i}. {title}\n   URL: {link}\n   {snippet}"
                )

            output = f"Search results for '{query}':\n\n" + "\n\n".join(formatted_results)

            return ToolResult.ok(
                output,
                metadata={
                    "query": query,
                    "total_results": len(results),
                    "returned_results": len(formatted_results)
                }
            )

        except requests.exceptions.RequestException as e:
            return ToolResult.fail(f"Search API request failed: {e}")
        except json.JSONDecodeError as e:
            return ToolResult.fail(f"Failed to parse search results: {e}")
        except Exception as e:
            return ToolResult.fail(f"Unexpected error during search: {e}")

    def _search_fallback(self, query: str) -> ToolResult:
        """
        Fallback search using simple Google search URL (no API).

        Args:
            query: Search query

        Returns:
            ToolResult with search suggestion
        """
        encoded_query = quote_plus(query)
        google_url = f"https://www.google.com/search?q={encoded_query}"
        return ToolResult.ok(
            f"Web search is not configured. To search for '{query}', visit:\n{google_url}\n\n"
            f"To enable automated search, set a WEB_SEARCH_API_KEY in your .env file.",
            metadata={"query": query, "fallback": True}
        )

    def execute(self, query: str, num_results: int = 5) -> ToolResult:
        """
        Execute a web search.

        Args:
            query: Search query
            num_results: Number of results to return (1-10)

        Returns:
            ToolResult with search results
        """
        if not self.enabled:
            return self._search_fallback(query)

        # Validate num_results
        if num_results < 1:
            num_results = 1
        elif num_results > 10:
            num_results = 10

        return self._search_with_serpapi(query, num_results)