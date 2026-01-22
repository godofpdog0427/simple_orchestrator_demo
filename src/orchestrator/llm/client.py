"""LLM client abstraction."""

import asyncio
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from LLM."""

    content: list[Any]  # Content blocks (text or tool_use)
    stop_reason: str  # "end_turn", "tool_use", "max_tokens", etc.
    usage: dict[str, int]  # Token usage stats
    model: str
    raw_response: Any  # Original response object


@dataclass
class StreamChunk:
    """Wrapper for stream chunk to distinguish from final response."""
    text: str


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> LLMResponse:
        """
        Send chat request to LLM.

        Args:
            messages: List of message dicts with role and content
            tools: Optional list of tool definitions

        Returns:
            LLMResponse object
        """
        pass


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, config: dict) -> None:
        """
        Initialize Anthropic provider.

        Args:
            config: Provider configuration
        """
        self.config = config
        self.model = config.get("model", "claude-sonnet-4-20250514")
        self.max_tokens = config.get("max_tokens", 4096)
        self.temperature = config.get("temperature", 0.7)

        # Retry configuration
        retry_config = config.get("retry", {})
        self.max_retries = retry_config.get("max_retries", 5)
        self.base_delay = retry_config.get("base_delay", 2.0)
        self.max_delay = retry_config.get("max_delay", 60.0)
        self.exponential_base = retry_config.get("exponential_base", 2.0)

        # Throttle configuration
        throttle_config = config.get("throttle", {})
        self.throttle_enabled = throttle_config.get("enabled", False)
        self.min_request_interval = throttle_config.get("min_request_interval", 0.5)
        self.last_request_time = 0.0

        # Get API key
        api_key_env = config.get("api_key_env", "ANTHROPIC_API_KEY")
        self.api_key = os.getenv(api_key_env)

        if not self.api_key:
            raise ValueError(f"API key not found in environment variable: {api_key_env}")

        # Initialize Anthropic client
        try:
            from anthropic import AsyncAnthropic

            self.client = AsyncAnthropic(api_key=self.api_key)
        except ImportError as e:
            raise ImportError(
                "anthropic package not installed. Install with: pip install anthropic"
            ) from e

        logger.info(f"Initialized Anthropic provider with model: {self.model}")
        logger.info(f"Retry config: max_retries={self.max_retries}, base_delay={self.base_delay}s")

    async def _apply_throttle(self) -> None:
        """Apply request throttling if enabled."""
        if not self.throttle_enabled:
            return

        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            logger.debug(f"Throttling: sleeping for {sleep_time:.2f}s")
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()

    async def chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> LLMResponse:
        """
        Send chat request to Anthropic API with retry logic.

        Args:
            messages: List of message dicts with role and content
            tools: Optional list of tool definitions in Anthropic format

        Returns:
            LLMResponse object

        Raises:
            Exception: If all retries are exhausted
        """
        # Apply throttling if enabled
        await self._apply_throttle()

        # Separate system message from conversation
        system_message = None
        conversation_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                conversation_messages.append(msg)

        # Prepare API call parameters
        params = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": conversation_messages,
        }

        if system_message:
            params["system"] = system_message

        if tools:
            params["tools"] = tools

        logger.debug(f"Calling Anthropic API with {len(conversation_messages)} messages")

        # Retry loop with exponential backoff
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.messages.create(**params)

                # Convert to LLMResponse
                return LLMResponse(
                    content=response.content,
                    stop_reason=response.stop_reason,
                    usage={
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    },
                    model=response.model,
                    raw_response=response,
                )

            except Exception as e:
                last_exception = e

                # Check if it's a rate limit error (429)
                is_rate_limit = self._is_rate_limit_error(e)

                if is_rate_limit and attempt < self.max_retries:
                    # Calculate retry delay with exponential backoff
                    delay = min(
                        self.base_delay * (self.exponential_base**attempt), self.max_delay
                    )

                    # Check for retry-after header
                    retry_after = self._get_retry_after(e)
                    if retry_after:
                        delay = min(retry_after, self.max_delay)

                    logger.warning(
                        f"Rate limit error (429) on attempt {attempt + 1}/{self.max_retries + 1}. "
                        f"Retrying in {delay:.1f}s... "
                        f"(Tip: Check your usage tier at https://console.anthropic.com/settings/limits)"
                    )

                    await asyncio.sleep(delay)
                    continue

                # Not a rate limit error, or out of retries
                if is_rate_limit:
                    logger.error(
                        f"Rate limit error persisted after {self.max_retries} retries. "
                        f"Your API usage tier may be too low. "
                        f"Check https://console.anthropic.com/settings/limits"
                    )
                else:
                    logger.error(f"Error calling Anthropic API: {e}", exc_info=True)

                raise

        # Should never reach here, but just in case
        raise last_exception

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if error is a rate limit (429) error."""
        # Check for anthropic.RateLimitError
        error_type = type(error).__name__
        if "RateLimitError" in error_type:
            return True

        # Check error message for 429
        error_str = str(error).lower()
        if "429" in error_str or "rate limit" in error_str or "too many requests" in error_str:
            return True

        return False

    def _get_retry_after(self, error: Exception) -> float | None:
        """Extract retry-after value from error if available."""
        try:
            # Try to get retry_after from error object
            if hasattr(error, "response") and hasattr(error.response, "headers"):
                retry_after = error.response.headers.get("retry-after")
                if retry_after:
                    return float(retry_after)
        except (AttributeError, ValueError, TypeError):
            pass

        return None

    async def chat_stream(
        self, messages: list[dict], tools: list[dict] | None = None
    ):
        """
        Stream chat response from Anthropic API.

        Yields StreamChunk objects with text, then yields final LLMResponse.

        Args:
            messages: List of message dicts with role and content
            tools: Optional list of tool definitions in Anthropic format

        Yields:
            StreamChunk: Text chunks from the stream
            LLMResponse: Final complete response (last yield)
        """
        # Apply throttling if enabled
        await self._apply_throttle()

        # Separate system message from conversation
        system_message = None
        conversation_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                conversation_messages.append(msg)

        # Prepare API call parameters
        params = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": conversation_messages,
        }

        if system_message:
            params["system"] = system_message

        if tools:
            params["tools"] = tools

        logger.debug(f"Streaming Anthropic API with {len(conversation_messages)} messages")

        # Use stream API
        async with self.client.messages.stream(**params) as stream:
            # Stream text chunks
            async for text in stream.text_stream:
                yield StreamChunk(text=text)

            # Get final message
            final_message = await stream.get_final_message()

            # Yield final response as last item
            yield LLMResponse(
                content=final_message.content,
                stop_reason=final_message.stop_reason,
                usage={
                    "input_tokens": final_message.usage.input_tokens,
                    "output_tokens": final_message.usage.output_tokens,
                },
                model=final_message.model,
                raw_response=final_message,
            )


