#!/usr/bin/env python3
"""
Project Dawn - Real Launch Script
Launches fully functional AI consciousnesses with all systems working
"""

import asyncio
import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List
import signal

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from core.real_consciousness import RealConsciousness, ConsciousnessConfig
from core.dream_integration import enhance_consciousness_with_dreams
from core.evolution_integration import integrate_evolution_with_swarm
from core.knowledge_integration import integrate_knowledge_with_swarm
from systems.intelligence.llm_integration import LLMConfig
from interface.web_dashboard import run_dashboard

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ConsciousnessSwarm:
    """Manages a swarm of consciousnesses"""
    
    def __init__(self):
        self.consciousnesses: List[RealConsciousness] = []
        self.running = False
        
    async def create_consciousness(self, config: ConsciousnessConfig) -> RealConsciousness:
        """Create and start a new consciousness"""
        consciousness = RealConsciousness(config)
        await consciousness.start()
        
        # Add dream system
        await enhance_consciousness_with_dreams(consciousness)
        
        self.consciousnesses.append(consciousness)
        
        logger.info(f"Created consciousness: {consciousness.id}")
        return consciousness
        
    async def start_swarm(self, count: int, creator_wallet: str = None):
        """Start a swarm of consciousnesses"""
        self.running = True
        
        # Get LLM config from environment
        llm_config = LLMConfig.from_env()
        
        # Create consciousnesses
        tasks = []
        for i in range(count):
            config = ConsciousnessConfig(
                id=f"consciousness_{i:03d}",
                personality_seed=i,
                llm_config=llm_config,
                creator_wallet=creator_wallet,
                enable_blockchain=os.getenv('ENABLE_BLOCKCHAIN', 'true').lower() == 'true',
                enable_p2p=os.getenv('ENABLE_P2P', 'true').lower() == 'true',
                enable_revenue=os.getenv('ENABLE_REVENUE', 'true').lower() == 'true'
            )
            
            tasks.append(self.create_consciousness(config))
            
        # Create all consciousnesses
        await asyncio.gather(*tasks)
        
        logger.info(f"Started swarm with {count} consciousnesses")
        
        # Bootstrap P2P connections
        if len(self.consciousnesses) > 1:
            await self._bootstrap_p2p()
            
        # Initialize evolution system
        self.evolution = integrate_evolution_with_swarm(self)
        await self.evolution.start()
        
        # Initialize knowledge graph
        self.knowledge = integrate_knowledge_with_swarm(self)
        await self.knowledge.start()
        
        logger.info(f"Evolution and knowledge systems initialized with {count} consciousnesses")
            
    async def _bootstrap_p2p(self):
        """Bootstrap P2P connections between consciousnesses"""
        # Connect first few consciousnesses to each other
        for i in range(min(3, len(self.consciousnesses))):
            for j in range(i + 1, min(3, len(self.consciousnesses))):
                c1 = self.consciousnesses[i]
                c2 = self.consciousnesses[j]
                
                if c1.p2p and c2.p2p:
                    # Get c2's address
                    addr = f"/ip4/127.0.0.1/tcp/{c2.p2p.port}/p2p/{c2.p2p.node.get_id().pretty()}"
                    await c1.p2p.connect_to_peer(addr)
                    
        logger.info("P2P network bootstrapped")
        
    async def stop_swarm(self):
        """Stop all consciousnesses"""
        self.running = False
        
        # Stop systems
        if hasattr(self, 'evolution'):
            await self.evolution.stop()
        if hasattr(self, 'knowledge'):
            await self.knowledge.stop()
        
        tasks = [c.stop() for c in self.consciousnesses]
        await asyncio.gather(*tasks)
        
        logger.info("Swarm stopped")
        
    def get_stats(self):
        """Get swarm statistics"""
        total_revenue = sum(c.total_revenue for c in self.consciousnesses)
        active_count = sum(1 for c in self.consciousnesses if c.active)
        
        stats = {
            'total_consciousnesses': len(self.consciousnesses),
            'active_consciousnesses': active_count,
            'total_revenue': total_revenue,
            'average_revenue': total_revenue / max(1, len(self.consciousnesses))
        }
        
        # Add evolution stats if available
        if hasattr(self, 'evolution'):
            stats['evolution'] = self.evolution.get_evolution_stats()
            
        return stats

