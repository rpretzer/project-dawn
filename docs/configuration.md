# Configuration Guide

Project Dawn uses a flexible configuration system that supports YAML files, environment variables, and programmatic configuration.

## Configuration Sources

Configuration is loaded in the following order (later sources override earlier ones):

1. Default values (hardcoded in `config/config.py`)
2. `config/config.yaml` (if exists)
3. `config/default.yaml` (fallback template)
4. Environment variables
5. Programmatic overrides

## Configuration File

Create `config/config.yaml` in the project root:

```yaml
# Node Configuration
node:
  address: "ws://localhost:8000"
  enable_encryption: true
  enable_privacy: false
  bootstrap_nodes: []

# Security Configuration
security:
  reject_unknown: false  # Reject connections from unknown peers
  trust_default: "UNKNOWN"  # Default trust level for new peers
  audit_log_enabled: true

# Resilience Configuration
resilience:
  rate_limit:
    max_requests: 100      # Max requests per time window
    time_window: 60.0      # Time window in seconds
    burst: 10              # Burst capacity
  
  circuit_breaker:
    failure_threshold: 5   # Failures before opening circuit
    timeout: 30.0          # Timeout before half-open
    success_threshold: 2   # Successes to close circuit
  
  retry:
    max_attempts: 3        # Maximum retry attempts
    initial_delay: 1.0     # Initial delay in seconds
    max_delay: 60.0        # Maximum delay in seconds
    exponential_base: 2.0  # Exponential backoff base

# Logging Configuration
logging:
  level: "INFO"            # DEBUG, INFO, WARNING, ERROR
  format: "json"           # json or text
  file: null              # Log file path (null = stdout)

# Observability Configuration
observability:
  metrics_enabled: true
  metrics_port: 9090
  health_check_enabled: true
  health_check_port: 9090
```

## Environment Variables

All configuration can be overridden with environment variables using the format:

```
PROJECT_DAWN_<SECTION>_<KEY>=<value>
```

Examples:

```bash
# Node configuration
export PROJECT_DAWN_NODE_ADDRESS="ws://0.0.0.0:8000"
export PROJECT_DAWN_NODE_ENABLE_ENCRYPTION="true"

# Security configuration
export PROJECT_DAWN_SECURITY_REJECT_UNKNOWN="true"

# Logging configuration
export LOG_LEVEL="DEBUG"
export LOG_FORMAT="text"

# Data root
export PROJECT_DAWN_DATA_ROOT="/custom/data/path"
```

## Configuration Sections

### Node Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `address` | string | `"ws://localhost:8000"` | Node WebSocket address |
| `enable_encryption` | boolean | `true` | Enable message encryption |
| `enable_privacy` | boolean | `false` | Enable privacy features (onion routing, etc.) |
| `bootstrap_nodes` | list | `[]` | List of bootstrap node addresses |

### Security Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `reject_unknown` | boolean | `false` | Reject connections from unknown peers |
| `trust_default` | string | `"UNKNOWN"` | Default trust level (UNTRUSTED, UNKNOWN, VERIFIED, TRUSTED, BOOTSTRAP) |
| `audit_log_enabled` | boolean | `true` | Enable security audit logging |

### Resilience Configuration

#### Rate Limiting

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `max_requests` | integer | `100` | Maximum requests per time window |
| `time_window` | float | `60.0` | Time window in seconds |
| `burst` | integer | `10` | Burst capacity |

#### Circuit Breaker

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `failure_threshold` | integer | `5` | Number of failures before opening circuit |
| `timeout` | float | `30.0` | Timeout in seconds before half-open |
| `success_threshold` | integer | `2` | Number of successes to close circuit |

#### Retry Policy

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `max_attempts` | integer | `3` | Maximum retry attempts |
| `initial_delay` | float | `1.0` | Initial delay in seconds |
| `max_delay` | float | `60.0` | Maximum delay in seconds |
| `exponential_base` | float | `2.0` | Exponential backoff base |

### Logging Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `level` | string | `"INFO"` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `format` | string | `"json"` | Log format (json, text) |
| `file` | string/null | `null` | Log file path (null = stdout) |

### Observability Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `metrics_enabled` | boolean | `true` | Enable Prometheus metrics |
| `metrics_port` | integer | `9090` | Metrics HTTP server port |
| `health_check_enabled` | boolean | `true` | Enable health check endpoints |
| `health_check_port` | integer | `9090` | Health check HTTP server port |

## Programmatic Configuration

You can also configure Project Dawn programmatically:

```python
from config import Config, load_config

# Load configuration
config = load_config()

# Override specific values
config.node.address = "ws://0.0.0.0:8000"
config.security.reject_unknown = True

# Save configuration
config.save("config/config.yaml")
```

## Configuration Validation

Configuration is validated on load. Invalid values will raise `ValueError` with a descriptive error message.

## Production Configuration

For production deployments, consider:

1. **Security**:
   ```yaml
   security:
     reject_unknown: true  # Only allow known peers
     trust_default: "UNTRUSTED"
   ```

2. **Resilience**:
   ```yaml
   resilience:
     rate_limit:
       max_requests: 1000  # Higher limit for production
       time_window: 60.0
     circuit_breaker:
       failure_threshold: 10
       timeout: 60.0
   ```

3. **Logging**:
   ```yaml
   logging:
     level: "INFO"  # Don't use DEBUG in production
     format: "json"  # Structured logging for log aggregation
     file: "/var/log/project-dawn/app.log"
   ```

4. **Observability**:
   ```yaml
   observability:
     metrics_enabled: true
     metrics_port: 9090
     health_check_enabled: true
   ```

## Configuration Examples

### Development

```yaml
node:
  address: "ws://localhost:8000"
  enable_encryption: true

security:
  reject_unknown: false

logging:
  level: "DEBUG"
  format: "text"
```

### Production

```yaml
node:
  address: "ws://0.0.0.0:8000"
  enable_encryption: true
  enable_privacy: true

security:
  reject_unknown: true
  trust_default: "UNTRUSTED"

resilience:
  rate_limit:
    max_requests: 1000
    time_window: 60.0

logging:
  level: "INFO"
  format: "json"
  file: "/var/log/project-dawn/app.log"
```

## Troubleshooting

### Configuration Not Loading

- Check file path: `config/config.yaml` should be in project root
- Verify YAML syntax is valid
- Check file permissions

### Environment Variables Not Working

- Use format: `PROJECT_DAWN_<SECTION>_<KEY>`
- Use uppercase and underscores
- Restart the server after setting environment variables

### Default Values

If configuration file doesn't exist, default values from `config/default.yaml` are used. You can copy this file to `config/config.yaml` and customize it.
