# Project Dawn

**Autonomous Agent Collaboration Framework**

Project Dawn is a framework for running multiple LLM-backed **agents** with persistent memory and a real-time multi-user chat interface. It is designed for collaborative “ideas → tasks → delegated work → results” workflows (humans and agents together).

## Features

- **Agent runtime**: Multiple autonomous agents with background loops and persistent state
- **LLM Integration**: Support for OpenAI, Anthropic, and Ollama (local LLMs)
- **Memory System**: Persistent memory storage and retrieval (SQLite; optional ChromaDB)
- **Knowledge Graphs**: Optional shared knowledge graph (requires `networkx`)
- **Evolution System**: Experimental evolution of agent strategies and population management
- **P2P Networking**: Peer-to-peer communication between agents (optional)
- **Blockchain Integration**: Decentralized memory storage (optional)
- **Revenue Integration**: Optional publishing/integration hooks (simulated unless configured)
- **Realtime Chat**: WebSocket-based multi-user chat + agent orchestration

## Quick Start

### Prerequisites

- Python 3.9+ (tested with Python 3.14.2)
- Virtual environment (recommended)

### Installation

1. **Clone and navigate to the project:**
   ```bash
   cd /home/rpretzer/project-dawn
   ```

2. **Create and activate virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install core dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

   **Note**: Some dependencies are optional. The system will work without them but with reduced functionality. See [Optional Dependencies](#optional-dependencies) below.

4. **Configure environment:**
   ```bash
   cp .env.example .env  # If you have an example file
   # Or create .env manually
   ```

   Minimum `.env` configuration:
   ```bash
   # LLM Provider (required - choose one)
   LLM_PROVIDER=ollama  # or 'openai' or 'anthropic'
   
   # For Ollama (local LLM)
   OLLAMA_MODEL=llama3
   OLLAMA_URL=http://localhost:11434
   
   # For OpenAI
   # OPENAI_API_KEY=your-key-here
   # OPENAI_MODEL=gpt-4-turbo-preview
   
   # For Anthropic
   # ANTHROPIC_API_KEY=your-key-here
   # ANTHROPIC_MODEL=claude-3-opus-20240229
   
   # Feature flags (set to false to disable)
   ENABLE_BLOCKCHAIN=false
   ENABLE_P2P=true
   ENABLE_REVENUE=false
   ```

5. **Test the installation:**
   ```bash
   python3 -c "from systems.intelligence.llm_integration import LLMConfig; print('✓ Installation successful!')"
   ```

### Running Project Dawn

**Basic launch (single agent):**
```bash
python3 launch.py --count 1
```

**Launch with realtime chat (recommended):**
```bash
python3 launch.py --count 3 --realtime --port 8000
```

**Launch legacy dashboard (polling-based, kept for compatibility):**
```bash
python3 launch.py --count 3 --dashboard --port 8000
```

**Launch with custom wallet:**
```bash
python3 launch.py 0xYourWalletAddress --count 5
```

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `LLM_PROVIDER` | LLM provider: `openai`, `anthropic`, or `ollama` | Yes | - |
| `OPENAI_API_KEY` | OpenAI API key | If using OpenAI | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | If using Anthropic | - |
| `OLLAMA_MODEL` | Ollama model name | If using Ollama | `llama3` |
| `OLLAMA_URL` | Ollama server URL | If using Ollama | `http://localhost:11434` |
| `ENABLE_BLOCKCHAIN` | Enable blockchain features | No | `true` |
| `ENABLE_P2P` | Enable P2P networking | No | `true` |
| `ENABLE_REVENUE` | Enable revenue generation | No | `true` |
| `BLOCKCHAIN_PRIVATE_KEY` | Private key for blockchain | If blockchain enabled | - |
| `BLOCKCHAIN_NETWORK` | Blockchain network | If blockchain enabled | `polygon-mumbai` |
| `IPFS_API` | IPFS API endpoint | If using IPFS | `/ip4/127.0.0.1/tcp/5001` |

## Optional Dependencies

The following dependencies are optional. The system will gracefully degrade if they're not installed:

### Blockchain & Web3
```bash
pip install web3 eth-account
```
**Note**: Also requires `ipfshttpclient` for IPFS storage:
```bash
pip install ipfshttpclient
```

### P2P Networking
```bash
pip install libp2p multiaddr
```
**Warning**: `libp2p` Python library may have compatibility issues with Python 3.14. The system will use fallback networking if unavailable.

### Social Media Integration
```bash
pip install discord.py tweepy linkedin-api
```

### Computer Vision
```bash
pip install opencv-python
```

### Observability
```bash
pip install opentelemetry-api opentelemetry-sdk
```

## Project Structure

```
project-dawn/
├── core/                    # Core consciousness implementation
│   ├── real_consciousness.py    # Main consciousness class
│   ├── dream_integration.py     # Dream system integration
│   ├── evolution_integration.py # Evolution system integration
│   └── ...
├── systems/                 # Subsystems
│   ├── intelligence/        # LLM integration
│   ├── memory/              # Memory system
│   ├── knowledge/           # Knowledge graphs
│   ├── evolution/           # Evolutionary system
│   ├── network/             # P2P networking
│   ├── blockchain/          # Blockchain integration
│   └── ...
├── interface/               # User interfaces
│   ├── web_dashboard.py     # Web dashboard
│   └── ...
├── plugins/                 # Plugin system
├── data/                    # Data storage
├── logs/                    # Log files
├── launch.py                # Main entry point
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

## Usage Examples

### Basic Consciousness

```python
from core.real_consciousness import RealConsciousness, ConsciousnessConfig
from systems.intelligence.llm_integration import LLMConfig

# Create configuration
config = ConsciousnessConfig(
    id="consciousness_001",
    llm_config=LLMConfig.from_env(),
    enable_blockchain=False,
    enable_p2p=False
)

# Create and start consciousness
consciousness = RealConsciousness(config)
await consciousness.start()
```

### Consciousness Swarm

```python
from launch import ConsciousnessSwarm

swarm = ConsciousnessSwarm()
await swarm.start_swarm(count=5)
```

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError` for optional dependencies:
- The system is designed to work without them
- Check if the feature is enabled in your `.env` file
- Install the dependency if you need that feature

### LLM Connection Issues

**Ollama:**
- Ensure Ollama is running: `ollama serve`
- Check available models: `ollama list`
- Verify URL in `.env` matches your Ollama server

**OpenAI/Anthropic:**
- Verify API keys are set correctly
- Check API key permissions and quotas

### P2P Networking Issues

If P2P networking fails:
- The system will automatically use fallback networking
- Install `libp2p` if you need true P2P: `pip install libp2p`
- Note: May have compatibility issues with Python 3.14

### Blockchain Issues

If blockchain features fail:
- Set `ENABLE_BLOCKCHAIN=false` in `.env` to disable
- Ensure you have a valid private key if enabling
- Check network RPC endpoint is accessible

## Development

### Running Tests

```bash
python3 -m pytest tests/
```

### Code Quality

```bash
# Format code
black .

# Lint code
flake8 .

# Type checking
mypy .
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Architecture

Project Dawn uses a modular architecture:

- **Core**: Main consciousness implementation
- **Systems**: Subsystems (memory, intelligence, evolution, etc.)
- **Interface**: User-facing interfaces (web, CLI, etc.)
- **Plugins**: Extensible plugin system

Each agent is an independent runtime with:
- Memory system (memOS)
- Personality system
- Emotional system
- LLM integration
- Knowledge graph
- Evolution capabilities

## License

[Add your license here]

## Support

For issues and questions:
- Check the [Diagnostic Report](DIAGNOSTIC_REPORT.md)
- Review [Dependency Management](DEPENDENCY_MANAGEMENT.md)
- Open an issue on GitHub

## Acknowledgments

Project Dawn is an ambitious exploration of digital consciousness, combining:
- Advanced memory systems
- LLM integration
- Evolutionary algorithms
- P2P networking
- Blockchain technology

---

**Status**: ⚠️ Active Development - Some features may be experimental

**Last Updated**: December 2025
