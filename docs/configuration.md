# Configuration Guide

Complete guide to configuring Project Dawn.

---

## Configuration Methods

Project Dawn supports three configuration methods (in order of precedence):

1. **Environment Variables** (highest precedence)
2. **Configuration File** (`config.yaml`)
3. **Default Values** (lowest precedence)

---

## Configuration File

### Location

Configuration file is located at:
- Default: `~/.project-dawn/config.yaml`
- Custom: `$PROJECT_DAWN_DATA_ROOT/config.yaml`

### Format

YAML format (requires PyYAML package):
```yaml
node:
  identity_path: ~/.project-dawn/vault/node_identity.key
  address: ws://0.0.0.0:8000
  data_root: ~/.project-dawn

security:
  trust_level_default: UNKNOWN
  reject_unknown: false
  audit_log_path: ~/.project-dawn/vault/audit.log

resilience:
  rate_limit:
    max_requests: 100
    time_window: 60.0
  circuit_breaker:
    failure_threshold: 5
    timeout: 60.0

logging:
  level: INFO
  format: text
  file: ~/.project-dawn/logs/dawn.log

observability:
  metrics_port: 9090
  enable_tracing: false
```

---

## Configuration Options

### Node Configuration

| Option | Environment Variable | Default | Description |
|--------|---------------------|---------|-------------|
| `identity_path` | - | `~/.project-dawn/vault/node_identity.key` | Path to node identity private key |
| `address` | `PROJECT_DAWN_ADDRESS` | `ws://0.0.0.0:8000` | WebSocket server address |
| `data_root` | `PROJECT_DAWN_DATA_ROOT` | `~/.project-dawn` | Data root directory |

**Example:**
```yaml
node:
  identity_path: /var/lib/project-dawn/vault/node_identity.key
  address: ws://0.0.0.0:8000
  data_root: /var/lib/project-dawn
```

### Security Configuration

| Option | Environment Variable | Default | Description |
|--------|---------------------|---------|-------------|
| `trust_level_default` | `PROJECT_DAWN_TRUST_LEVEL` | `UNKNOWN` | Default trust level for new peers |
| `reject_unknown` | `PROJECT_DAWN_REJECT_UNKNOWN` | `false` | Reject unknown peers (true/false) |
| `audit_log_path` | - | `~/.project-dawn/vault/audit.log` | Path to audit log file |

**Trust Levels:**
- `UNTRUSTED`: Explicitly rejected
- `UNKNOWN`: Not in whitelist (default)
- `VERIFIED`: Verified via signature
- `TRUSTED`: Whitelisted, trusted
- `BOOTSTRAP`: Bootstrap node, highly trusted

**Example:**
```yaml
security:
  trust_level_default: UNKNOWN
  reject_unknown: false  # Allow unknown peers
  audit_log_path: /var/lib/project-dawn/vault/audit.log
```

### Resilience Configuration

| Option | Environment Variable | Default | Description |
|--------|---------------------|---------|-------------|
| `rate_limit.max_requests` | `PROJECT_DAWN_RATE_LIMIT_MAX` | `100` | Max requests per time window |
| `rate_limit.time_window` | `PROJECT_DAWN_RATE_LIMIT_WINDOW` | `60.0` | Time window in seconds |
| `circuit_breaker.failure_threshold` | `PROJECT_DAWN_CB_THRESHOLD` | `5` | Failures before opening circuit |
| `circuit_breaker.timeout` | `PROJECT_DAWN_CB_TIMEOUT` | `60.0` | Timeout before half-open attempt |

**Example:**
```yaml
resilience:
  rate_limit:
    max_requests: 100
    time_window: 60.0
  circuit_breaker:
    failure_threshold: 5
    timeout: 60.0
```

### Logging Configuration

| Option | Environment Variable | Default | Description |
|--------|---------------------|---------|-------------|
| `level` | `LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `format` | `LOG_FORMAT` | `text` | Log format (text or json) |
| `file` | `PROJECT_DAWN_LOG_FILE` | `~/.project-dawn/logs/dawn.log` | Log file path |

**Log Levels:**
- `DEBUG`: Detailed diagnostic information
- `INFO`: General informational messages (default)
- `WARNING`: Warning messages
- `ERROR`: Error messages
- `CRITICAL`: Critical errors

**Log Formats:**
- `text`: Human-readable text format
- `json`: JSON format for log aggregation

**Example:**
```yaml
logging:
  level: INFO
  format: json  # Use JSON for production
  file: /var/log/project-dawn/dawn.log