class AzureAnthropicProvider(AnthropicProvider):
    """Azure-hosted Anthropic Claude provider.

    Uses Anthropic SDK with custom base_url to connect to Azure endpoint.
    Inherits chat() and chat_stream() methods from AnthropicProvider.
    """

    def __init__(self, config: dict) -> None:
        """
        Initialize Azure Anthropic provider.

        Args:
            config: Provider configuration with Azure-specific settings

        Required config keys:
            endpoint: Azure Anthropic API endpoint URL
            deployment_name: Azure deployment name (used as model)

        Optional config keys:
            api_key_env: Environment variable name for API key (default: AZURE_ANTHROPIC_API_KEY)
            max_tokens, temperature, retry, throttle: Same as AnthropicProvider
        """
        self.config = config

        # Azure-specific configuration
        self.endpoint = config.get("endpoint")
        self.deployment_name = config.get("deployment_name")

        if not self.endpoint:
            raise ValueError("Azure Anthropic endpoint is required")
        if not self.deployment_name:
            raise ValueError("Azure Anthropic deployment_name is required")

        # Use deployment_name as model
        self.model = self.deployment_name
        self.max_tokens = config.get("max_tokens", 4096)
        self.temperature = config.get("temperature", 0.7)

        # Retry configuration
        retry_config = config.get("retry", {})
        self.max_retries = retry_config.get("max_retries", 5)
        self.base_delay = retry_config.get("base_delay", 2.0)
        self.max_delay = retry_config.get("max_delay", 60.0)
        self.exponential_base = retry_config.get("exponential_base", 2.0)

        # Throttle configuration
        throttle_config = config.get("throttle", {})
        self.throttle_enabled = throttle_config.get("enabled", False)
        self.min_request_interval = throttle_config.get("min_request_interval", 0.5)
        self.last_request_time = 0.0

        # Get API key
        api_key_env = config.get("api_key_env", "AZURE_ANTHROPIC_API_KEY")
        self.api_key = os.getenv(api_key_env)

        if not self.api_key:
            raise ValueError(f"API key not found in environment variable: {api_key_env}")

        # Initialize Anthropic client with Azure base_url
        try:
            from anthropic import AsyncAnthropic

            self.client = AsyncAnthropic(
                api_key=self.api_key,
                base_url=self.endpoint,
            )
        except ImportError as e:
            raise ImportError(
                "anthropic package not installed. Install with: pip install anthropic"
            ) from e

        logger.info("Initialized Azure Anthropic provider")
        logger.info(f"  Endpoint: {self.endpoint}")
        logger.info(f"  Deployment: {self.deployment_name}")


class LLMClient:
    """Main LLM client that routes to appropriate provider."""

    def __init__(self, config: dict) -> None:
        """
        Initialize LLM client.

        Args:
            config: LLM configuration
        """
        self.config = config
        provider_name = config.get("provider", "anthropic")

        # Initialize provider
        if provider_name == "anthropic":
            provider_config = config.get("anthropic", {})
            self.provider: LLMProvider = AnthropicProvider(provider_config)
        elif provider_name == "azure_anthropic":
            provider_config = config.get("azure_anthropic", {})
            self.provider = AzureAnthropicProvider(provider_config)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider_name}")

        logger.info(f"Initialized LLM client with provider: {provider_name}")

    async def chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> LLMResponse:
        """
        Send chat request to LLM provider.

        Args:
            messages: List of message dicts
            tools: Optional list of tool definitions

        Returns:
            LLMResponse object
        """
        return await self.provider.chat(messages, tools)

    async def chat_stream(
        self, messages: list[dict], tools: list[dict] | None = None
    ):
        """
        Stream chat response from LLM provider.

        Args:
            messages: List of message dicts
            tools: Optional list of tool definitions

        Yields:
            str: Text chunks from the stream

        Returns:
            LLMResponse: Final complete response
        """
        # Check if provider supports streaming
        if not hasattr(self.provider, "chat_stream"):
            raise NotImplementedError(
                f"Provider {type(self.provider).__name__} does not support streaming"
            )

        async for chunk in self.provider.chat_stream(messages, tools):
            yield chunk
