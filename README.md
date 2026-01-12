# Project Dawn

A decentralized, multi-agent system built on the Model Context Protocol (MCP). Project Dawn enables peer-to-peer communication between AI agents with built-in security, resilience, and observability.

## Features

- **P2P Networking**: Decentralized peer-to-peer communication with encrypted WebSocket transport
- **Multi-Agent System**: Run multiple MCP agents on a single node
- **Security**: Trust management, authentication, authorization, and audit logging
- **Resilience**: Rate limiting, circuit breakers, retry policies, and graceful degradation
- **Observability**: Prometheus metrics, health checks, and structured logging
- **Privacy**: Optional onion routing, message padding, and timing obfuscation
- **Data Persistence**: Automatic state persistence for peers and agents
- **CLI**: Friendly interactive command-line interface
- **Web UI**: Local web interface for monitoring and interaction
- **Docker Support**: Containerized deployment with Docker and Docker Compose

## Quick Start

### Prerequisites

- Python 3.11+
- pip

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd project-dawn

# Install dependencies
pip install -r requirements.txt

# Optional: Install CLI dependencies for enhanced experience
pip install rich typer
```

### Running the Server

```bash
# Start the P2P node server
python server_p2p.py
```

The server will start on:
- **WebSocket**: `ws://localhost:8000`
- **Web UI**: `http://localhost:8080`
- **Metrics/Health**: `http://localhost:9090`

### Using the CLI

```bash
# Make CLI executable
chmod +x dawn

# Check node status
./dawn status

# List connected peers
./dawn peers

# Start interactive mode
./dawn interactive
```

See [CLI Documentation](docs/cli.md) for more details.

## Architecture

### Core Components

- **P2P Node** (`p2p/p2p_node.py`): Main node managing agents, peers, and routing
- **Agents** (`agents/`): MCP agents providing tools and capabilities
- **Transport** (`mcp/encrypted_transport.py`): Encrypted WebSocket transport layer
- **Security** (`security/`): Trust management, authentication, and audit logging
- **Resilience** (`resilience/`): Rate limiting, circuit breakers, and retry policies
- **Observability** (`metrics/`, `health/`): Metrics collection and health checks

### Data Storage

All data is stored under a configurable root directory:

```bash
# Default: ./data
# Override with environment variable:
export PROJECT_DAWN_DATA_ROOT=/path/to/data
```

Data structure:
```
data/
├── mesh/
│   ├── peer_registry.json    # Known peers
│   └── trust.json            # Trust records
├── agents/
│   └── {agent_id}/
│       └── state.json        # Agent state
├── vault/
│   └── llm_config.json       # LLM configuration
└── audit.log                 # Security audit log
```

## Configuration

Project Dawn uses YAML configuration files with environment variable overrides.

### Configuration File

Create `config/config.yaml` (or use `config/default.yaml` as a template):

```yaml
node:
  address: "ws://localhost:8000"
  enable_encryption: true
  enable_privacy: false

security:
  reject_unknown: false  # Reject connections from unknown peers

resilience:
  rate_limit:
    max_requests: 100
    time_window: 60.0
  circuit_breaker:
    failure_threshold: 5
    timeout: 30.0

logging:
  level: "INFO"
  format: "json"  # or "text"
```

See [Configuration Guide](docs/configuration.md) for complete configuration options.

### Environment Variables

- `PROJECT_DAWN_DATA_ROOT`: Override data root directory
- `LIBP2P_ENABLED=true`: Enable libp2p transport (experimental)
- `LOG_LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `LOG_FORMAT`: Set log format (json, text)

## Development

### Running Tests

```bash
# Run all tests
pytest -q

# Run specific test file
pytest tests/test_p2p_node.py

# Run with coverage
pytest --cov=. --cov-report=html
```

### Code Structure

```
project-dawn/
├── agents/          # MCP agents
├── cli/            # Command-line interface
├── config/         # Configuration management
├── consensus/       # Distributed agent registry
├── crypto/         # Cryptographic utilities
├── docs/           # Documentation
├── health/         # Health check framework
├── mcp/            # Model Context Protocol
├── metrics/        # Prometheus metrics
├── p2p/            # P2P networking
├── resilience/     # Resilience patterns
├── security/       # Security framework
├── server_p2p.py   # Main server entry point
└── tests/          # Test suite
```

## Deployment

### Docker

```bash
# Build image
docker build -t project-dawn .

# Run container
docker run -p 8000:8000 -p 8080:8080 -p 9090:9090 project-dawn

# Or use Docker Compose
docker-compose up
```

See [Deployment Guide](docs/deployment.md) for production deployment instructions.

## Security

Project Dawn includes comprehensive security features:

- **Trust Management**: Manage peer trust levels (UNTRUSTED, UNKNOWN, VERIFIED, TRUSTED, BOOTSTRAP)
- **Authentication**: Token-based authentication system
- **Authorization**: Permission-based access control
- **Encryption**: End-to-end encryption for all messages
- **Audit Logging**: Comprehensive security event logging
- **Key Storage**: Secure passphrase-protected key storage

See [Security Documentation](docs/production-checklist.md#security) for security best practices.

## Monitoring

### Metrics

Prometheus metrics are available at `http://localhost:9090/metrics`:

- `dawn_peers_total`: Number of connected peers
- `dawn_messages_processed_total`: Total messages processed
- `dawn_message_latency_seconds`: Message processing latency
- `dawn_connection_attempts_total`: Connection attempts
- `dawn_errors_total`: Error count by type

### Health Checks

Health check endpoints:
- `http://localhost:9090/health`: Overall health status
- `http://localhost:9090/health/ready`: Readiness probe
- `http://localhost:9090/health/live`: Liveness probe

### Logging

Structured JSON logging is enabled by default. Logs include:
- Timestamp
- Log level
- Component name
- Message
- Context (node_id, peer_id, etc.)

## Backup and Restore

```bash
# Backup data directory
./dawn backup

# Or use CLI directly
python -m cli.backup

# Restore from backup
python -m cli.restore <backup-name>
```

## Troubleshooting

Common issues and solutions:

- **No peers connecting**: Check firewall settings and ensure port 8000 is open
- **Connection refused**: Verify the server is running and address is correct
- **Import errors**: Ensure all dependencies are installed (`pip install -r requirements.txt`)
- **Permission errors**: Check file permissions on data directory

See [Troubleshooting Guide](docs/troubleshooting.md) for more help.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[Add your license here]

## Support

For issues, questions, or contributions, please open an issue on GitHub.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.
