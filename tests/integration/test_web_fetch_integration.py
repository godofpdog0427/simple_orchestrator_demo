"""Integration tests for WebFetchTool with real HTTP requests."""

import pytest

from orchestrator.tools.builtin.web_fetch import WebFetchTool


@pytest.fixture
def web_fetch_tool():
    """Create a WebFetchTool instance for testing."""
    config = {
        "timeout_seconds": 30,
        "max_response_size_mb": 5,
        "follow_redirects": True,
        "max_redirects": 10,
        "user_agent": "TestAgent/1.0",
        "allowed_schemes": ["http", "https"],
        "blocked_domains": [],
    }
    return WebFetchTool(config)


@pytest.mark.integration
@pytest.mark.asyncio
class TestWebFetchToolRealRequests:
    """Integration tests with real HTTP requests to httpbin.org."""

    async def test_fetch_html_page(self, web_fetch_tool):
        """Test fetching a real HTML page."""
        result = await web_fetch_tool.execute("https://httpbin.org/html")

        assert result.success is True
        assert result.data["status_code"] == 200
        assert "html" in result.data["content_type"].lower()
        # HTML should be parsed to text
        assert "<html>" not in result.data["content"]
        assert result.metadata["parsed_html"] is True

    async def test_fetch_json_endpoint(self, web_fetch_tool):
        """Test fetching JSON data."""
        result = await web_fetch_tool.execute(
            "https://httpbin.org/json", parse_html=False
        )

        assert result.success is True
        assert result.data["status_code"] == 200
        assert "json" in result.data["content_type"].lower()
        # JSON should not be parsed as HTML
        assert result.metadata["parsed_html"] is False

    async def test_follow_redirects(self, web_fetch_tool):
        """Test that redirects are followed correctly."""
        # httpbin.org/redirect/2 redirects twice before returning 200
        result = await web_fetch_tool.execute("https://httpbin.org/redirect/2")

        assert result.success is True
        assert result.data["status_code"] == 200
        assert result.metadata["redirects"] == 2
        # Final URL should be different from original
        assert "redirect/2" not in result.data["url"]

    async def test_http_404_not_found(self, web_fetch_tool):
        """Test handling of HTTP 404 error."""
        result = await web_fetch_tool.execute("https://httpbin.org/status/404")

        assert result.success is False
        assert "404" in result.error
        assert result.metadata["status_code"] == 404

    async def test_http_500_server_error(self, web_fetch_tool):
        """Test handling of HTTP 500 error."""
        result = await web_fetch_tool.execute("https://httpbin.org/status/500")

        assert result.success is False
        assert "500" in result.error
        assert result.metadata["status_code"] == 500

    async def test_fetch_with_delay(self, web_fetch_tool):
        """Test fetching a page with delay (should succeed within timeout)."""
        # httpbin.org/delay/2 waits 2 seconds before responding
        result = await web_fetch_tool.execute("https://httpbin.org/delay/2")

        assert result.success is True
        assert result.data["status_code"] == 200
        # Response time should be > 2000ms
        assert result.metadata["response_time_ms"] >= 2000

    async def test_parse_html_vs_raw(self, web_fetch_tool):
        """Test difference between parsed and raw HTML."""
        url = "https://httpbin.org/html"

        # Fetch with HTML parsing
        result_parsed = await web_fetch_tool.execute(url, parse_html=True)
        # Fetch without HTML parsing
        result_raw = await web_fetch_tool.execute(url, parse_html=False)

        assert result_parsed.success is True
        assert result_raw.success is True

        # Parsed version should not contain HTML tags
        assert "<html>" not in result_parsed.data["content"]
        assert "<body>" not in result_parsed.data["content"]

        # Raw version should contain HTML tags
        assert "<html>" in result_raw.data["content"]
        assert "<body>" in result_raw.data["content"]

    async def test_user_agent_header(self, web_fetch_tool):
        """Test that User-Agent header is sent correctly."""
        # httpbin.org/user-agent returns the user agent used
        result = await web_fetch_tool.execute(
            "https://httpbin.org/user-agent", parse_html=False
        )

        assert result.success is True
        assert "TestAgent/1.0" in result.data["content"]

    async def test_get_request(self, web_fetch_tool):
        """Test explicit GET request."""
        result = await web_fetch_tool.execute(
            "https://httpbin.org/get", method="GET", parse_html=False
        )

        assert result.success is True
        assert result.data["status_code"] == 200
        # Response should indicate GET method was used
        assert '"url"' in result.data["content"]

    async def test_post_request(self, web_fetch_tool):
        """Test POST request."""
        result = await web_fetch_tool.execute(
            "https://httpbin.org/post", method="POST", parse_html=False
        )

        assert result.success is True
        assert result.data["status_code"] == 200
        # Response should indicate POST method was used
        assert '"url"' in result.data["content"]


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
class TestWebFetchToolEdgeCases:
    """Integration tests for edge cases (slow tests)."""

    async def test_very_long_timeout(self, web_fetch_tool):
        """Test fetching page with very long delay (should timeout)."""
        # Configure tool with short timeout
        config = {
            "timeout_seconds": 5,  # 5 second timeout
            "max_response_size_mb": 5,
            "follow_redirects": True,
            "max_redirects": 10,
            "user_agent": "TestAgent/1.0",
            "allowed_schemes": ["http", "https"],
            "blocked_domains": [],
        }
        tool = WebFetchTool(config)

        # httpbin.org/delay/10 waits 10 seconds (longer than timeout)
        result = await tool.execute("https://httpbin.org/delay/10")

        assert result.success is False
        assert "timed out" in result.error.lower()

    async def test_too_many_redirects(self, web_fetch_tool):
        """Test handling of too many redirects."""
        # Configure tool with low redirect limit
        config = {
            "timeout_seconds": 30,
            "max_response_size_mb": 5,
            "follow_redirects": True,
            "max_redirects": 2,  # Only allow 2 redirects
            "user_agent": "TestAgent/1.0",
            "allowed_schemes": ["http", "https"],
            "blocked_domains": [],
        }
        tool = WebFetchTool(config)

        # httpbin.org/redirect/5 redirects 5 times (more than limit)
        result = await tool.execute("https://httpbin.org/redirect/5")

        assert result.success is False
        assert "redirect" in result.error.lower()