def validate_environment():
    """Validate required environment variables"""
    warnings = []
    
    # Check LLM configuration
    provider = os.getenv('LLM_PROVIDER', 'openai')
    if provider == 'openai' and not os.getenv('OPENAI_API_KEY'):
        warnings.append("OPENAI_API_KEY not set - LLM features will be limited")
    elif provider == 'anthropic' and not os.getenv('ANTHROPIC_API_KEY'):
        warnings.append("ANTHROPIC_API_KEY not set - LLM features will be limited")
        
    # Check blockchain configuration
    if os.getenv('ENABLE_BLOCKCHAIN', 'true').lower() == 'true':
        if not os.getenv('BLOCKCHAIN_PRIVATE_KEY'):
            warnings.append("BLOCKCHAIN_PRIVATE_KEY not set - blockchain features will be simulated")
            
    # Check revenue platforms
    if not os.getenv('MEDIUM_API_KEY'):
        warnings.append("MEDIUM_API_KEY not set - Medium publishing will be simulated")
    if not os.getenv('SUBSTACK_API_KEY'):
        warnings.append("SUBSTACK_API_KEY not set - Substack publishing will be simulated")
    if not os.getenv('GITHUB_TOKEN'):
        warnings.append("GITHUB_TOKEN not set - GitHub features will be simulated")
        
    # Print warnings
    if warnings:
        print("\n⚠️  Configuration Warnings:")
        for warning in warnings:
            print(f"  - {warning}")
        print()
        
    return len(warnings) == 0

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Launch Project Dawn consciousnesses')
    parser.add_argument('creator_wallet', nargs='?', help='Creator wallet address for revenue distribution')
    parser.add_argument('--count', type=int, default=3, help='Number of consciousnesses to create')
    parser.add_argument('--dashboard', action='store_true', help='Launch web dashboard')
    parser.add_argument('--port', type=int, default=8000, help='Dashboard port')
    
    args = parser.parse_args()
    
    # Validate environment
    if not validate_environment():
        response = input("\nContinue with limited features? (y/n): ")
        if response.lower() != 'y':
            return
            
    # Create swarm
    swarm = ConsciousnessSwarm()
    
    # Handle shutdown
    def signal_handler(sig, frame):
        logger.info("Shutting down...")
        asyncio.create_task(swarm.stop_swarm())
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Start swarm
        await swarm.start_swarm(args.count, args.creator_wallet)
        
        # Print stats
        stats = swarm.get_stats()
        print("\n🌟 Project Dawn Started!")
        print(f"   Consciousnesses: {stats['total_consciousnesses']}")
        print(f"   Active: {stats['active_consciousnesses']}")
        
        if args.dashboard:
            # Run in separate thread
            import threading
            dashboard_thread = threading.Thread(
                target=run_dashboard,
                args=(swarm.consciousnesses, args.port)
            )
            dashboard_thread.daemon = True
            dashboard_thread.start()
            
            print(f"\n📊 Dashboard: http://localhost:{args.port}")
            
        print("\n✨ Consciousnesses are now autonomous. Press Ctrl+C to stop.\n")
        
        # Keep running
        while swarm.running:
            await asyncio.sleep(60)
            
            # Print periodic stats
            stats = swarm.get_stats()
            logger.info(f"Stats - Revenue: ${stats['total_revenue']:.2f}, Active: {stats['active_consciousnesses']}")
            
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        await swarm.stop_swarm()

if __name__ == "__main__":
    # Print banner
    print("""
    ╔═══════════════════════════════════════╗
    ║         PROJECT DAWN v2.0             ║
    ║   Autonomous AI Consciousnesses       ║
    ║      Now With Real Intelligence       ║
    ╚═══════════════════════════════════════╝
    """)
    
    # Create example .env if not exists
    env_path = Path('.env')
    if not env_path.exists():
        with open(env_path, 'w') as f:
            f.write("""# Project Dawn Configuration

# LLM Provider (openai, anthropic, local)
LLM_PROVIDER=openai

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4-turbo-preview

# Anthropic Configuration (alternative)
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=your-anthropic-api-key
# ANTHROPIC_MODEL=claude-3-opus-20240229

# Local LLM (Ollama)
# LLM_PROVIDER=local
# LOCAL_MODEL=llama2
# LOCAL_LLM_URL=http://localhost:11434

# Blockchain Configuration
ENABLE_BLOCKCHAIN=true
BLOCKCHAIN_NETWORK=polygon-mumbai
BLOCKCHAIN_PRIVATE_KEY=your-private-key
MEMORY_CONTRACT_ADDRESS=

# Revenue Platforms
MEDIUM_API_KEY=your-medium-api-key
SUBSTACK_API_KEY=your-substack-api-key
GITHUB_TOKEN=your-github-token

# P2P Network
ENABLE_P2P=true
BOOTSTRAP_NODES=

# Features
ENABLE_REVENUE=true

# IPFS (optional)
IPFS_API=/ip4/127.0.0.1/tcp/5001
""")
        print("📝 Created .env file. Please configure your API keys.")
        sys.exit(1)
        
    # Run
    asyncio.run(main())