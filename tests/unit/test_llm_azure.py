"""Unit tests for Azure Anthropic provider."""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from orchestrator.llm.client import (
    AzureAnthropicProvider,
    LLMClient,
    LLMResponse,
    StreamChunk,
)


class TestAzureAnthropicProvider:
    """Test AzureAnthropicProvider class."""

    def test_init_requires_endpoint(self):
        """Test that endpoint is required."""
        with patch.dict(os.environ, {"AZURE_ANTHROPIC_API_KEY": "test-key"}):
            with pytest.raises(ValueError, match="endpoint is required"):
                AzureAnthropicProvider({"deployment_name": "test"})

    def test_init_requires_deployment_name(self):
        """Test that deployment_name is required."""
        with patch.dict(os.environ, {"AZURE_ANTHROPIC_API_KEY": "test-key"}):
            with pytest.raises(ValueError, match="deployment_name is required"):
                AzureAnthropicProvider(
                    {"endpoint": "https://test.azure.com/anthropic/"}
                )

    def test_init_requires_api_key(self):
        """Test that API key environment variable is required."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear any existing key
            if "AZURE_ANTHROPIC_API_KEY" in os.environ:
                del os.environ["AZURE_ANTHROPIC_API_KEY"]

            with pytest.raises(ValueError, match="API key not found"):
                AzureAnthropicProvider(
                    {
                        "endpoint": "https://test.azure.com/anthropic/",
                        "deployment_name": "claude-sonnet-4-5",
                    }
                )

    @patch("anthropic.AsyncAnthropic")
    def test_init_with_valid_config(self, mock_anthropic):
        """Test successful initialization with valid config."""
        with patch.dict(os.environ, {"AZURE_ANTHROPIC_API_KEY": "test-key"}):
            provider = AzureAnthropicProvider(
                {
                    "endpoint": "https://test.azure.com/anthropic/",
                    "deployment_name": "claude-sonnet-4-5",
                    "max_tokens": 4096,
                    "temperature": 0.5,
                }
            )

            assert provider.endpoint == "https://test.azure.com/anthropic/"
            assert provider.deployment_name == "claude-sonnet-4-5"
            assert provider.model == "claude-sonnet-4-5"
            assert provider.max_tokens == 4096
            assert provider.temperature == 0.5

            # Verify AsyncAnthropic was called with base_url
            mock_anthropic.assert_called_once_with(
                api_key="test-key",
                base_url="https://test.azure.com/anthropic/",
            )

    @patch("anthropic.AsyncAnthropic")
    def test_init_custom_api_key_env(self, mock_anthropic):
        """Test initialization with custom API key environment variable."""
        with patch.dict(os.environ, {"MY_AZURE_KEY": "custom-key"}):
            provider = AzureAnthropicProvider(
                {
                    "endpoint": "https://test.azure.com/anthropic/",
                    "deployment_name": "claude-sonnet-4-5",
                    "api_key_env": "MY_AZURE_KEY",
                }
            )

            assert provider.api_key == "custom-key"
            mock_anthropic.assert_called_once_with(
                api_key="custom-key",
                base_url="https://test.azure.com/anthropic/",
            )

    @patch("anthropic.AsyncAnthropic")
    def test_init_default_values(self, mock_anthropic):
        """Test default values for optional config."""
        with patch.dict(os.environ, {"AZURE_ANTHROPIC_API_KEY": "test-key"}):
            provider = AzureAnthropicProvider(
                {
                    "endpoint": "https://test.azure.com/anthropic/",
                    "deployment_name": "claude-sonnet-4-5",
                }
            )

            # Default values
            assert provider.max_tokens == 4096
            assert provider.temperature == 0.7
            assert provider.max_retries == 5
            assert provider.base_delay == 2.0
            assert provider.max_delay == 60.0
            assert provider.exponential_base == 2.0
            assert provider.throttle_enabled is False
            assert provider.min_request_interval == 0.5

    @patch("anthropic.AsyncAnthropic")
    def test_init_retry_config(self, mock_anthropic):
        """Test retry configuration."""
        with patch.dict(os.environ, {"AZURE_ANTHROPIC_API_KEY": "test-key"}):
            provider = AzureAnthropicProvider(
                {
                    "endpoint": "https://test.azure.com/anthropic/",
                    "deployment_name": "claude-sonnet-4-5",
                    "retry": {
                        "max_retries": 3,
                        "base_delay": 1.0,
                        "max_delay": 30.0,
                        "exponential_base": 1.5,
                    },
                }
            )

            assert provider.max_retries == 3
            assert provider.base_delay == 1.0
            assert provider.max_delay == 30.0
            assert provider.exponential_base == 1.5

    @patch("anthropic.AsyncAnthropic")
    def test_init_throttle_config(self, mock_anthropic):
        """Test throttle configuration."""
        with patch.dict(os.environ, {"AZURE_ANTHROPIC_API_KEY": "test-key"}):
            provider = AzureAnthropicProvider(
                {
                    "endpoint": "https://test.azure.com/anthropic/",
                    "deployment_name": "claude-sonnet-4-5",
                    "throttle": {
                        "enabled": True,
                        "min_request_interval": 1.0,
                    },
                }
            )

            assert provider.throttle_enabled is True
            assert provider.min_request_interval == 1.0


class TestAzureAnthropicProviderInheritance:
    """Test that AzureAnthropicProvider inherits methods from AnthropicProvider."""

    @patch("anthropic.AsyncAnthropic")
    def test_has_chat_method(self, mock_anthropic):
        """Test that provider has chat method from parent."""
        with patch.dict(os.environ, {"AZURE_ANTHROPIC_API_KEY": "test-key"}):
            provider = AzureAnthropicProvider(
                {
                    "endpoint": "https://test.azure.com/anthropic/",
                    "deployment_name": "claude-sonnet-4-5",
                }
            )

            assert hasattr(provider, "chat")
            assert callable(provider.chat)

    @patch("anthropic.AsyncAnthropic")
    def test_has_chat_stream_method(self, mock_anthropic):
        """Test that provider has chat_stream method from parent."""
        with patch.dict(os.environ, {"AZURE_ANTHROPIC_API_KEY": "test-key"}):
            provider = AzureAnthropicProvider(
                {
                    "endpoint": "https://test.azure.com/anthropic/",
                    "deployment_name": "claude-sonnet-4-5",
                }
            )

            assert hasattr(provider, "chat_stream")
            assert callable(provider.chat_stream)


class TestLLMClientRouting:
    """Test LLMClient routes to correct provider."""

    @patch("anthropic.AsyncAnthropic")
    def test_azure_anthropic_provider_selection(self, mock_anthropic):
        """Test LLMClient routes to AzureAnthropicProvider."""
        with patch.dict(os.environ, {"AZURE_ANTHROPIC_API_KEY": "test-key"}):
            client = LLMClient(
                {
                    "provider": "azure_anthropic",
                    "azure_anthropic": {
                        "endpoint": "https://test.azure.com/anthropic/",
                        "deployment_name": "claude-sonnet-4-5",
                    },
                }
            )

            assert isinstance(client.provider, AzureAnthropicProvider)
            assert client.provider.endpoint == "https://test.azure.com/anthropic/"

    @patch("anthropic.AsyncAnthropic")
    def test_anthropic_provider_still_works(self, mock_anthropic):
        """Test that original anthropic provider still works."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            from orchestrator.llm.client import AnthropicProvider

            client = LLMClient(
                {
                    "provider": "anthropic",
                    "anthropic": {
                        "model": "claude-sonnet-4-20250514",
                    },
                }
            )

            assert isinstance(client.provider, AnthropicProvider)
            assert not isinstance(client.provider, AzureAnthropicProvider)

    def test_unsupported_provider_raises_error(self):
        """Test that unsupported provider raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            LLMClient({"provider": "unsupported"})

    @patch("anthropic.AsyncAnthropic")
    def test_default_provider_is_anthropic(self, mock_anthropic):
        """Test that default provider is anthropic."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            from orchestrator.llm.client import AnthropicProvider

            # No provider specified
            client = LLMClient(
                {
                    "anthropic": {
                        "model": "claude-sonnet-4-20250514",
                    },
                }
            )

            assert isinstance(client.provider, AnthropicProvider)
