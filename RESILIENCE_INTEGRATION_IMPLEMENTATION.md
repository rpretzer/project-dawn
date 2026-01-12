# Resilience Integration & Security Defaults - Phase 4 Implementation Plan

**Date:** 2025-02-15  
**Status:** 📋 IMPLEMENTATION PLAN (Code integration needed)

## Overview

This document outlines the implementation plan for Phase 4.1: Integrate Resilience Framework and Phase 4.2: Configure Security Defaults. The resilience framework components already exist and are tested. This phase requires integrating them into the core P2P node and transport layers, and configuring security defaults.

---

## 📋 Implementation Plan

### 4.1 Integrate Resilience Framework

#### 1. Rate Limiting in Message Routing

**File:** `p2p/p2p_node.py`

**Changes needed:**
1. Add imports:
   ```python
   from resilience import RateLimiter, RateLimitConfig
   from resilience.errors import RateLimitError
   ```

2. In `__init__`, add rate limiter:
   ```python
   # After metrics initialization
   from config import get_config
   config = get_config()
   self.rate_limiter = RateLimiter(
       default_config=RateLimitConfig(
           max_requests=config.resilience["rate_limit"]["max_requests"],
           time_window=config.resilience["rate_limit"]["time_window"],
       )
   )
   ```

3. In `_route_message()`, add rate limit check before processing:
   ```python
   # After authorization checks, before message processing
   if sender_node_id and sender_node_id != self.node_id:
       allowed, retry_after = self.rate_limiter.check_limit(sender_node_id)
       if not allowed:
           logger.warning(f"Rate limit exceeded for {sender_node_id[:16]}...")
           result = {
               "jsonrpc": "2.0",
               "id": message.get("id"),
               "error": {
                   "code": -32000,
                   "message": f"Rate limit exceeded. Retry after {retry_after:.1f}s",
                   "data": {"retry_after": retry_after},
               }
           }
           latency = time.time() - start_time
           self.metrics.record_message(message_type, "error", latency, message_size)
           return result
   ```

#### 2. Circuit Breakers Per Peer Connection

**File:** `p2p/p2p_node.py`

**Changes needed:**
1. Add imports:
   ```python
   from resilience import CircuitBreaker, CircuitBreakerConfig
   from resilience.errors import CircuitBreakerOpenError
   ```

2. In `__init__`, add circuit breakers dict:
   ```python
   # After peer_connections
   self.circuit_breakers: Dict[str, CircuitBreaker] = {}
   ```

3. In `connect_to_peer()`, add circuit breaker:
   ```python
   # After trust check, before connection attempt
   from config import get_config
   config = get_config()
   
   # Get or create circuit breaker for peer
   if peer.node_id not in self.circuit_breakers:
       self.circuit_breakers[peer.node_id] = CircuitBreaker(
           name=f"peer_{peer.node_id[:16]}",
           config=CircuitBreakerConfig(
               failure_threshold=config.resilience["circuit_breaker"]["failure_threshold"],
               timeout=config.resilience["circuit_breaker"]["timeout"],
           )
       )
   
   circuit_breaker = self.circuit_breakers[peer.node_id]
   
   try:
       # Wrap connection in circuit breaker
       transport = await circuit_breaker.call_async(
           lambda: self._do_connect_to_peer(peer)
       )
       # ... rest of connection logic
   except CircuitBreakerOpenError as e:
       logger.warning(f"Circuit breaker open for {peer.node_id[:16]}...: {e}")
       peer.record_connection_failure()
       return False
   ```

   Note: This requires refactoring the connection logic into a helper method `_do_connect_to_peer()`.

#### 3. Retry Policies for Connection Attempts

**File:** `mcp/encrypted_transport.py`

**Changes needed:**
1. Add imports:
   ```python
   from resilience import RetryPolicy, retry_async
   from resilience.errors import NetworkError, RetryExhaustedError
   ```

