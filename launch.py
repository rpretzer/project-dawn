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
from systems.intelligence.llm_integration import LLMConfig
try:
    from interface.web_dashboard import run_dashboard
except ImportError:
    try:
        from interface.web_dashboard import web_dashboard as run_dashboard
    except ImportError:
        run_dashboard = None

# Optional realtime chat server (aiohttp + websockets)
try:
    from interface.realtime_server import run_realtime_server
except Exception:
    run_realtime_server = None

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
        
    async def create_consciousness(self, config: ConsciousnessConfig, safemode: bool = False) -> RealConsciousness:
        """Create and start a new consciousness"""
        consciousness = RealConsciousness(config)
        await consciousness.start(safemode=safemode)
        
        # Add dream system (skip in safemode)
        if not safemode:
            try:
                from core.dream_integration import enhance_consciousness_with_dreams
                await enhance_consciousness_with_dreams(consciousness)
            except Exception as e:
                logger.warning(f"Dream system failed (non-fatal): {e}")
        
        self.consciousnesses.append(consciousness)
        
        logger.info(f"Created consciousness: {consciousness.id}")
        return consciousness
        
    async def start_swarm(self, count: int, creator_wallet: str = None, safemode: bool = False):
        """Start a swarm of consciousnesses"""
        self.running = True
        
        # Get LLM config from environment
        llm_config = LLMConfig.from_env()
        
        # In safemode, disable all optional features
        if safemode:
            logger.info("🚨 Safe mode enabled: Skipping optional systems for minimal startup")
            os.environ['ENABLE_BLOCKCHAIN'] = 'false'
            os.environ['ENABLE_P2P'] = 'false'
            os.environ['ENABLE_REVENUE'] = 'false'
        
        # Create consciousnesses
        tasks = []
        for i in range(count):
            config = ConsciousnessConfig(
                id=f"consciousness_{i:03d}",
                personality_seed=i,
                llm_config=llm_config,
                creator_wallet=creator_wallet,
                enable_blockchain=os.getenv('ENABLE_BLOCKCHAIN', 'true').lower() == 'true' and not safemode,
                enable_p2p=os.getenv('ENABLE_P2P', 'true').lower() == 'true' and not safemode,
                enable_revenue=os.getenv('ENABLE_REVENUE', 'true').lower() == 'true' and not safemode
            )
            
            tasks.append(self.create_consciousness(config, safemode=safemode))
        
        # Create all consciousnesses
        await asyncio.gather(*tasks)
        
        logger.info(f"Started swarm with {count} consciousnesses")
        
        # Skip optional integrations in safemode
        if safemode:
            logger.info("Safe mode: Skipping P2P, evolution, and knowledge integrations")
            return
        
        # Bootstrap P2P connections (only if P2P is enabled)
        if len(self.consciousnesses) > 1 and os.getenv('ENABLE_P2P', 'true').lower() == 'true':
            try:
                await self._bootstrap_p2p()
            except Exception as e:
                logger.warning(f"P2P bootstrap failed (non-fatal): {e}")
                # Continue without P2P
            
        # Initialize evolution system
        try:
            from core.evolution_integration import integrate_evolution_with_swarm
            self.evolution = integrate_evolution_with_swarm(self)
            await self.evolution.start()
        except Exception as e:
            logger.warning(f"Evolution system failed (non-fatal): {e}")
        
        # Initialize knowledge graph
        try:
            from core.knowledge_integration import integrate_knowledge_with_swarm
            self.knowledge = integrate_knowledge_with_swarm(self)
            await self.knowledge.start()
        except Exception as e:
            logger.warning(f"Knowledge system failed (non-fatal): {e}")
        
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
            try:
                evolution_stats = self.evolution.get_evolution_stats()
                # Convert any non-serializable objects to dicts
                if isinstance(evolution_stats, dict):
                    stats['evolution'] = {k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v 
                                          for k, v in evolution_stats.items()}
                else:
                    stats['evolution'] = str(evolution_stats)
            except Exception as e:
                logger.warning(f"Could not get evolution stats: {e}")
                stats['evolution'] = {}
            
        return stats

