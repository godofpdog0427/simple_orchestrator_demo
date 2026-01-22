"""Unit tests for WebFetchTool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from orchestrator.tools.builtin.web_fetch import WebFetchTool
from orchestrator.tools.base import ToolResult


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
        "blocked_domains": ["blocked.com"],
    }
    return WebFetchTool(config)


class TestWebFetchToolValidation:
    """Test URL validation."""

    def test_valid_http_url(self, web_fetch_tool):
        """Test validation of valid HTTP URL."""
        error = web_fetch_tool._validate_url("http://example.com")
        assert error is None

    def test_valid_https_url(self, web_fetch_tool):
        """Test validation of valid HTTPS URL."""
        error = web_fetch_tool._validate_url("https://example.com")
        assert error is None

    def test_invalid_scheme(self, web_fetch_tool):
        """Test validation rejects unsupported schemes."""
        error = web_fetch_tool._validate_url("ftp://example.com")
        assert error is not None
        assert "not allowed" in error.lower()

    def test_blocked_domain(self, web_fetch_tool):
        """Test validation rejects blocked domains."""
        error = web_fetch_tool._validate_url("https://blocked.com/page")
        assert error is not None
        assert "blocked" in error.lower()

    def test_missing_domain(self, web_fetch_tool):
        """Test validation rejects URLs without domain."""
        error = web_fetch_tool._validate_url("https://")
        assert error is not None
        assert "missing domain" in error.lower()


class TestWebFetchToolHTMLParsing:
    """Test HTML parsing functionality."""

    def test_parse_simple_html(self, web_fetch_tool):
        """Test parsing simple HTML."""
        html = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Hello World</h1>
                <p>This is a test.</p>
            </body>
        </html>
        """
        result = web_fetch_tool._parse_html(html)

        assert "Title: Test Page" in result
        assert "Hello World" in result
        assert "This is a test." in result

    def test_parse_html_removes_scripts(self, web_fetch_tool):
        """Test that scripts are removed during parsing."""
        html = """
        <html>
            <head><title>Test</title></head>
            <body>
                <p>Content</p>
                <script>alert('evil');</script>
            </body>
        </html>
        """
        result = web_fetch_tool._parse_html(html)

        assert "Content" in result
        assert "script" not in result.lower()
        assert "alert" not in result

    def test_parse_html_removes_styles(self, web_fetch_tool):
        """Test that styles are removed during parsing."""
        html = """
        <html>
            <head>
                <title>Test</title>
                <style>body { color: red; }</style>
            </head>
            <body><p>Content</p></body>
        </html>
        """
        result = web_fetch_tool._parse_html(html)

        assert "Content" in result
        assert "color: red" not in result

    def test_parse_html_with_meta_description(self, web_fetch_tool):
        """Test extraction of meta description."""
        html = """
        <html>
            <head>
                <title>Test</title>
                <meta name="description" content="This is a test page">
            </head>
            <body><p>Content</p></body>
        </html>
        """
        result = web_fetch_tool._parse_html(html)

        assert "Description: This is a test page" in result


@pytest.mark.asyncio
class TestWebFetchToolExecution:
    """Test tool execution with mocked HTTP responses."""

    async def test_successful_get_request(self, web_fetch_tool):
        """Test successful GET request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Test Content</body></html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.url = "https://example.com"
        mock_response.history = []
        mock_response.content = b"Test Content"
        mock_response.reason_phrase = "OK"

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            result = await web_fetch_tool.execute("https://example.com")

            assert result.success is True
            assert result.data["status_code"] == 200
            assert "Test Content" in result.data["content"]
            assert result.data["url"] == "https://example.com"

    async def test_http_404_error(self, web_fetch_tool):
        """Test handling of HTTP 404 error."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.reason_phrase = "Not Found"
        mock_response.headers = {}
        mock_response.url = "https://example.com/notfound"
        mock_response.history = []

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            result = await web_fetch_tool.execute("https://example.com/notfound")

            assert result.success is False
            assert "404" in result.error
            assert result.metadata["status_code"] == 404

    async def test_connection_error(self, web_fetch_tool):
        """Test handling of connection errors."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_instance.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client.return_value = mock_instance

            result = await web_fetch_tool.execute("https://example.com")

            assert result.success is False
            assert "connection error" in result.error.lower()

    async def test_timeout_error(self, web_fetch_tool):
        """Test handling of timeout errors."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_instance.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.return_value = mock_instance

            result = await web_fetch_tool.execute("https://example.com")

            assert result.success is False
            assert "timed out" in result.error.lower()

    async def test_invalid_url_returns_error(self, web_fetch_tool):
        """Test that invalid URL returns error without making request."""
        result = await web_fetch_tool.execute("ftp://example.com")

        assert result.success is False
        assert "not allowed" in result.error.lower()

    async def test_parse_html_flag(self, web_fetch_tool):
        """Test that parse_html parameter controls HTML parsing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><p>Test</p></body></html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.url = "https://example.com"
        mock_response.history = []
        mock_response.content = b"<html><body><p>Test</p></body></html>"
        mock_response.reason_phrase = "OK"

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            # With parsing (default)
            result_parsed = await web_fetch_tool.execute("https://example.com", parse_html=True)
            assert "<p>" not in result_parsed.data["content"]
            assert "Test" in result_parsed.data["content"]

            # Without parsing
            result_raw = await web_fetch_tool.execute("https://example.com", parse_html=False)
            assert "<p>Test</p>" in result_raw.data["content"]


class TestWebFetchToolDefinition:
    """Test tool definition and metadata."""

    def test_tool_definition(self, web_fetch_tool):
        """Test that tool definition is correctly configured."""
        definition = web_fetch_tool.definition

        assert definition.name == "web_fetch"
        assert definition.category == "web"
        assert len(definition.parameters) == 3

        # Check parameters
        param_names = [p.name for p in definition.parameters]
        assert "url" in param_names
        assert "method" in param_names
        assert "parse_html" in param_names

    def test_url_parameter_required(self, web_fetch_tool):
        """Test that url parameter is required."""
        url_param = next(
            p for p in web_fetch_tool.definition.parameters if p.name == "url"
        )
        assert url_param.required is True

    def test_method_parameter_enum(self, web_fetch_tool):
        """Test that method parameter has correct enum values."""
        method_param = next(
            p for p in web_fetch_tool.definition.parameters if p.name == "method"
        )
        assert method_param.enum == ["GET", "POST"]
        assert method_param.required is False