2. In `EncryptedWebSocketTransport.connect()`, add retry policy:
   ```python
   retry_policy = RetryPolicy(
       max_attempts=3,
       initial_delay=1.0,
       max_delay=10.0,
       retryable_errors=(ConnectionError, TimeoutError, OSError),
   )
   
   try:
       await retry_async(
           lambda: self._do_connect(),
           retry_policy,
           operation_name="connect",
       )
   except RetryExhaustedError as e:
       raise NetworkError(
           f"Connection failed after {retry_policy.max_attempts} attempts",
           original_error=e,
       ) from e
   ```

   Note: This requires refactoring the connection logic into a helper method `_do_connect()`.

#### 4. Structured Errors

**Files:** `p2p/p2p_node.py`, `mcp/encrypted_transport.py`

**Changes needed:**
- Replace generic `Exception` with structured errors:
  - `RateLimitError` for rate limiting
  - `CircuitBreakerOpenError` for circuit breaker
  - `NetworkError` for connection failures
  - `RetryExhaustedError` for retry exhaustion

### 4.2 Configure Security Defaults

#### 1. Default Trust Policy

**File:** `security/peer_validator.py`

**Changes needed:**
1. In `__init__`, accept config:
   ```python
   def __init__(self, trust_manager: TrustManager, identity: NodeIdentity, 
                audit_logger: AuditLogger, config: Optional[Dict] = None):
       # ...
       from config import get_config
       config = config or get_config().security
       self.reject_unknown = config.get("reject_unknown", False)
   ```

2. In `can_connect()`, check reject_unknown:
   ```python
   trust_level = self.trust_manager.get_trust_level(node_id)
   
   # Reject unknown peers if configured
   if self.reject_unknown and trust_level == TrustLevel.UNKNOWN:
       logger.warning(f"Rejecting connection from unknown peer: {node_id[:16]}...")
       return False
   
   # ... rest of logic
   ```

**File:** `p2p/p2p_node.py`

**Changes needed:**
1. In `__init__`, pass config to PeerValidator:
   ```python
   from config import get_config
   config = get_config()
   self.peer_validator = PeerValidator(
       self.trust_manager, 
       identity, 
       self.audit_logger,
       config.security,
   )
   ```

#### 2. Default Permission Grants

**File:** `security/auth.py` or `p2p/p2p_node.py`

**Changes needed:**
- When peers are verified/trusted, grant default permissions
- Can be done in `connect_to_peer()` or `PeerValidator.can_connect()`

#### 3. Encryption at Rest / Passphrase for Keys

**Files:** `config/config.py`, `server_p2p.py`

**Changes needed:**
- Add config options:
  ```yaml
  security:
    encryption_at_rest: true
    require_passphrase: true
  ```
- These are already implemented in `SecureStorage` and `SecureKeyStorage`

---

## 🎯 Implementation Notes

**Complexity Considerations:**
- `p2p/p2p_node.py` is large (1090 lines), so changes need to be careful
- Circuit breaker integration requires refactoring connection logic
- Retry policy integration requires refactoring connection logic
- Rate limiting is straightforward (add check in existing method)

**Testing:**
- Test rate limiting with high message volume
- Test circuit breakers with failing connections
- Test retry policies with intermittent failures
- Test security defaults with various configurations

**Backward Compatibility:**
- All resilience features are opt-in (can be disabled)
- Security defaults are configurable
- No breaking changes to existing APIs

---

## ✅ Status

**Implementation Status:** 📋 PLAN COMPLETE - Code integration pending

**Next Steps:**
1. Implement rate limiting integration (straightforward)
2. Implement circuit breaker integration (requires refactoring)
3. Implement retry policy integration (requires refactoring)
4. Implement structured errors (replace generic exceptions)
5. Implement security defaults configuration
6. Test all integrations
7. Update documentation

---

## 📝 Notes

This is a comprehensive integration task that requires careful implementation to avoid breaking existing functionality. The resilience framework components are already implemented and tested, so the integration is primarily about:

1. Adding the components to the right places
2. Configuring them appropriately
3. Handling errors correctly
4. Testing thoroughly

The security defaults are primarily configuration changes, which are simpler to implement.
