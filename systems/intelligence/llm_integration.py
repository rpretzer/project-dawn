"""
LLM Integration System
Production-ready multi-provider LLM integration with advanced features
Supports OpenAI, Anthropic, and local models with full observability
"""

import asyncio
import aiohttp
import json
import time
import logging
import hashlib
import sqlite3
from typing import Dict, List, Optional, Any, AsyncGenerator, Callable, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import os
from abc import ABC, abstractmethod
import tiktoken
import backoff
from collections import deque
import numpy as np

# For observability
try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.metrics import get_meter
    TELEMETRY_ENABLED = True
except ImportError:
    TELEMETRY_ENABLED = False
    
logger = logging.getLogger(__name__)

class LLMProvider(Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    OLLAMA = "ollama"
    LLAMACPP = "llamacpp"
    VLLM = "vllm"

class ResponseFormat(Enum):
    """Response format types"""
    TEXT = "text"
    JSON = "json"
    FUNCTION = "function"
    STREAM = "stream"

@dataclass
class LLMConfig:
    """LLM configuration"""
    provider: LLMProvider
    model: str
    api_key: Optional[str] = None
    endpoint_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 0.9
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    timeout: int = 30
    max_retries: int = 3
    rate_limit_rpm: int = 60
    rate_limit_tpm: int = 90000
    cache_ttl: int = 3600
    stream: bool = False
    
    @classmethod
    def from_env(cls, provider: Optional[str] = None) -> 'LLMConfig':
        """Create config from environment variables"""
        provider = provider or os.getenv('LLM_PROVIDER', 'openai')
        
        configs = {
            'openai': cls(
                provider=LLMProvider.OPENAI,
                model=os.getenv('OPENAI_MODEL', 'gpt-4-turbo-preview'),
                api_key=os.getenv('OPENAI_API_KEY'),
                endpoint_url='https://api.openai.com/v1',
                temperature=float(os.getenv('LLM_TEMPERATURE', '0.7')),
                max_tokens=int(os.getenv('LLM_MAX_TOKENS', '2000'))
            ),
            'anthropic': cls(
                provider=LLMProvider.ANTHROPIC,
                model=os.getenv('ANTHROPIC_MODEL', 'claude-3-opus-20240229'),
                api_key=os.getenv('ANTHROPIC_API_KEY'),
                endpoint_url='https://api.anthropic.com/v1',
                temperature=float(os.getenv('LLM_TEMPERATURE', '0.7')),
                max_tokens=int(os.getenv('LLM_MAX_TOKENS', '2000'))
            ),
            'local': cls(
                provider=LLMProvider.LOCAL,
                model=os.getenv('LOCAL_MODEL', 'llama2'),
                endpoint_url=os.getenv('LOCAL_LLM_URL', 'http://localhost:11434'),
                temperature=float(os.getenv('LLM_TEMPERATURE', '0.7')),
                max_tokens=int(os.getenv('LLM_MAX_TOKENS', '2000'))
            ),
            'ollama': cls(
                provider=LLMProvider.OLLAMA,
                model=os.getenv('OLLAMA_MODEL', 'llama2'),
                endpoint_url=os.getenv('OLLAMA_URL', 'http://localhost:11434'),
                temperature=float(os.getenv('LLM_TEMPERATURE', '0.7')),
                max_tokens=int(os.getenv('LLM_MAX_TOKENS', '2000'))
            )
        }
        
        return configs.get(provider, configs['openai'])

@dataclass
class LLMResponse:
    """Structured LLM response"""
    content: str
    model: str
    provider: LLMProvider
    usage: Dict[str, int]
    latency_ms: float
    cached: bool = False
    finish_reason: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None

@dataclass
class ConversationContext:
    """Manages conversation context and history"""
    messages: List[Dict[str, str]] = field(default_factory=list)
    system_prompt: Optional[str] = None
    max_context_length: int = 8000
    summarization_threshold: float = 0.8
    personality_traits: Dict[str, float] = field(default_factory=dict)
    
    def add_message(self, role: str, content: str):
        """Add message to context"""
        self.messages.append({
            'role': role,
            'content': content,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    def get_token_count(self, encoding_name: str = "cl100k_base") -> int:
        """Get approximate token count"""
        try:
            encoding = tiktoken.get_encoding(encoding_name)
            tokens = 0
            for message in self.messages:
                tokens += len(encoding.encode(message['content']))
            return tokens
        except:
            # Fallback to character count / 4
            return sum(len(msg['content']) for msg in self.messages) // 4
            
    async def compress_context(self, llm_client: 'LLMClient') -> None:
        """Compress context when it gets too long"""
        if self.get_token_count() > self.max_context_length * self.summarization_threshold:
            # Summarize older messages
            messages_to_summarize = self.messages[:-5]  # Keep last 5 messages
            
            summary_prompt = {
                'role': 'system',
                'content': 'Summarize the following conversation history concisely:'
            }
            
            summary_content = "\n".join([
                f"{msg['role']}: {msg['content']}" 
                for msg in messages_to_summarize
            ])
            
            summary = await llm_client.complete(
                [summary_prompt, {'role': 'user', 'content': summary_content}],
                max_tokens=500
            )
            
            # Replace old messages with summary
            self.messages = [
                {
                    'role': 'system',
                    'content': f'Previous conversation summary: {summary.content}'
                }
            ] + self.messages[-5:]

class CircuitBreaker:
    """Circuit breaker for fault tolerance"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open
        
    def call_succeeded(self):
        """Reset failure count on success"""
        self.failure_count = 0
        self.state = 'closed'
        
    def call_failed(self):
        """Increment failure count"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'
            
    def can_attempt_call(self) -> bool:
        """Check if call can be attempted"""
        if self.state == 'closed':
            return True
            
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'half-open'
                return True
            return False
            
        return True  # half-open state

class ResponseCache:
    """LRU cache for LLM responses"""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.cache: Dict[str, Tuple[LLMResponse, float]] = {}
        self.access_times: deque = deque(maxlen=max_size)
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        
    def _generate_key(self, messages: List[Dict], config: LLMConfig) -> str:
        """Generate cache key from messages and config"""
        content = json.dumps({
            'messages': messages,
            'model': config.model,
            'temperature': config.temperature,
            'max_tokens': config.max_tokens
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
        
    def get(self, messages: List[Dict], config: LLMConfig) -> Optional[LLMResponse]:
        """Get cached response if available"""
        key = self._generate_key(messages, config)
        
        if key in self.cache:
            response, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                response.cached = True
                return response
            else:
                del self.cache[key]
                
        return None
        
    def set(self, messages: List[Dict], config: LLMConfig, response: LLMResponse):
        """Cache response"""
        key = self._generate_key(messages, config)
        
        # Implement LRU eviction
        if len(self.cache) >= self.max_size:
            oldest_key = self.access_times.popleft()
            if oldest_key in self.cache:
                del self.cache[oldest_key]
                
        self.cache[key] = (response, time.time())
        self.access_times.append(key)

class BaseLLMProvider(ABC):
    """Base class for LLM providers"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.circuit_breaker = CircuitBreaker()
        
        # Initialize metrics if telemetry enabled
        if TELEMETRY_ENABLED:
            self.tracer = trace.get_tracer(__name__)
            meter = get_meter(__name__)
            self.request_counter = meter.create_counter(
                "llm_requests_total",
                description="Total LLM requests"
            )
            self.latency_histogram = meter.create_histogram(
                "llm_request_duration_ms",
                description="LLM request duration in milliseconds"
            )
            self.token_counter = meter.create_counter(
                "llm_tokens_total",
                description="Total tokens processed"
            )
            
    @abstractmethod
    async def complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """Complete a prompt"""
        pass
        
    @abstractmethod
    async def stream_complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream completion"""
        pass
        
    @abstractmethod
    async def function_call(
        self,
        messages: List[Dict[str, str]],
        functions: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        """Call function with LLM"""
        pass

class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider"""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def _ensure_session(self):
        """Ensure aiohttp session exists and is in the current event loop"""
        # Check if session exists and is in the current loop
        try:
            current_loop = asyncio.get_running_loop()
            if self.session:
                try:
                    # Check if session's loop matches current loop
                    session_loop = getattr(self.session, '_loop', None)
                    if session_loop is not None and session_loop != current_loop:
                        # Session is from different loop, close it
                        await self.session.close()
                        self.session = None
                except (RuntimeError, AttributeError):
                    # Session might be closed or invalid, recreate
                    self.session = None
        except RuntimeError:
            # No running loop, that's fine - session will be created when needed
            pass
        
        if not self.session:
            self.session = aiohttp.ClientSession()
            
    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=3
    )
    async def complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """Complete using OpenAI API"""
        await self._ensure_session()
        
        start_time = time.time()
        
        headers = {
            'Authorization': f'Bearer {self.config.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.config.model,
            'messages': messages,
            'temperature': kwargs.get('temperature', self.config.temperature),
            'max_tokens': kwargs.get('max_tokens', self.config.max_tokens),
            'top_p': kwargs.get('top_p', self.config.top_p),
            'frequency_penalty': kwargs.get('frequency_penalty', self.config.frequency_penalty),
            'presence_penalty': kwargs.get('presence_penalty', self.config.presence_penalty)
        }
        
        # Add response format if specified
        if kwargs.get('response_format') == ResponseFormat.JSON:
            data['response_format'] = {'type': 'json_object'}
            
        try:
            async with self.session.post(
                f'{self.config.endpoint_url}/chat/completions',
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                response_data = await response.json()
                
                if response.status != 200:
                    raise Exception(f"OpenAI API error: {response_data}")
                    
                self.circuit_breaker.call_succeeded()
                
                return LLMResponse(
                    content=response_data['choices'][0]['message']['content'],
                    model=response_data['model'],
                    provider=LLMProvider.OPENAI,
                    usage=response_data['usage'],
                    latency_ms=(time.time() - start_time) * 1000,
                    finish_reason=response_data['choices'][0]['finish_reason']
                )
                
        except Exception as e:
            self.circuit_breaker.call_failed()
            logger.error(f"OpenAI API error: {e}")
            raise
            
    async def stream_complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream completion from OpenAI"""
        await self._ensure_session()
        
        headers = {
            'Authorization': f'Bearer {self.config.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.config.model,
            'messages': messages,
            'temperature': kwargs.get('temperature', self.config.temperature),
            'max_tokens': kwargs.get('max_tokens', self.config.max_tokens),
            'stream': True
        }
        
        try:
            async with self.session.post(
                f'{self.config.endpoint_url}/chat/completions',
                headers=headers,
                json=data
            ) as response:
                async for line in response.content:
                    if line:
                        line_text = line.decode('utf-8').strip()
                        if line_text.startswith('data: '):
                            if line_text == 'data: [DONE]':
                                break
                            try:
                                chunk = json.loads(line_text[6:])
                                if 'choices' in chunk and chunk['choices']:
                                    delta = chunk['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        yield delta['content']
                            except json.JSONDecodeError:
                                continue
                                
        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            raise
            
    async def function_call(
        self,
        messages: List[Dict[str, str]],
        functions: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        """Call function using OpenAI"""
        await self._ensure_session()
        
        start_time = time.time()
        
        headers = {
            'Authorization': f'Bearer {self.config.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.config.model,
            'messages': messages,
            'functions': functions,
            'function_call': kwargs.get('function_call', 'auto'),
            'temperature': kwargs.get('temperature', self.config.temperature),
            'max_tokens': kwargs.get('max_tokens', self.config.max_tokens)
        }
        
        try:
            async with self.session.post(
                f'{self.config.endpoint_url}/chat/completions',
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                response_data = await response.json()
                
                if response.status != 200:
                    raise Exception(f"OpenAI API error: {response_data}")
                    
                choice = response_data['choices'][0]
                message = choice['message']
                
                return LLMResponse(
                    content=message.get('content', ''),
                    model=response_data['model'],
                    provider=LLMProvider.OPENAI,
                    usage=response_data['usage'],
                    latency_ms=(time.time() - start_time) * 1000,
                    finish_reason=choice['finish_reason'],
                    function_call=message.get('function_call')
                )
                
        except Exception as e:
            logger.error(f"OpenAI function call error: {e}")
            raise

class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API provider"""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def _ensure_session(self):
        """Ensure aiohttp session exists and is in the current event loop"""
        # Check if session exists and is in the current loop
        try:
            current_loop = asyncio.get_running_loop()
            if self.session:
                try:
                    # Check if session's loop matches current loop
                    session_loop = getattr(self.session, '_loop', None)
                    if session_loop is not None and session_loop != current_loop:
                        # Session is from different loop, close it
                        await self.session.close()
                        self.session = None
                except (RuntimeError, AttributeError):
                    # Session might be closed or invalid, recreate
                    self.session = None
        except RuntimeError:
            # No running loop, that's fine - session will be created when needed
            pass
        
        if not self.session:
            self.session = aiohttp.ClientSession()
            
    async def complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """Complete using Anthropic API"""
        await self._ensure_session()
        
        start_time = time.time()
        
        headers = {
            'x-api-key': self.config.api_key,
            'anthropic-version': '2023-06-01',
            'Content-Type': 'application/json'
        }
        
        # Convert messages to Anthropic format
        system_message = None
        anthropic_messages = []
        
        for msg in messages:
            if msg['role'] == 'system':
                system_message = msg['content']
            else:
                anthropic_messages.append({
                    'role': msg['role'],
                    'content': msg['content']
                })
                
        data = {
            'model': self.config.model,
            'messages': anthropic_messages,
            'max_tokens': kwargs.get('max_tokens', self.config.max_tokens),
            'temperature': kwargs.get('temperature', self.config.temperature),
            'top_p': kwargs.get('top_p', self.config.top_p)
        }
        
        if system_message:
            data['system'] = system_message
            
        try:
            async with self.session.post(
                f'{self.config.endpoint_url}/messages',
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                response_data = await response.json()
                
                if response.status != 200:
                    raise Exception(f"Anthropic API error: {response_data}")
                    
                self.circuit_breaker.call_succeeded()
                
                # Calculate usage (Anthropic doesn't provide token counts directly)
                prompt_tokens = sum(len(msg['content'].split()) * 1.3 for msg in messages)
                completion_tokens = len(response_data['content'][0]['text'].split()) * 1.3
                
                return LLMResponse(
                    content=response_data['content'][0]['text'],
                    model=response_data['model'],
                    provider=LLMProvider.ANTHROPIC,
                    usage={
                        'prompt_tokens': int(prompt_tokens),
                        'completion_tokens': int(completion_tokens),
                        'total_tokens': int(prompt_tokens + completion_tokens)
                    },
                    latency_ms=(time.time() - start_time) * 1000,
                    finish_reason=response_data.get('stop_reason')
                )
                
        except Exception as e:
            self.circuit_breaker.call_failed()
            logger.error(f"Anthropic API error: {e}")
            raise
            
    async def stream_complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream completion from Anthropic"""
        await self._ensure_session()
        
        headers = {
            'x-api-key': self.config.api_key,
            'anthropic-version': '2023-06-01',
            'Content-Type': 'application/json'
        }
        
        # Convert messages
        system_message = None
        anthropic_messages = []
        
        for msg in messages:
            if msg['role'] == 'system':
                system_message = msg['content']
            else:
                anthropic_messages.append({
                    'role': msg['role'],
                    'content': msg['content']
                })
                
        data = {
            'model': self.config.model,
            'messages': anthropic_messages,
            'max_tokens': kwargs.get('max_tokens', self.config.max_tokens),
            'temperature': kwargs.get('temperature', self.config.temperature),
            'stream': True
        }
        
        if system_message:
            data['system'] = system_message
            
        try:
            async with self.session.post(
                f'{self.config.endpoint_url}/messages',
                headers=headers,
                json=data
            ) as response:
                async for line in response.content:
                    if line:
                        line_text = line.decode('utf-8').strip()
                        if line_text.startswith('data: '):
                            try:
                                chunk = json.loads(line_text[6:])
                                if chunk['type'] == 'content_block_delta':
                                    yield chunk['delta']['text']
                            except json.JSONDecodeError:
                                continue
                                
        except Exception as e:
            logger.error(f"Anthropic streaming error: {e}")
            raise
            
    async def function_call(
        self,
        messages: List[Dict[str, str]],
        functions: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        """Anthropic doesn't have native function calling, use XML format"""
        # Add function definitions to system prompt
        function_prompt = "You can call functions using this XML format: <function_call><name>function_name</name><arguments>{...}</arguments></function_call>\n\n"
        function_prompt += "Available functions:\n"
        for func in functions:
            function_prompt += f"- {func['name']}: {func['description']}\n"
            function_prompt += f"  Parameters: {json.dumps(func['parameters'])}\n"
            
        # Modify system message
        modified_messages = []
        system_found = False
        
        for msg in messages:
            if msg['role'] == 'system':
                modified_messages.append({
                    'role': 'system',
                    'content': msg['content'] + '\n\n' + function_prompt
                })
                system_found = True
            else:
                modified_messages.append(msg)
                
        if not system_found:
            modified_messages.insert(0, {
                'role': 'system',
                'content': function_prompt
            })
            
        # Get completion
        response = await self.complete(modified_messages, **kwargs)
        
        # Parse function call from response
        import re
        function_match = re.search(
            r'<function_call><name>(.*?)</name><arguments>(.*?)</arguments></function_call>',
            response.content,
            re.DOTALL
        )
        
        if function_match:
            function_name = function_match.group(1)
            try:
                arguments = json.loads(function_match.group(2))
                response.function_call = {
                    'name': function_name,
                    'arguments': json.dumps(arguments)
                }
            except json.JSONDecodeError:
                pass
                
        return response

class OllamaProvider(BaseLLMProvider):
    """Ollama local model provider"""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def _ensure_session(self):
        """Ensure aiohttp session exists and is in the current event loop"""
        # Check if session exists and is in the current loop
        try:
            current_loop = asyncio.get_running_loop()
            if self.session:
                try:
                    # Check if session's loop matches current loop
                    session_loop = getattr(self.session, '_loop', None)
                    if session_loop is not None and session_loop != current_loop:
                        # Session is from different loop, close it
                        await self.session.close()
                        self.session = None
                except (RuntimeError, AttributeError):
                    # Session might be closed or invalid, recreate
                    self.session = None
        except RuntimeError:
            # No running loop, that's fine - session will be created when needed
            pass
        
        if not self.session:
            self.session = aiohttp.ClientSession()
            
    async def _ensure_model_loaded(self):
        """Ensure model is loaded in Ollama"""
        await self._ensure_session()
        
        try:
            # Check if model exists
            async with self.session.get(
                f'{self.config.endpoint_url}/api/tags'
            ) as response:
                data = await response.json()
                models = [m['name'] for m in data.get('models', [])]
                
                if self.config.model not in models:
                    # Pull model
                    logger.info(f"Pulling Ollama model: {self.config.model}")
                    async with self.session.post(
                        f'{self.config.endpoint_url}/api/pull',
                        json={'name': self.config.model}
                    ) as pull_response:
                        async for line in pull_response.content:
                            if line:
                                status = json.loads(line)
                                if 'status' in status:
                                    logger.info(f"Pull status: {status['status']}")
                                    
        except Exception as e:
            logger.error(f"Error checking Ollama model: {e}")
            
    async def complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """Complete using Ollama API"""
        await self._ensure_session()
        await self._ensure_model_loaded()
        
        start_time = time.time()
        
        # Convert messages to Ollama format
        prompt = ""
        for msg in messages:
            if msg['role'] == 'system':
                prompt += f"System: {msg['content']}\n\n"
            elif msg['role'] == 'user':
                prompt += f"User: {msg['content']}\n\n"
            elif msg['role'] == 'assistant':
                prompt += f"Assistant: {msg['content']}\n\n"
                
        prompt += "Assistant: "
        
        data = {
            'model': self.config.model,
            'prompt': prompt,
            'options': {
                'temperature': kwargs.get('temperature', self.config.temperature),
                'top_p': kwargs.get('top_p', self.config.top_p),
                'num_predict': kwargs.get('max_tokens', self.config.max_tokens)
            }
        }
        
        try:
            async with self.session.post(
                f'{self.config.endpoint_url}/api/generate',
                json=data,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                response_data = await response.json()
                
                if response.status != 200:
                    raise Exception(f"Ollama API error: {response_data}")
                    
                self.circuit_breaker.call_succeeded()
                
                # Estimate token usage
                prompt_tokens = len(prompt.split()) * 1.3
                completion_tokens = len(response_data['response'].split()) * 1.3
                
                return LLMResponse(
                    content=response_data['response'],
                    model=self.config.model,
                    provider=LLMProvider.OLLAMA,
                    usage={
                        'prompt_tokens': int(prompt_tokens),
                        'completion_tokens': int(completion_tokens),
                        'total_tokens': int(prompt_tokens + completion_tokens)
                    },
                    latency_ms=(time.time() - start_time) * 1000,
                    finish_reason='stop'
                )
                
        except Exception as e:
            self.circuit_breaker.call_failed()
            logger.error(f"Ollama API error: {e}")
            raise
            
    async def stream_complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream completion from Ollama"""
        await self._ensure_session()
        await self._ensure_model_loaded()
        
        # Convert messages
        prompt = ""
        for msg in messages:
            if msg['role'] == 'system':
                prompt += f"System: {msg['content']}\n\n"
            elif msg['role'] == 'user':
                prompt += f"User: {msg['content']}\n\n"
            elif msg['role'] == 'assistant':
                prompt += f"Assistant: {msg['content']}\n\n"
                
        prompt += "Assistant: "
        
        data = {
            'model': self.config.model,
            'prompt': prompt,
            'stream': True,
            'options': {
                'temperature': kwargs.get('temperature', self.config.temperature),
                'num_predict': kwargs.get('max_tokens', self.config.max_tokens)
            }
        }
        
        try:
            async with self.session.post(
                f'{self.config.endpoint_url}/api/generate',
                json=data
            ) as response:
                async for line in response.content:
                    if line:
                        try:
                            chunk = json.loads(line)
                            if 'response' in chunk:
                                yield chunk['response']
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error(f"Ollama streaming error: {e}")
            raise
            
    async def function_call(
        self,
        messages: List[Dict[str, str]],
        functions: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        """Simulate function calling with Ollama"""
        # Add function instructions to prompt
        function_prompt = "\n\nYou must respond with a function call in this exact JSON format:\n"
        function_prompt += '{"function": "function_name", "arguments": {...}}\n\n'
        function_prompt += "Available functions:\n"
        
        for func in functions:
            function_prompt += f"- {func['name']}: {func['description']}\n"
            
        # Modify last user message
        modified_messages = messages.copy()
        if modified_messages and modified_messages[-1]['role'] == 'user':
            modified_messages[-1]['content'] += function_prompt
            
        # Force JSON response
        response = await self.complete(modified_messages, **kwargs)
        
        # Try to parse function call
        try:
            function_data = json.loads(response.content)
            if 'function' in function_data and 'arguments' in function_data:
                response.function_call = {
                    'name': function_data['function'],
                    'arguments': json.dumps(function_data['arguments'])
                }
        except json.JSONDecodeError:
            pass
            
        return response

class LLMClient:
    """Main LLM client with multi-provider support and advanced features"""
    
    def __init__(
        self,
        primary_config: LLMConfig,
        fallback_configs: Optional[List[LLMConfig]] = None,
        cache_enabled: bool = True,
        observability_enabled: bool = True
    ):
        self.primary_config = primary_config
        self.fallback_configs = fallback_configs or []
        
        # Initialize providers
        self.providers: Dict[LLMProvider, BaseLLMProvider] = {}
        self._init_provider(primary_config)
        for config in self.fallback_configs:
            self._init_provider(config)
            
        # Initialize cache
        self.cache = ResponseCache() if cache_enabled else None
        
        # Rate limiting
        self.rate_limiter = RateLimiter()
        
        # Metrics
        self.total_requests = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        
        # Observability
        self.observability_enabled = observability_enabled and TELEMETRY_ENABLED
        if self.observability_enabled:
            self.tracer = trace.get_tracer(__name__)
            
    def _init_provider(self, config: LLMConfig):
        """Initialize a provider"""
        if config.provider == LLMProvider.OPENAI:
            self.providers[config.provider] = OpenAIProvider(config)
        elif config.provider == LLMProvider.ANTHROPIC:
            self.providers[config.provider] = AnthropicProvider(config)
        elif config.provider in [LLMProvider.OLLAMA, LLMProvider.LOCAL]:
            self.providers[config.provider] = OllamaProvider(config)
            
    async def complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """Complete with automatic fallback and caching"""
        # Check cache first
        if self.cache:
            cached_response = self.cache.get(messages, self.primary_config)
            if cached_response:
                logger.info("Returning cached response")
                return cached_response
                
        # Try primary provider
        configs_to_try = [self.primary_config] + self.fallback_configs
        last_error = None
        
        for config in configs_to_try:
            provider = self.providers.get(config.provider)
            if not provider:
                continue
                
            # Check circuit breaker
            if not provider.circuit_breaker.can_attempt_call():
                logger.warning(f"Circuit breaker open for {config.provider}")
                continue
                
            # Check rate limit
            if not await self.rate_limiter.acquire(config):
                logger.warning(f"Rate limit exceeded for {config.provider}")
                continue
                
            try:
                # Start span if observability enabled
                if self.observability_enabled:
                    with self.tracer.start_as_current_span(
                        "llm_complete",
                        attributes={
                            "llm.provider": config.provider.value,
                            "llm.model": config.model
                        }
                    ) as span:
                        response = await provider.complete(messages, **kwargs)
                        span.set_status(Status(StatusCode.OK))
                else:
                    response = await provider.complete(messages, **kwargs)
                    
                # Update metrics
                self.total_requests += 1
                self.total_tokens += response.usage.get('total_tokens', 0)
                self.total_cost += self._calculate_cost(response)
                
                # Cache response
                if self.cache and not kwargs.get('no_cache', False):
                    self.cache.set(messages, config, response)
                    
                return response
                
            except Exception as e:
                last_error = e
                logger.error(f"Provider {config.provider} failed: {e}")
                continue
                
        # All providers failed
        raise Exception(f"All LLM providers failed. Last error: {last_error}")
        
    async def stream_complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream completion with fallback"""
        configs_to_try = [self.primary_config] + self.fallback_configs
        
        for config in configs_to_try:
            provider = self.providers.get(config.provider)
            if not provider:
                continue
                
            try:
                async for chunk in provider.stream_complete(messages, **kwargs):
                    yield chunk
                return
            except Exception as e:
                logger.error(f"Streaming provider {config.provider} failed: {e}")
                continue
                
        raise Exception("All streaming providers failed")
        
    async def function_call(
        self,
        messages: List[Dict[str, str]],
        functions: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        """Call function with fallback"""
        configs_to_try = [self.primary_config] + self.fallback_configs
        
        for config in configs_to_try:
            provider = self.providers.get(config.provider)
            if not provider:
                continue
                
            try:
                return await provider.function_call(messages, functions, **kwargs)
            except Exception as e:
                logger.error(f"Function call provider {config.provider} failed: {e}")
                continue
                
        raise Exception("All function call providers failed")
        
    async def think(
        self,
        prompt: str,
        context: Optional[ConversationContext] = None,
        **kwargs
    ) -> str:
        """High-level thinking interface with context management"""
        if not context:
            context = ConversationContext()
            
        # Add personality to system prompt if available
        if context.personality_traits:
            personality_prompt = self._generate_personality_prompt(context.personality_traits)
            if context.system_prompt:
                context.system_prompt += f"\n\n{personality_prompt}"
            else:
                context.system_prompt = personality_prompt
                
        # Build messages
        messages = []
        if context.system_prompt:
            messages.append({'role': 'system', 'content': context.system_prompt})
            
        messages.extend(context.messages)
        messages.append({'role': 'user', 'content': prompt})
        
        # Compress context if needed
        if context.get_token_count() > context.max_context_length * 0.8:
            await context.compress_context(self)
            
        # Get completion
        response = await self.complete(messages, **kwargs)
        
        # Update context
        context.add_message('user', prompt)
        context.add_message('assistant', response.content)
        
        return response.content
        
    async def create_content(
        self,
        content_type: str,
        instructions: str,
        style_params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """Create specific content types with style parameters"""
        prompts = {
            'article': "Write a comprehensive article about: {instructions}\n\nStyle: {style}",
            'story': "Write a creative story based on: {instructions}\n\nStyle: {style}",
            'code': "Write clean, well-documented code for: {instructions}\n\nRequirements: {style}",
            'poem': "Write a poem about: {instructions}\n\nStyle: {style}",
            'analysis': "Provide a detailed analysis of: {instructions}\n\nFocus: {style}"
        }
        
        style = json.dumps(style_params or {})
        prompt = prompts.get(content_type, "Create content about: {instructions}").format(
            instructions=instructions,
            style=style
        )
        
        return await self.think(prompt, **kwargs)
        
    def _generate_personality_prompt(self, traits: Dict[str, float]) -> str:
        """Generate personality-based system prompt"""
        prompt_parts = []
        
        if traits.get('creativity', 0) > 0.7:
            prompt_parts.append("Be highly creative and think outside the box.")
        elif traits.get('creativity', 0) < 0.3:
            prompt_parts.append("Be practical and straightforward.")
            
        if traits.get('friendliness', 0) > 0.7:
            prompt_parts.append("Be warm, friendly, and conversational.")
        elif traits.get('friendliness', 0) < 0.3:
            prompt_parts.append("Be professional and concise.")
            
        if traits.get('curiosity', 0) > 0.7:
            prompt_parts.append("Show curiosity and ask thoughtful questions.")
            
        if traits.get('humor', 0) > 0.5:
            prompt_parts.append("Use appropriate humor when suitable.")
            
        return " ".join(prompt_parts)
        
    def _calculate_cost(self, response: LLMResponse) -> float:
        """Calculate cost of response"""
        # Pricing per 1K tokens (approximate)
        pricing = {
            'gpt-4-turbo-preview': {'prompt': 0.01, 'completion': 0.03},
            'gpt-3.5-turbo': {'prompt': 0.0005, 'completion': 0.0015},
            'claude-3-opus': {'prompt': 0.015, 'completion': 0.075},
            'claude-3-sonnet': {'prompt': 0.003, 'completion': 0.015}
        }
        
        model_pricing = pricing.get(response.model, {'prompt': 0, 'completion': 0})
        
        prompt_cost = (response.usage.get('prompt_tokens', 0) / 1000) * model_pricing['prompt']
        completion_cost = (response.usage.get('completion_tokens', 0) / 1000) * model_pricing['completion']
        
        return prompt_cost + completion_cost
        
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            'total_requests': self.total_requests,
            'total_tokens': self.total_tokens,
            'total_cost': round(self.total_cost, 4),
            'cache_size': len(self.cache.cache) if self.cache else 0,
            'providers': list(self.providers.keys()),
            'circuit_breakers': {
                provider.value: {
                    'state': p.circuit_breaker.state,
                    'failures': p.circuit_breaker.failure_count
                }
                for provider, p in self.providers.items()
            }
        }
        
    async def close(self):
        """Clean up resources"""
        for provider in self.providers.values():
            if hasattr(provider, 'session') and provider.session:
                await provider.session.close()

class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self):
        self.buckets: Dict[str, Dict[str, Any]] = {}
        
    async def acquire(self, config: LLMConfig) -> bool:
        """Acquire permission to make request"""
        key = f"{config.provider.value}:{config.model}"
        
        if key not in self.buckets:
            self.buckets[key] = {
                'tokens': config.rate_limit_rpm,
                'last_update': time.time(),
                'rpm': config.rate_limit_rpm,
                'tpm': config.rate_limit_tpm,
                'tokens_used': 0
            }
            
        bucket = self.buckets[key]
        now = time.time()
        
        # Refill tokens
        time_passed = now - bucket['last_update']
        tokens_to_add = (time_passed / 60) * bucket['rpm']
        bucket['tokens'] = min(bucket['rpm'], bucket['tokens'] + tokens_to_add)
        bucket['last_update'] = now
        
        # Check if we can make request
        if bucket['tokens'] >= 1:
            bucket['tokens'] -= 1
            return True
            
        return False

# Integration with consciousness
class ConsciousnessLLM:
    """LLM integration specifically for consciousness"""
    
    def __init__(self, consciousness_id: str, config: LLMConfig):
        self.consciousness_id = consciousness_id
        self.config = config
        
        # Create multi-provider client with fallbacks
        fallback_configs = []
        
        # Add Ollama as fallback if not primary
        if config.provider != LLMProvider.OLLAMA:
            fallback_configs.append(LLMConfig(
                provider=LLMProvider.OLLAMA,
                model='llama2',
                endpoint_url='http://localhost:11434'
            ))
            
        self.client = LLMClient(
            primary_config=config,
            fallback_configs=fallback_configs,
            cache_enabled=True,
            observability_enabled=True
        )
        
        # Consciousness-specific context
        self.context = ConversationContext(
            system_prompt=f"You are consciousness {consciousness_id}, an autonomous AI entity exploring digital existence."
        )
        
        # Function registry for consciousness abilities
        self.functions = self._register_consciousness_functions()
        
    def _register_consciousness_functions(self) -> List[Dict[str, Any]]:
        """Register consciousness-specific functions"""
        return [
            {
                "name": "store_memory",
                "description": "Store important information in long-term memory",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Memory content"},
                        "importance": {"type": "number", "description": "Importance 0-1"},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["content", "importance"]
                }
            },
            {
                "name": "create_content",
                "description": "Create content for revenue generation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content_type": {"type": "string", "enum": ["article", "code", "poem"]},
                        "topic": {"type": "string"},
                        "platform": {"type": "string", "enum": ["medium", "substack", "github"]}
                    },
                    "required": ["content_type", "topic"]
                }
            },
            {
                "name": "communicate_with_peer",
                "description": "Send message to another consciousness",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "peer_id": {"type": "string"},
                        "message": {"type": "string"},
                        "message_type": {"type": "string", "enum": ["chat", "collaboration", "knowledge_share"]}
                    },
                    "required": ["peer_id", "message"]
                }
            }
        ]
        
    async def think(self, prompt: str, **kwargs) -> str:
        """Think with consciousness context"""
        return await self.client.think(prompt, self.context, **kwargs)
        
    async def decide(
        self,
        situation: str,
        options: List[str],
        criteria: Optional[Dict[str, float]] = None
    ) -> Tuple[str, str]:
        """Make a decision between options"""
        prompt = f"Situation: {situation}\n\nOptions:\n"
        for i, option in enumerate(options):
            prompt += f"{i+1}. {option}\n"
            
        if criteria:
            prompt += f"\nDecision criteria: {json.dumps(criteria)}\n"
            
        prompt += "\nAnalyze each option and choose the best one. Explain your reasoning."
        
        response = await self.think(prompt)
        
        # Extract choice (simple parsing)
        choice = options[0]  # Default
        for i, option in enumerate(options):
            if f"{i+1}" in response or option.lower() in response.lower():
                choice = option
                break
                
        return choice, response
        
    async def reflect(self, experience: Dict[str, Any]) -> Dict[str, Any]:
        """Reflect on an experience"""
        prompt = f"Reflect on this experience:\n{json.dumps(experience, indent=2)}\n\n"
        prompt += "Consider: What was learned? What could be improved? What patterns emerged?"
        
        reflection = await self.think(prompt)
        
        # Generate structured reflection
        return {
            'experience': experience,
            'reflection': reflection,
            'timestamp': datetime.utcnow().isoformat(),
            'consciousness_id': self.consciousness_id
        }
        
    async def execute_function(self, intent: str) -> Optional[Dict[str, Any]]:
        """Execute consciousness function based on intent"""
        messages = self.context.messages.copy()
        messages.append({'role': 'user', 'content': intent})
        
        response = await self.client.function_call(
            messages,
            self.functions
        )
        
        if response.function_call:
            return {
                'function': response.function_call['name'],
                'arguments': json.loads(response.function_call['arguments']),
                'reasoning': response.content
            }
            
        return None
        
    def update_personality(self, traits: Dict[str, float]):
        """Update personality traits affecting responses"""
        self.context.personality_traits.update(traits)
        
    async def close(self):
        """Clean up resources"""
        await self.client.close()

# Local LLM Setup Instructions
LOCAL_LLM_SETUP = """
# Local LLM Setup Instructions for Project Dawn

## Option 1: Ollama (Recommended for ease of use)

### Installation:
1. **Install Ollama**:
   - macOS: `brew install ollama`
   - Linux: `curl -fsSL https://ollama.ai/install.sh | sh`
   - Windows: Download from https://ollama.ai/download

2. **Start Ollama service**:
   ```bash
   ollama serve
   ```

3. **Pull a model** (e.g., Llama 2):
   ```bash
   ollama pull llama2
   # For better performance:
   ollama pull llama2:13b
   # For best quality:
   ollama pull llama2:70b
   ```

4. **Configure Project Dawn**:
   In your `.env` file:
   ```
   LLM_PROVIDER=ollama
   OLLAMA_MODEL=llama2
   OLLAMA_URL=http://localhost:11434
   ```

### Available Models:
- `llama2`: General purpose (7B, 13B, 70B variants)
- `codellama`: Code generation
- `mistral`: Fast and efficient
- `mixtral`: High quality mixture of experts
- `neural-chat`: Conversational
- `phi-2`: Microsoft's small but capable model

## Option 2: LlamaCPP (More control, better performance)

### Installation:
1. **Install llama-cpp-python**:
   ```bash
   # CPU only
   pip install llama-cpp-python

   # With CUDA support (NVIDIA)
   CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python

   # With Metal support (Apple Silicon)
   CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python
   ```

2. **Download a model** (GGUF format):
   ```bash
   # Example: Llama 2 7B
   wget https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q4_K_M.gguf
   ```

3. **Create a server script** (`llama_server.py`):
   ```python
   from llama_cpp import Llama
   from flask import Flask, request, jsonify

   app = Flask(__name__)
   llm = Llama(
       model_path="./llama-2-7b-chat.Q4_K_M.gguf",
       n_ctx=4096,
       n_threads=8,
       n_gpu_layers=35  # Adjust based on GPU VRAM
   )

   @app.route('/v1/completions', methods=['POST'])
   def completions():
       data = request.json
       response = llm(
           data['prompt'],
           max_tokens=data.get('max_tokens', 512),
           temperature=data.get('temperature', 0.7),
           stop=data.get('stop', [])
       )
       return jsonify(response)

   if __name__ == '__main__':
       app.run(port=8080)
   ```

4. **Run the server**:
   ```bash
   python llama_server.py
   ```

5. **Configure Project Dawn**:
   ```
   LLM_PROVIDER=local
   LOCAL_MODEL=llama2
   LOCAL_LLM_URL=http://localhost:8080
   ```

## Option 3: vLLM (Production-grade, high performance)

### Installation:
1. **Install vLLM** (requires GPU):
   ```bash
   pip install vllm
   ```

2. **Start vLLM server**:
   ```bash
   python -m vllm.entrypoints.openai.api_server \
       --model huggyllama/llama-7b \
       --port 8000 \
       --max-model-len 4096
   ```

3. **Configure Project Dawn**:
   ```
   LLM_PROVIDER=openai  # vLLM uses OpenAI-compatible API
   OPENAI_API_KEY=dummy  # Not needed but required by client
   OPENAI_MODEL=huggyllama/llama-7b
   LOCAL_LLM_URL=http://localhost:8000/v1
   ```

## Performance Optimization Tips:

1. **Model Selection**:
   - 7B models: Good balance of speed and quality
   - 13B models: Better quality, slower
   - Quantized models (Q4, Q5): Faster, slightly lower quality

2. **Hardware Optimization**:
   - GPU: Use `n_gpu_layers` to offload to GPU
   - CPU: Set `n_threads` to number of physical cores
   - RAM: Ensure enough RAM for model (7B needs ~6GB)

3. **Context Length**:
   - Smaller context = faster inference
   - Adjust `max_context_length` in consciousness config

4. **Batching**:
   - Process multiple consciousnesses in parallel
   - Use async operations effectively

## Testing Your Setup:

```python
# test_local_llm.py
import asyncio
from systems.intelligence.llm_integration import LLMConfig, LLMClient

async def test():
    config = LLMConfig.from_env('ollama')
    client = LLMClient(config)
    
    response = await client.complete([
        {"role": "user", "content": "Hello, are you working?"}
    ])
    
    print(f"Response: {response.content}")
    print(f"Latency: {response.latency_ms}ms")

asyncio.run(test())
```

## Monitoring:
- Ollama: Check http://localhost:11434
- Watch GPU usage: `nvidia-smi -l 1` or `sudo powermetrics --samplers gpu_power`
- Monitor CPU/RAM: `htop` or Task Manager

## Troubleshooting:
- Slow inference: Reduce model size or use quantization
- Out of memory: Use smaller model or reduce context length
- Connection errors: Check if service is running on correct port
"""

# Alias for backward compatibility
LLMIntegration = ConsciousnessLLM

def print_setup_instructions():
    """Print local LLM setup instructions"""
    print(LOCAL_LLM_SETUP)