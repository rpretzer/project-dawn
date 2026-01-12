# Project Dawn CLI

A friendly command-line interface for managing your P2P node, agents, and peers.

## Installation

The CLI requires additional dependencies:

```bash
pip install rich typer
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

## Usage

### Quick Start

```bash
# Make the CLI executable (if not already)
chmod +x dawn

# Run the CLI
./dawn --help

# Or use Python directly
python -m cli.main --help
```

### Commands

#### Status

Show node status and health:

```bash
dawn status
dawn status --json  # JSON output
```

#### Peers

List connected peers:

```bash
dawn peers
dawn peers --json
```

#### Agents

List registered agents:

```bash
dawn agents
dawn agents --json
```

#### Health

Show detailed health information:

```bash
dawn health
dawn health --json
```

#### Metrics

Show Prometheus metrics:

```bash
dawn metrics
dawn metrics --json
```

#### Trust

Manage peer trust levels:

```bash
# Check trust level for a peer
dawn trust <node_id>

# Set trust level
dawn trust <node_id> --set TRUSTED

# Available levels: UNTRUSTED, UNKNOWN, VERIFIED, TRUSTED, BOOTSTRAP
```

#### Interactive Mode

Start an interactive CLI session:

```bash
dawn interactive
```

In interactive mode, you can type commands directly:

```
dawn> status
dawn> peers
dawn> agents
dawn> help
dawn> exit
```

### Examples

```bash
# Check if node is running
dawn status

# See all connected peers
dawn peers

# Check health
dawn health

# Start interactive mode
dawn interactive
```

## Features

- **Rich Terminal Output**: Beautiful, colored output using the `rich` library
- **JSON Support**: All commands support `--json` flag for machine-readable output
- **Interactive Mode**: Friendly interactive session for quick commands
- **Status Monitoring**: Check node health, peers, and agents
- **Trust Management**: Manage peer trust levels
- **Metrics**: View Prometheus metrics

## Integration

The CLI can be used alongside the main server:

```bash
# Terminal 1: Start the server
python server_p2p.py

# Terminal 2: Use CLI to monitor
dawn status
dawn peers
dawn interactive
```

## Troubleshooting

### "Required packages not installed"

Install the CLI dependencies:

```bash
pip install rich typer
```

### "No peers connected"

This is normal if:
- The node just started
- No other nodes are running
- Network discovery hasn't found peers yet

### "No agents registered"

Agents are registered when the node starts. Make sure `server_p2p.py` is running.

## Future Enhancements

- Real-time status updates
- Node configuration management
- Agent management (start/stop agents)
- Peer connection management
- Backup/restore integration
- Log viewing
