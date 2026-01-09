"""
JSON-RPC 2.0 Protocol Handler

Base protocol for MCP (Model Context Protocol).
Specification: https://www.jsonrpc.org/specification
"""

import asyncio
import json
import uuid
import logging
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import IntEnum

logger = logging.getLogger(__name__)


class JSONRPCErrorCode(IntEnum):
    """JSON-RPC 2.0 standard error codes"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    # Server error codes -32000 to -32099 are reserved


@dataclass
class JSONRPCRequest:
    """JSON-RPC 2.0 Request"""
    method: str
    params: Optional[Union[Dict[str, Any], List[Any]]] = None
    id: Optional[Union[str, int]] = None
    jsonrpc: str = "2.0"
    
    def __post_init__(self):
        """Generate ID if not provided"""
        if self.id is None:
            self.id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-RPC 2.0 request dict"""
        result = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "id": self.id,
        }
        if self.params is not None:
            result["params"] = self.params
        return result
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JSONRPCRequest":
        """Create from dict"""
        if "method" not in data:
            raise ValueError("Missing 'method' in request")
        
        return cls(
            method=data["method"],
            params=data.get("params"),
            id=data.get("id"),
            jsonrpc=data.get("jsonrpc", "2.0"),
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "JSONRPCRequest":
        """Create from JSON string"""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")


@dataclass
class JSONRPCError:
    """JSON-RPC 2.0 Error"""
    code: int
    message: str
    data: Optional[Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-RPC 2.0 error dict"""
        result = {
            "code": self.code,
            "message": self.message,
        }
        if self.data is not None:
            result["data"] = self.data
        return result
    
    @classmethod
    def parse_error(cls, data: Optional[Any] = None) -> "JSONRPCError":
        """Create parse error"""
        return cls(
            code=JSONRPCErrorCode.PARSE_ERROR,
            message="Parse error",
            data=data,
        )
    
    @classmethod
    def invalid_request(cls, data: Optional[Any] = None) -> "JSONRPCError":
        """Create invalid request error"""
        return cls(
            code=JSONRPCErrorCode.INVALID_REQUEST,
            message="Invalid Request",
            data=data,
        )
    
    @classmethod
    def method_not_found(cls, method: str, data: Optional[Any] = None) -> "JSONRPCError":
        """Create method not found error"""
        return cls(
            code=JSONRPCErrorCode.METHOD_NOT_FOUND,
            message="Method not found",
            data={"method": method} if data is None else data,
        )
    
    @classmethod
    def invalid_params(cls, data: Optional[Any] = None) -> "JSONRPCError":
        """Create invalid params error"""
        return cls(
            code=JSONRPCErrorCode.INVALID_PARAMS,
            message="Invalid params",
            data=data,
        )
    
    @classmethod
    def internal_error(cls, data: Optional[Any] = None) -> "JSONRPCError":
        """Create internal error"""
        return cls(
            code=JSONRPCErrorCode.INTERNAL_ERROR,
            message="Internal error",
            data=data,
        )


@dataclass
class JSONRPCResponse:
    """JSON-RPC 2.0 Response"""
    id: Optional[Union[str, int]]
    result: Optional[Any] = None
    error: Optional[JSONRPCError] = None
    jsonrpc: str = "2.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-RPC 2.0 response dict"""
        if self.error is not None:
            return {
                "jsonrpc": self.jsonrpc,
                "id": self.id,
                "error": self.error.to_dict(),
            }
        else:
            return {
                "jsonrpc": self.jsonrpc,
                "id": self.id,
                "result": self.result,
            }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def success(cls, request_id: Optional[Union[str, int]], result: Any) -> "JSONRPCResponse":
        """Create success response"""
        return cls(id=request_id, result=result)
    
    @classmethod
    def error_response(
        cls,
        request_id: Optional[Union[str, int]],
        error: JSONRPCError
    ) -> "JSONRPCResponse":
        """Create error response"""
        return cls(id=request_id, error=error)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JSONRPCResponse":
        """Create from dict"""
        error = None
        if "error" in data:
            error_data = data["error"]
            error = JSONRPCError(
                code=error_data["code"],
                message=error_data["message"],
                data=error_data.get("data"),
            )
        
        return cls(
            id=data.get("id"),
            result=data.get("result"),
            error=error,
            jsonrpc=data.get("jsonrpc", "2.0"),
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "JSONRPCResponse":
        """Create from JSON string"""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")


class JSONRPCHandler:
    """
    JSON-RPC 2.0 Handler
    
    Handles parsing, validation, and routing of JSON-RPC 2.0 messages.
    """
    
    def __init__(self):
        self.method_handlers: Dict[str, Callable] = {}
    
    def register_method(self, method: str, handler: Callable):
        """Register a method handler (can be sync or async)"""
        self.method_handlers[method] = handler
        logger.debug(f"Registered method handler: {method}")
    
    def _is_async(self, handler: Callable) -> bool:
        """Check if handler is async"""
        return asyncio.iscoroutinefunction(handler)
    
    def unregister_method(self, method: str):
        """Unregister a method handler"""
        if method in self.method_handlers:
            del self.method_handlers[method]
            logger.debug(f"Unregistered method handler: {method}")
    
    def _validate_request(self, data: Dict[str, Any]) -> Optional[JSONRPCError]:
        """Validate JSON-RPC 2.0 request"""
        if not isinstance(data, dict):
            return JSONRPCError.invalid_request("Request must be an object")
        
        if "jsonrpc" not in data or data["jsonrpc"] != "2.0":
            return JSONRPCError.invalid_request("Missing or invalid 'jsonrpc' field")
        
        if "method" not in data:
            return JSONRPCError.invalid_request("Missing 'method' field")
        
        if not isinstance(data["method"], str):
            return JSONRPCError.invalid_request("'method' must be a string")
        
        # ID is optional for notifications
        if "id" in data:
            if not isinstance(data["id"], (str, int, type(None))):
                return JSONRPCError.invalid_request("'id' must be string, number, or null")
        
        return None
    
    async def _handle_request_async(self, request: JSONRPCRequest) -> Optional[JSONRPCResponse]:
        """Handle a single request (async version)"""
        # Check if method exists
        if request.method not in self.method_handlers:
            return JSONRPCResponse.error_response(
                request.id,
                JSONRPCError.method_not_found(request.method)
            )
        
        # Call handler
        handler = self.method_handlers[request.method]
        try:
            # Handle both positional and named params
            if isinstance(request.params, list):
                if self._is_async(handler):
                    result = await handler(*request.params)
                else:
                    result = handler(*request.params)
            elif isinstance(request.params, dict):
                if self._is_async(handler):
                    result = await handler(**request.params)
                else:
                    result = handler(**request.params)
            elif request.params is None:
                if self._is_async(handler):
                    result = await handler()
                else:
                    result = handler()
            else:
                return JSONRPCResponse.error_response(
                    request.id,
                    JSONRPCError.invalid_params("Params must be array, object, or null")
                )
            
            # If request has no ID, it's a notification (no response)
            if request.id is None:
                return None
            
            return JSONRPCResponse.success(request.id, result)
        
        except TypeError as e:
            # Invalid params
            logger.warning(f"Invalid params for {request.method}: {e}")
            return JSONRPCResponse.error_response(
                request.id,
                JSONRPCError.invalid_params(str(e))
            )
        except Exception as e:
            # Internal error
            logger.error(f"Error handling {request.method}: {e}", exc_info=True)
            return JSONRPCResponse.error_response(
                request.id,
                JSONRPCError.internal_error(str(e))
            )
    
    def _handle_request(self, request: JSONRPCRequest) -> Optional[JSONRPCResponse]:
        """Handle a single request (sync version - for backward compatibility)"""
        # If handler is async, we can't call it synchronously
        if request.method in self.method_handlers:
            handler = self.method_handlers[request.method]
            if self._is_async(handler):
                # Return a coroutine that needs to be awaited
                raise RuntimeError(f"Method '{request.method}' is async - use handle_message_async")
        
        # Check if method exists
        if request.method not in self.method_handlers:
            return JSONRPCResponse.error_response(
                request.id,
                JSONRPCError.method_not_found(request.method)
            )
        
        # Call handler (sync)
        handler = self.method_handlers[request.method]
        try:
            # Handle both positional and named params
            if isinstance(request.params, list):
                result = handler(*request.params)
            elif isinstance(request.params, dict):
                result = handler(**request.params)
            elif request.params is None:
                result = handler()
            else:
                return JSONRPCResponse.error_response(
                    request.id,
                    JSONRPCError.invalid_params("Params must be array, object, or null")
                )
            
            # If request has no ID, it's a notification (no response)
            if request.id is None:
                return None
            
            return JSONRPCResponse.success(request.id, result)
        
        except TypeError as e:
            # Invalid params
            logger.warning(f"Invalid params for {request.method}: {e}")
            return JSONRPCResponse.error_response(
                request.id,
                JSONRPCError.invalid_params(str(e))
            )
        except Exception as e:
            # Internal error
            logger.error(f"Error handling {request.method}: {e}", exc_info=True)
            return JSONRPCResponse.error_response(
                request.id,
                JSONRPCError.internal_error(str(e))
            )
    
    async def handle_message_async(self, message: Union[str, Dict[str, Any]]) -> Optional[Union[JSONRPCResponse, List[JSONRPCResponse]]]:
        """
        Handle a JSON-RPC 2.0 message (async version)
        
        Args:
            message: JSON string or dict
            
        Returns:
            Response(s) or None for notifications
        """
        # Parse JSON if string
        if isinstance(message, str):
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                return JSONRPCResponse(
                    id=None,
                    error=JSONRPCError.parse_error()
                )
        else:
            data = message
        
        # Handle batch request
        if isinstance(data, list):
            if not data:  # Empty array
                return JSONRPCResponse(
                    id=None,
                    error=JSONRPCError.invalid_request("Empty batch array")
                )
            
            responses = []
            for item in data:
                error = self._validate_request(item)
                if error:
                    responses.append(JSONRPCResponse(id=item.get("id"), error=error))
                    continue
                
                request = JSONRPCRequest.from_dict(item)
                response = await self._handle_request_async(request)
                if response is not None:
                    responses.append(response)
            
            return responses if responses else None
        
        # Handle single request
        error = self._validate_request(data)
        if error:
            return JSONRPCResponse(id=data.get("id"), error=error)
        
        request = JSONRPCRequest.from_dict(data)
        return await self._handle_request_async(request)
    
    def handle_message(self, message: Union[str, Dict[str, Any]]) -> Optional[Union[JSONRPCResponse, List[JSONRPCResponse]]]:
        """
        Handle a JSON-RPC 2.0 message (sync version)
        
        Args:
            message: JSON string or dict
            
        Returns:
            Response(s) or None for notifications
        """
        # Parse JSON if string
        if isinstance(message, str):
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                return JSONRPCResponse(
                    id=None,
                    error=JSONRPCError.parse_error()
                )
        else:
            data = message
        
        # Handle batch request
        if isinstance(data, list):
            if not data:  # Empty array
                return JSONRPCResponse(
                    id=None,
                    error=JSONRPCError.invalid_request("Empty batch array")
                )
            
            responses = []
            for item in data:
                error = self._validate_request(item)
                if error:
                    responses.append(JSONRPCResponse(id=item.get("id"), error=error))
                    continue
                
                request = JSONRPCRequest.from_dict(item)
                response = self._handle_request(request)
                if response is not None:
                    responses.append(response)
            
            return responses if responses else None
        
        # Handle single request
        error = self._validate_request(data)
        if error:
            return JSONRPCResponse(id=data.get("id"), error=error)
        
        request = JSONRPCRequest.from_dict(data)
        return self._handle_request(request)