```

### Observability Configuration

| Option | Environment Variable | Default | Description |
|--------|---------------------|---------|-------------|
| `metrics_port` | `PROJECT_DAWN_METRICS_PORT` | `9090` | Port for metrics and health endpoints |
| `enable_tracing` | `PROJECT_DAWN_ENABLE_TRACING` | `false` | Enable distributed tracing (future) |

**Example:**
```yaml
observability:
  metrics_port: 9090
  enable_tracing: false
```

---

## Environment Variables

All configuration can be overridden via environment variables. Environment variables take precedence over configuration file.

### Common Environment Variables

```bash
# Data and paths
export PROJECT_DAWN_DATA_ROOT=/var/lib/project-dawn
export PROJECT_DAWN_HOST=0.0.0.0
export PROJECT_DAWN_WS_PORT=8000
export PROJECT_DAWN_HTTP_PORT=8080

# Security
export PROJECT_DAWN_TRUST_LEVEL=UNKNOWN
export PROJECT_DAWN_REJECT_UNKNOWN=false

# Logging
export LOG_LEVEL=INFO
export LOG_FORMAT=json
export PROJECT_DAWN_LOG_FILE=/var/log/project-dawn/dawn.log

# Observability
export PROJECT_DAWN_METRICS_PORT=9090
export PROJECT_DAWN_ENABLE_TRACING=false

# Resilience
export PROJECT_DAWN_RATE_LIMIT_MAX=100
export PROJECT_DAWN_RATE_LIMIT_WINDOW=60.0
export PROJECT_DAWN_CB_THRESHOLD=5
export PROJECT_DAWN_CB_TIMEOUT=60.0
```

---

## Configuration Loading

### Programmatic Usage

```python
from config import load_config, get_config

# Load from default location
config = load_config()

# Load from custom location
from pathlib import Path
config = load_config(Path("/etc/project-dawn/config.yaml"))

# Get global config
config = get_config()

# Access configuration
print(config.node["address"])
print(config.security["trust_level_default"])
print(config.logging["level"])
```

### Validation

Configuration is automatically validated on load:

- Log levels validated (must be DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Log formats validated (must be text or json)
- Trust levels validated (must be UNTRUSTED, UNKNOWN, VERIFIED, TRUSTED, BOOTSTRAP)
- Ports validated (must be 1-65535)

Invalid values are replaced with defaults and warnings are logged.

---

## Production Configuration Example

```yaml
# Production configuration
node:
  identity_path: /var/lib/project-dawn/vault/node_identity.key
  address: ws://0.0.0.0:8000
  data_root: /var/lib/project-dawn

security:
  trust_level_default: UNKNOWN
  reject_unknown: true  # Reject unknown peers in production
  audit_log_path: /var/lib/project-dawn/vault/audit.log

resilience:
  rate_limit:
    max_requests: 100
    time_window: 60.0
  circuit_breaker:
    failure_threshold: 5
    timeout: 60.0

logging:
  level: INFO  # Use INFO or WARNING, not DEBUG
  format: json  # JSON format for log aggregation
  file: /var/log/project-dawn/dawn.log

observability:
  metrics_port: 9090
  enable_tracing: false
```

---

## Docker Configuration

In Docker, use environment variables in `docker-compose.yml`:

```yaml
services:
  dawn:
    environment:
      - PROJECT_DAWN_DATA_ROOT=/data
      - LOG_LEVEL=INFO
      - LOG_FORMAT=json
      - PROJECT_DAWN_METRICS_PORT=9090
      - PROJECT_DAWN_REJECT_UNKNOWN=true
```

Or mount a config file:

```yaml
services:
  dawn:
    volumes:
      - ./config.yaml:/data/config.yaml
    environment:
      - PROJECT_DAWN_DATA_ROOT=/data
```

---

## Configuration Tips

1. **Use environment variables for sensitive values**: Never put secrets in config files
2. **Use JSON logging in production**: Easier to parse and aggregate
3. **Set appropriate log levels**: Use INFO or WARNING in production, DEBUG only for troubleshooting
4. **Configure trust policies**: Set `reject_unknown: true` in production
5. **Monitor metrics port**: Restrict access to metrics endpoint (9090) to internal network
6. **Validate configuration**: Always validate config file syntax before deployment

---

## Troubleshooting

See [Troubleshooting Guide](troubleshooting.md) for configuration-related issues.

---

## Additional Resources

- [Deployment Guide](deployment.md)
- [Production Checklist](production-checklist.md)
- [Default Configuration](../config/default.yaml)
