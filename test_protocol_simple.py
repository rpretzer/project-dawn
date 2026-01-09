#!/usr/bin/env python3
"""Simple test runner for JSON-RPC protocol (no pytest required)"""

import sys
from mcp.protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
    JSONRPCHandler,
    JSONRPCErrorCode,
)


def test_request():
    """Test JSON-RPC request"""
    print("Testing JSONRPCRequest...")
    
    # Create request
    req = JSONRPCRequest(method="test", params={"key": "value"})
    assert req.method == "test"
    assert req.params == {"key": "value"}
    assert req.id is not None
    print("  ✓ Request creation")
    
    # To/from JSON
    json_str = req.to_json()
    req2 = JSONRPCRequest.from_json(json_str)
    assert req2.method == req.method
    assert req2.params == req.params
    print("  ✓ JSON serialization")
    
    # Auto-generate ID
    req1 = JSONRPCRequest(method="test")
    req2 = JSONRPCRequest(method="test")
    assert req1.id != req2.id
    print("  ✓ Auto ID generation")


def test_response():
    """Test JSON-RPC response"""
    print("\nTesting JSONRPCResponse...")
    
    # Success response
    resp = JSONRPCResponse.success(123, "result")
    assert resp.id == 123
    assert resp.result == "result"
    assert resp.error is None
    print("  ✓ Success response")
    
    # Error response
    error = JSONRPCError.method_not_found("test")
    resp = JSONRPCResponse.error_response(123, error)
    assert resp.error is not None
    assert resp.error.code == JSONRPCErrorCode.METHOD_NOT_FOUND
    print("  ✓ Error response")
    
    # To dict
    data = resp.to_dict()
    assert "error" in data
    assert data["error"]["code"] == JSONRPCErrorCode.METHOD_NOT_FOUND
    print("  ✓ Dict conversion")


def test_handler():
    """Test JSON-RPC handler"""
    print("\nTesting JSONRPCHandler...")
    
    handler = JSONRPCHandler()
    
    # Register method
    def add(a, b):
        return a + b
    
    handler.register_method("add", add)
    assert "add" in handler.method_handlers
    print("  ✓ Method registration")
    
    # Handle request with positional params
    request = JSONRPCRequest(method="add", params=[2, 3], id=1)
    response = handler._handle_request(request)
    assert response is not None
    assert response.result == 5
    print("  ✓ Positional params")
    
    # Handle request with named params
    def greet(name, greeting="Hello"):
        return f"{greeting}, {name}!"
    
    handler.register_method("greet", greet)
    request = JSONRPCRequest(
        method="greet",
        params={"name": "World", "greeting": "Hi"},
        id=2
    )
    response = handler._handle_request(request)
    assert response.result == "Hi, World!"
    print("  ✓ Named params")
    
    # Method not found
    request = JSONRPCRequest(method="nonexistent", params={}, id=3)
    response = handler._handle_request(request)
    assert response.error is not None
    assert response.error.code == JSONRPCErrorCode.METHOD_NOT_FOUND
    print("  ✓ Method not found error")
    
    # Handle JSON string
    json_str = '{"jsonrpc":"2.0","method":"add","params":[4,5],"id":4}'
    response = handler.handle_message(json_str)
    assert response.result == 9
    print("  ✓ JSON string handling")
    
    # Batch request
    batch = [
        {"jsonrpc": "2.0", "method": "add", "params": [1, 2], "id": 5},
        {"jsonrpc": "2.0", "method": "add", "params": [3, 4], "id": 6},
    ]
    responses = handler.handle_message(batch)
    assert isinstance(responses, list)
    assert len(responses) == 2
    assert responses[0].result == 3
    assert responses[1].result == 7
    print("  ✓ Batch request")
    
    # Notification (no response)
    def noop():
        pass
    
    handler.register_method("noop", noop)
    request = JSONRPCRequest(method="noop", params=None, id=None)
    # For notifications (no ID), handler should return None
    # But if ID is None, JSONRPCRequest generates one, so we need to explicitly set it
    request.id = None
    response = handler._handle_request(request)
    # Actually, handler checks if request.id is None after handler runs
    # So it should return None for notifications
    assert response is None, f"Expected None for notification, got {response}"
    print("  ✓ Notification (no response)")
    
    # Invalid JSON
    response = handler.handle_message("not json")
    assert response.error is not None
    assert response.error.code == JSONRPCErrorCode.PARSE_ERROR
    print("  ✓ Invalid JSON error")


def main():
    """Run all tests"""
    print("Running JSON-RPC 2.0 Protocol Tests\n")
    print("=" * 50)
    
    try:
        test_request()
        test_response()
        test_handler()
        
        print("\n" + "=" * 50)
        print("✓ All tests passed!")
        return 0
    
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