def validate_environment():
    """Validate required environment variables"""
    warnings = []
    
    # Check LLM configuration
    provider = os.getenv('LLM_PROVIDER', 'openai').lower()
    if provider == 'openai' and not os.getenv('OPENAI_API_KEY'):
        warnings.append("OPENAI_API_KEY not set - LLM features will be limited")
    elif provider == 'anthropic' and not os.getenv('ANTHROPIC_API_KEY'):
        warnings.append("ANTHROPIC_API_KEY not set - LLM features will be limited")
    elif provider in ('ollama', 'local'):
        # Ollama/local LLM - no API key needed, just check if URL is accessible
        ollama_url = os.getenv('OLLAMA_URL') or os.getenv('LOCAL_LLM_URL', 'http://localhost:11434')
        # Don't add warning - Ollama works without API keys
        pass
        
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
    parser.add_argument('--realtime', action='store_true', help='Launch realtime chat server (WebSocket)')
    parser.add_argument('--port', type=int, default=8000, help='Dashboard port')
    parser.add_argument('--safemode', action='store_true', help='Safe mode: Skip optional systems, minimal initialization for debugging')
    
    args = parser.parse_args()
    
    # Validate environment
    if not validate_environment():
        # Check if running in non-interactive mode (no TTY)
        import sys
        if sys.stdin.isatty():
            try:
                response = input("\nContinue with limited features? (y/n): ")
                if response.lower() != 'y':
                    print("Exiting. Please configure your .env file with API keys.")
                    return
            except (EOFError, KeyboardInterrupt):
                print("\n⚠️  Running in non-interactive mode. Continuing with limited features...")
        else:
            print("\n⚠️  Running in non-interactive mode. Continuing with limited features...")
            
    # Create swarm
    swarm = ConsciousnessSwarm()
    
    # Handle shutdown
    def signal_handler(sig, frame):
        logger.info("Shutting down...")
        asyncio.create_task(swarm.stop_swarm())
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Start swarm (with safemode if requested)
        await swarm.start_swarm(args.count, args.creator_wallet, safemode=args.safemode)

        # Start realtime server (preferred for real-time multi-user chat)
        realtime_runner = None
        if args.realtime:
            if run_realtime_server:
                try:
                    realtime_runner = await run_realtime_server(swarm.consciousnesses, args.port, swarm)
                    print(f"\n💬 Realtime chat: http://localhost:{args.port}")
                    print("   WebSocket endpoint: /ws")
                    print("   Commands: /help, /ask, /agents, /spawn")
                except Exception as e:
                    logger.error(f"Failed to start realtime server: {e}")
                    print("\n⚠️  Realtime server failed to start")
            else:
                print("\n⚠️  Realtime server not available (interface.realtime_server import failed)")

        # Start legacy dashboard (polling). Kept for backward compatibility.
        dashboard_started = False
        if args.dashboard:
            # Avoid port conflict if realtime server is running.
            dashboard_port = (args.port + 1) if realtime_runner else args.port
            if run_dashboard:
                try:
                    # Run in separate thread (Flask dev server blocks)
                    import threading
                    dashboard_thread = threading.Thread(
                        target=run_dashboard,
                        args=(swarm.consciousnesses, dashboard_port, swarm),
                        daemon=True
                    )
                    dashboard_thread.start()
                    dashboard_started = True

                    # Give dashboard a moment to start
                    await asyncio.sleep(2)

                    print(f"\n📊 Legacy dashboard: http://localhost:{dashboard_port}")
                    print("   (Polling-based; prefer --realtime for true multi-user real-time chat.)")
                except Exception as e:
                    logger.error(f"Failed to start dashboard: {e}")
                    print("\n⚠️  Dashboard failed to start")
            else:
                print("\n⚠️  Dashboard not available (interface.web_dashboard not found)")
        
        # Print stats (with error handling - non-fatal)
        try:
            stats = swarm.get_stats()
            print("\nProject Dawn Started!")
            print(f"   Consciousnesses: {stats.get('total_consciousnesses', len(swarm.consciousnesses))}")
            print(f"   Active: {stats.get('active_consciousnesses', sum(1 for c in swarm.consciousnesses if c.active))}")
            if 'total_revenue' in stats:
                print(f"   Total Revenue: ${stats.get('total_revenue', 0):.2f}")
        except Exception as e:
            logger.warning(f"Error getting initial stats (non-fatal): {e}")
            print("\nProject Dawn Started!")
            print(f"   Consciousnesses: {len(swarm.consciousnesses)}")
            print(f"   Active: {sum(1 for c in swarm.consciousnesses if c.active)}")
        
        # Open browser if any UI started
        if dashboard_started or realtime_runner:
            try:
                import subprocess
                subprocess.Popen(['xdg-open', f'http://localhost:{args.port}'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except:
                try:
                    subprocess.Popen(['sensible-browser', f'http://localhost:{args.port}'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except:
                    pass
            
        print("\nConsciousnesses are now autonomous. Press Ctrl+C to stop.\n")
        
        # Keep running
        while swarm.running:
            await asyncio.sleep(60)
            
            # Print periodic stats
            try:
                stats = swarm.get_stats()
                logger.info(f"Stats - Revenue: ${stats.get('total_revenue', 0):.2f}, Active: {stats.get('active_consciousnesses', 0)}")
            except Exception as e:
                logger.warning(f"Error getting stats: {e}")
            
    except Exception as e:
        logger.error(f"Error in main: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # Stop realtime server if running
        try:
            if 'realtime_runner' in locals() and realtime_runner:
                await realtime_runner.cleanup()
        except Exception:
            pass

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
    
    # Do not auto-generate .env (can accidentally create/overwrite config in prod).
    # Prefer `.env.example` as a template.
    env_path = Path(".env")
    if not env_path.exists():
        print("⚠️  No .env found. Proceeding with environment variables only.")
        print("   Tip: copy .env.example to .env and configure secrets/keys.")
        
    # Run
    asyncio.run(main())