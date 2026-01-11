"""Tests for JSON-RPC 2.0 protocol handler"""

import pytest
from mcp.protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
    JSONRPCHandler,
    JSONRPCErrorCode,
)


class TestJSONRPCRequest:
    """Test JSON-RPC request"""
    
    def test_create_request(self):
        """Test creating a request"""
        req = JSONRPCRequest(method="test_method", params={"key": "value"})
        assert req.method == "test_method"
        assert req.params == {"key": "value"}
        assert req.id is not None
        assert req.jsonrpc == "2.0"
    
    def test_auto_generate_id(self):
        """Test auto-generating ID"""
        req1 = JSONRPCRequest(method="test")
        req2 = JSONRPCRequest(method="test")
        assert req1.id != req2.id
    
    def test_to_dict(self):
        """Test converting to dict"""
        req = JSONRPCRequest(method="test", params={"key": "value"}, id=123)
        data = req.to_dict()
        assert data == {
            "jsonrpc": "2.0",
            "method": "test",
            "params": {"key": "value"},
            "id": 123,
        }
    
    def test_from_dict(self):
        """Test creating from dict"""
        data = {
            "jsonrpc": "2.0",
            "method": "test",
            "params": {"key": "value"},
            "id": 123,
        }
        req = JSONRPCRequest.from_dict(data)
        assert req.method == "test"
        assert req.params == {"key": "value"}
        assert req.id == 123
    
    def test_to_json(self):
        """Test converting to JSON"""
        req = JSONRPCRequest(method="test", params={"key": "value"})
        json_str = req.to_json()
        data = JSONRPCRequest.from_json(json_str).to_dict()
        assert data["method"] == "test"
        assert data["jsonrpc"] == "2.0"
    
    def test_from_json(self):
        """Test creating from JSON"""
        json_str = '{"jsonrpc":"2.0","method":"test","params":{"key":"value"},"id":123}'
        req = JSONRPCRequest.from_json(json_str)
        assert req.method == "test"
        assert req.params == {"key": "value"}
        assert req.id == 123


class TestJSONRPCResponse:
    """Test JSON-RPC response"""
    
    def test_success_response(self):
        """Test creating success response"""
        resp = JSONRPCResponse.success(123, {"result": "ok"})
        assert resp.id == 123
        assert resp.result == {"result": "ok"}
        assert resp.error is None
    
    def test_error_response(self):
        """Test creating error response"""
        error = JSONRPCError.method_not_found("test")
        resp = JSONRPCResponse.error_response(123, error)
        assert resp.id == 123
        assert resp.error == error
        assert resp.result is None
    
    def test_to_dict_success(self):
        """Test converting success to dict"""
        resp = JSONRPCResponse.success(123, "result")
        data = resp.to_dict()
        assert data == {
            "jsonrpc": "2.0",
            "id": 123,
            "result": "result",
        }
    
    def test_to_dict_error(self):
        """Test converting error to dict"""
        error = JSONRPCError.method_not_found("test")
        resp = JSONRPCResponse.error_response(123, error)
        data = resp.to_dict()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 123
        assert "error" in data
        assert data["error"]["code"] == JSONRPCErrorCode.METHOD_NOT_FOUND


class TestJSONRPCHandler:
    """Test JSON-RPC handler"""
    
    def test_register_method(self):
        """Test registering a method"""
        handler = JSONRPCHandler()
        
        def test_handler():
            return "test"
        
        handler.register_method("test", test_handler)
        assert "test" in handler.method_handlers
    
    def test_handle_method(self):
        """Test handling a method call"""
        handler = JSONRPCHandler()
        
        def add(a: int, b: int) -> int:
            return a + b
        
        handler.register_method("add", add)
        
        request = JSONRPCRequest(method="add", params=[2, 3], id=1)
        response = handler._handle_request(request)
        
        assert response is not None
        assert response.result == 5
        assert response.id == 1
    
    def test_handle_named_params(self):
        """Test handling named parameters"""
        handler = JSONRPCHandler()
        
        def greet(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"
        
        handler.register_method("greet", greet)
        
        request = JSONRPCRequest(
            method="greet",
            params={"name": "World", "greeting": "Hi"},
            id=1
        )
        response = handler._handle_request(request)
        
        assert response is not None
        assert response.result == "Hi, World!"
    
    def test_method_not_found(self):
        """Test method not found error"""
        handler = JSONRPCHandler()
        
        request = JSONRPCRequest(method="nonexistent", params={}, id=1)
        response = handler._handle_request(request)
        
        assert response is not None
        assert response.error is not None
        assert response.error.code == JSONRPCErrorCode.METHOD_NOT_FOUND
    
    def test_handle_json_string(self):
        """Test handling JSON string"""
        handler = JSONRPCHandler()
        
        def echo(text: str) -> str:
            return text
        
        handler.register_method("echo", echo)
        
        json_str = '{"jsonrpc":"2.0","method":"echo","params":["test"],"id":1}'
        response = handler.handle_message(json_str)
        
        assert response is not None
        assert response.result == "test"
    
    def test_handle_batch_request(self):
        """Test handling batch request"""
        handler = JSONRPCHandler()
        
        def add(a: int, b: int) -> int:
            return a + b
        
        handler.register_method("add", add)
        
        batch = [
            {"jsonrpc": "2.0", "method": "add", "params": [1, 2], "id": 1},
            {"jsonrpc": "2.0", "method": "add", "params": [3, 4], "id": 2},
        ]
        
        responses = handler.handle_message(batch)
        
        assert isinstance(responses, list)
        assert len(responses) == 2
        assert responses[0].result == 3
        assert responses[1].result == 7
    
    def test_notification_no_response(self):
        """Test notification (no ID) doesn't return response"""
        handler = JSONRPCHandler()
        
        def noop():
            pass
        
        handler.register_method("noop", noop)
        
        request = JSONRPCRequest(method="noop", params=None, id=None)
        response = handler._handle_request(request)
        
        assert response is None
    
    def test_invalid_json(self):
        """Test handling invalid JSON"""
        handler = JSONRPCHandler()
        
        response = handler.handle_message("not json")
        
        assert response is not None
        assert response.error is not None
        assert response.error.code == JSONRPCErrorCode.PARSE_ERROR
    
    def test_invalid_request(self):
        """Test handling invalid request"""
        handler = JSONRPCHandler()
        
        invalid_request = {"invalid": "request"}
        response = handler.handle_message(invalid_request)
        
        assert response is not None
        assert response.error is not None
        assert response.error.code == JSONRPCErrorCode.INVALID_REQUEST


