"""Web fetch tool for HTTP/HTTPS requests and HTML parsing."""

import asyncio
import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from orchestrator.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


class WebFetchTool(Tool):
    """Tool for fetching web content via HTTP/HTTPS."""

    def __init__(self, config: dict) -> None:
        """
        Initialize web fetch tool.

        Args:
            config: Tool configuration dictionary
        """
        self.config = config
        self.timeout_seconds = config.get("timeout_seconds", 30)
        self.max_response_size_mb = config.get("max_response_size_mb", 5)
        self.follow_redirects = config.get("follow_redirects", True)
        self.max_redirects = config.get("max_redirects", 10)
        self.user_agent = config.get("user_agent", "SimpleOrchestrator/1.0")
        self.allowed_schemes = config.get("allowed_schemes", ["http", "https"])
        self.blocked_domains = config.get("blocked_domains", [])

        # Define tool metadata
        self.definition = ToolDefinition(
            name="web_fetch",
            description=(
                "Fetch content from a URL via HTTP/HTTPS. "
                "Can parse HTML to plain text or return raw content. "
                "Useful for accessing web pages, APIs, documentation, etc."
            ),
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="URL to fetch (must start with http:// or https://)",
                    required=True,
                ),
                ToolParameter(
                    name="method",
                    type="string",
                    description="HTTP method to use (GET or POST)",
                    required=False,
                    enum=["GET", "POST"],
                ),
                ToolParameter(
                    name="parse_html",
                    type="boolean",
                    description=(
                        "Parse HTML content to plain text, removing scripts and styles. "
                        "Set to false to get raw HTML/content. Default: true"
                    ),
                    required=False,
                ),
            ],
            requires_approval=config.get("requires_approval", False),
            timeout_seconds=self.timeout_seconds,
            category="web",
        )

    async def execute(
        self, url: str, method: str = "GET", parse_html: bool = True
    ) -> ToolResult:
        """
        Execute web fetch operation.

        Args:
            url: URL to fetch
            method: HTTP method (GET or POST)
            parse_html: Whether to parse HTML to plain text

        Returns:
            ToolResult with fetched content and metadata
        """
        # Validate URL
        validation_error = self._validate_url(url)
        if validation_error:
            return ToolResult(success=False, error=validation_error)

        # Record start time
        start_time = time.time()

        try:
            # Fetch content
            async with httpx.AsyncClient(
                follow_redirects=self.follow_redirects,
                max_redirects=self.max_redirects,
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout_seconds,
            ) as client:
                # Make request with timeout
                try:
                    if method == "GET":
                        response = await asyncio.wait_for(
                            client.get(url), timeout=self.timeout_seconds
                        )
                    elif method == "POST":
                        response = await asyncio.wait_for(
                            client.post(url), timeout=self.timeout_seconds
                        )
                    else:
                        return ToolResult(
                            success=False, error=f"Unsupported HTTP method: {method}"
                        )

                except asyncio.TimeoutError:
                    return ToolResult(
                        success=False,
                        error=f"Request timed out after {self.timeout_seconds} seconds",
                    )

                # Calculate response time
                response_time_ms = int((time.time() - start_time) * 1000)

                # Check response size
                content_length = response.headers.get("content-length")
                if content_length:
                    size_mb = int(content_length) / (1024 * 1024)
                    if size_mb > self.max_response_size_mb:
                        return ToolResult(
                            success=False,
                            error=(
                                f"Response size ({size_mb:.2f}MB) exceeds "
                                f"maximum allowed ({self.max_response_size_mb}MB)"
                            ),
                        )

                # Handle HTTP errors
                if response.status_code >= 400:
                    error_type = "Client error" if response.status_code < 500 else "Server error"
                    return ToolResult(
                        success=False,
                        error=f"HTTP {response.status_code}: {error_type} - {response.reason_phrase}",
                        metadata={
                            "status_code": response.status_code,
                            "url": str(response.url),
                            "response_time_ms": response_time_ms,
                        },
                    )

                # Get content
                content = response.text
                content_type = response.headers.get("content-type", "")

                # Parse HTML if requested
                if parse_html and "html" in content_type.lower():
                    content = self._parse_html(content)

                # Count redirects
                redirect_count = len(response.history)

                logger.info(
                    f"Fetched {url} - Status: {response.status_code}, "
                    f"Size: {len(content)} chars, Time: {response_time_ms}ms, "
                    f"Redirects: {redirect_count}"
                )

                return ToolResult(
                    success=True,
                    data={
                        "content": content,
                        "url": str(response.url),  # Final URL after redirects
                        "status_code": response.status_code,
                        "content_type": content_type,
                    },
                    metadata={
                        "response_time_ms": response_time_ms,
                        "redirects": redirect_count,
                        "size_bytes": len(response.content),
                        "parsed_html": parse_html and "html" in content_type.lower(),
                    },
                )

        except httpx.ConnectError as e:
            logger.error(f"Connection error fetching {url}: {e}")
            return ToolResult(
                success=False,
                error=f"Connection error: Could not connect to {urlparse(url).netloc}",
            )

        except httpx.TimeoutException as e:
            logger.error(f"Timeout fetching {url}: {e}")
            return ToolResult(
                success=False,
                error=f"Request timed out after {self.timeout_seconds} seconds",
            )

        except httpx.TooManyRedirects:
            return ToolResult(
                success=False,
                error=f"Too many redirects (max: {self.max_redirects})",
            )

        except Exception as e:
            logger.error(f"Error fetching {url}: {e}", exc_info=True)
            return ToolResult(success=False, error=f"Fetch error: {str(e)}")

    def _validate_url(self, url: str) -> str | None:
        """
        Validate URL format and security constraints.

        Args:
            url: URL to validate

        Returns:
            Error message if invalid, None if valid
        """
        try:
            parsed = urlparse(url)

            # Check scheme
            if parsed.scheme not in self.allowed_schemes:
                return (
                    f"URL scheme '{parsed.scheme}' not allowed. "
                    f"Allowed schemes: {', '.join(self.allowed_schemes)}"
                )

            # Check for blocked domains
            if parsed.netloc in self.blocked_domains:
                return f"Domain blocked by configuration: {parsed.netloc}"

            # Check URL has netloc (domain)
            if not parsed.netloc:
                return "Invalid URL: missing domain"

            return None

        except Exception as e:
            return f"Invalid URL format: {str(e)}"

    def _parse_html(self, html: str) -> str:
        """
        Parse HTML to plain text, removing scripts and styles.

        Args:
            html: Raw HTML content

        Returns:
            Cleaned plain text
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Remove unwanted tags
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            # Extract title
            title = soup.find("title")
            title_text = title.get_text(strip=True) if title else ""

            # Extract meta description
            meta_desc = soup.find("meta", attrs={"name": "description"})
            description = ""
            if meta_desc and meta_desc.get("content"):
                description = meta_desc["content"]

            # Extract body text
            body = soup.find("body")
            if body:
                text = body.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)

            # Clean up whitespace
            lines = [line.strip() for line in text.split("\n")]
            lines = [line for line in lines if line]  # Remove empty lines
            text = "\n".join(lines)

            # Build final text with metadata
            result_parts = []

            if title_text:
                result_parts.append(f"Title: {title_text}")
            if description:
                result_parts.append(f"Description: {description}")
            if result_parts:
                result_parts.append("")  # Empty line separator

            result_parts.append(text)

            return "\n".join(result_parts)

        except Exception as e:
            logger.warning(f"Error parsing HTML: {e}")
            # Return raw HTML if parsing fails
            return html
