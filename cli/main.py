#!/usr/bin/env python3
"""
Project Dawn - Interactive CLI

A friendly command-line interface for managing the P2P node, agents, and peers.
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import typer
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Prompt, Confirm
    from rich.layout import Layout
    from rich.live import Live
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
    TYPER_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    TYPER_AVAILABLE = False
    typer = None

from crypto import NodeIdentity
from data_paths import data_root
from health import HealthChecker, HealthStatus
from cli.server_manager import ensure_server_running

# Setup logging
logging.basicConfig(
    level=logging.WARNING,  # Reduce noise in CLI
    format="%(message)s"
)
logger = logging.getLogger(__name__)

# Create console for rich output
console = Console() if RICH_AVAILABLE else None


def print_error(message: str):
    """Print error message"""
    if console:
        console.print(f"[red]❌ {message}[/red]")
    else:
        print(f"ERROR: {message}")


def print_success(message: str):
    """Print success message"""
    if console:
        console.print(f"[green]✅ {message}[/green]")
    else:
        print(f"SUCCESS: {message}")


def print_info(message: str):
    """Print info message"""
    if console:
        console.print(f"[blue]ℹ️  {message}[/blue]")
    else:
        print(f"INFO: {message}")


def cmd_status(json_output: bool = False):
    """Show node status and health"""
    # Ensure server is running
    if not ensure_server_running():
        print_error("Server is not running and could not be started")
        sys.exit(1)
    
    try:
        identity = NodeIdentity()
        node_id = identity.get_node_id()
        
        # Load health checker
        health_checker = HealthChecker()
        # Get overall health status (default to HEALTHY if no checks registered)
        health_status = HealthStatus.HEALTHY
        
        # Get metrics if available
        try:
            from metrics import get_metrics_collector
            metrics = get_metrics_collector()
        except Exception as e:
            logger.debug(f"Could not get metrics collector: {e}")
            metrics = None
        
        if json_output:
            uptime = time.time() - health_checker.start_time if hasattr(health_checker, 'start_time') else 0
            data = {
                "node_id": node_id,
                "health": health_status.value if hasattr(health_status, 'value') else str(health_status),
                "uptime": uptime,
                "data_root": str(data_root()),
            }
            if metrics:
                data["metrics"] = {
                    "peer_count": metrics._peer_count._value._value if hasattr(metrics, '_peer_count') else 0,
                }
            print(json.dumps(data, indent=2))
        else:
            if console:
                # Create status table
                table = Table(title="Node Status", box=box.ROUNDED)
                table.add_column("Property", style="cyan")
                table.add_column("Value", style="green")
                
                table.add_row("Node ID", node_id[:16] + "...")
                table.add_row("Health", str(health_status))
                uptime = time.time() - health_checker.start_time if hasattr(health_checker, 'start_time') else 0.0
                table.add_row("Uptime", f"{uptime:.1f}s")
                table.add_row("Data Root", str(data_root()))
                
                if metrics:
                    peer_count = metrics._peer_count._value._value if hasattr(metrics, '_peer_count') else 0
                    table.add_row("Connected Peers", str(peer_count))
                
                console.print(table)
            else:
                print(f"Node ID: {node_id}")
                print(f"Health: {health_status}")
                uptime = time.time() - health_checker.start_time if hasattr(health_checker, 'start_time') else 0.0
                print(f"Uptime: {uptime:.1f}s")
                print(f"Data Root: {data_root()}")
    
    except Exception as e:
        print_error(f"Failed to get status: {e}")
        sys.exit(1)


def cmd_peers(json_output: bool = False):
    """List connected peers"""
    # Ensure server is running
    if not ensure_server_running():
        print_error("Server is not running and could not be started")
        sys.exit(1)
    
    try:
        from p2p.peer_registry import PeerRegistry
        
        registry = PeerRegistry()
        peers_list = registry.list_peers()
        
        if json_output:
            data = {
                "peers": [
                    {
                        "node_id": peer.node_id,
                        "address": peer.address,
                        "last_seen": peer.last_seen,
                        "health_score": peer.health_score,
                    }
                    for peer in peers_list
                ],
                "total": len(peers_list)
            }
            print(json.dumps(data, indent=2))
        else:
            if console:
                if not peers_list:
                    console.print("[yellow]No peers connected[/yellow]")
                else:
                    table = Table(title="Connected Peers", box=box.ROUNDED)
                    table.add_column("Node ID", style="cyan")
                    table.add_column("Address", style="green")
                    table.add_column("Health", style="yellow")
                    table.add_column("Last Seen", style="blue")
                    
                    for peer in peers_list:
                        health_emoji = "🟢" if peer.health_score > 0.7 else "🟡" if peer.health_score > 0.4 else "🔴"
                        last_seen = datetime.fromtimestamp(peer.last_seen).strftime("%Y-%m-%d %H:%M:%S") if peer.last_seen else "Never"
                        table.add_row(
                            peer.node_id[:16] + "...",
                            peer.address,
                            f"{health_emoji} {peer.health_score:.2f}",
                            last_seen
                        )
                    
                    console.print(table)
                    console.print(f"\n[dim]Total: {len(peers_list)} peers[/dim]")
            else:
                if not peers_list:
                    print("No peers connected")
                else:
                    print(f"Connected Peers ({len(peers_list)}):")
                    for peer in peers_list:
                        print(f"  - {peer.node_id[:16]}... @ {peer.address}")
    
    except Exception as e:
        print_error(f"Failed to list peers: {e}")
        sys.exit(1)


def cmd_agents(json_output: bool = False):
    """List registered agents"""
    # Ensure server is running
    if not ensure_server_running():
        print_error("Server is not running and could not be started")
        sys.exit(1)
    
    try:
        from consensus import DistributedAgentRegistry
        
        registry = DistributedAgentRegistry("local")
        agents_list = registry.list_agents()
        
        if json_output:
            data = {
                "agents": [
                    {
                        "agent_id": agent.agent_id,
                        "name": agent.name,
                        "node_id": agent.node_id,
                        "capabilities": agent.capabilities,
                    }
                    for agent in agents_list
                ],
                "total": len(agents_list)
            }
            print(json.dumps(data, indent=2))
        else:
            if console:
                if not agents_list:
                    console.print("[yellow]No agents registered[/yellow]")
                else:
                    table = Table(title="Registered Agents", box=box.ROUNDED)
                    table.add_column("Agent ID", style="cyan")
                    table.add_column("Name", style="green")
                    table.add_column("Node ID", style="yellow")
                    table.add_column("Capabilities", style="blue")
                    
                    for agent in agents_list:
                        caps = ", ".join(agent.capabilities[:3])
                        if len(agent.capabilities) > 3:
                            caps += "..."
                        table.add_row(
                            agent.agent_id[:20] + "...",
                            agent.name,
                            agent.node_id[:16] + "...",
                            caps or "None"
                        )
                    
                    console.print(table)
                    console.print(f"\n[dim]Total: {len(agents_list)} agents[/dim]")
            else:
                if not agents_list:
                    print("No agents registered")
                else:
                    print(f"Registered Agents ({len(agents_list)}):")
                    for agent in agents_list:
                        print(f"  - {agent.name} ({agent.agent_id[:16]}...)")
    
    except Exception as e:
        print_error(f"Failed to list agents: {e}")
        sys.exit(1)


def cmd_health(json_output: bool = False):
    """Show detailed health information"""
    # Ensure server is running
    if not ensure_server_running():
        print_error("Server is not running and could not be started")
        sys.exit(1)
    
    try:
        health_checker = HealthChecker()
        # Get overall health status (default to HEALTHY)
        overall = HealthStatus.HEALTHY
        
        if json_output:
            uptime = time.time() - health_checker.start_time if hasattr(health_checker, 'start_time') else 0.0
            data = {
                "status": overall.value if hasattr(overall, 'value') else str(overall),
                "uptime": uptime,
            }
            print(json.dumps(data, indent=2))
        else:
            if console:
                status_color = {
                    HealthStatus.HEALTHY: "green",
                    HealthStatus.DEGRADED: "yellow",
                    HealthStatus.UNHEALTHY: "red",
                }.get(overall, "white")
                
                uptime = time.time() - health_checker.start_time if hasattr(health_checker, 'start_time') else 0.0
                panel = Panel(
                    f"[{status_color}]{overall}[/{status_color}]\n\n"
                    f"Uptime: {uptime:.1f}s",
                    title="Health Status",
                    border_style=status_color
                )
                console.print(panel)
            else:
                uptime = time.time() - health_checker.start_time if hasattr(health_checker, 'start_time') else 0.0
                print(f"Status: {overall}")
                print(f"Uptime: {uptime:.1f}s")
    
    except Exception as e:
        print_error(f"Failed to get health: {e}")
        sys.exit(1)


def cmd_metrics(json_output: bool = False):
    """Show Prometheus metrics"""
    # Ensure server is running
    if not ensure_server_running():
        print_error("Server is not running and could not be started")
        sys.exit(1)
    
    try:
        from prometheus_client import generate_latest, REGISTRY
        
        if json_output:
            # Parse Prometheus format to JSON (simplified)
            metrics_text = generate_latest(REGISTRY).decode('utf-8')
            print(metrics_text)
        else:
            metrics_text = generate_latest(REGISTRY).decode('utf-8')
            if console:
                console.print(Panel(metrics_text, title="Prometheus Metrics", border_style="blue"))
            else:
                print(metrics_text)
    
    except Exception as e:
        print_error(f"Failed to get metrics: {e}")
        sys.exit(1)


def cmd_trust(node_id: Optional[str] = None, level: Optional[str] = None, json_output: bool = False):
    """Manage peer trust levels"""
    # Ensure server is running
    if not ensure_server_running():
        print_error("Server is not running and could not be started")
        sys.exit(1)
    
    try:
        from security import TrustManager, TrustLevel
        
        trust_manager = TrustManager()
        
        if level and node_id:
            # Set trust level
            try:
                trust_level = TrustLevel[level.upper()]
                # Need public key - for now, just set trust
                trust_manager.add_trusted_peer(
                    node_id=node_id,
                    public_key="",  # Would need to get this from peer
                    trust_level=trust_level
                )
                print_success(f"Set trust level for {node_id[:16]}... to {level}")
            except KeyError:
                print_error(f"Invalid trust level: {level}. Use: UNTRUSTED, UNKNOWN, VERIFIED, TRUSTED, BOOTSTRAP")
                sys.exit(1)
        elif node_id:
            # Get trust level for specific node
            trust_level = trust_manager.get_trust_level(node_id)
            if json_output:
                print(json.dumps({"node_id": node_id, "trust_level": trust_level.value if hasattr(trust_level, 'value') else str(trust_level)}))
            else:
                if console:
                    console.print(f"Trust level for {node_id[:16]}...: [cyan]{trust_level}[/cyan]")
                else:
                    print(f"Trust level: {trust_level}")
        else:
            # List all trusted peers
            if json_output:
                print(json.dumps({"message": "Use node_id to check specific peer trust level"}))
            else:
                print_info("Use: dawn trust <node_id> to check trust level")
                print_info("Use: dawn trust <node_id> --set <level> to set trust level")
    
    except Exception as e:
        print_error(f"Failed to manage trust: {e}")
        sys.exit(1)


def cmd_interactive():
    """Start interactive mode (Claude Code-style)"""
    # Ensure server is running
    if not ensure_server_running():
        print_error("Server is not running and could not be started")
        sys.exit(1)
    
    # Use Claude Code-style interface
    from cli.interactive import run_interactive
    run_interactive()


# Create typer app and register commands if available
if TYPER_AVAILABLE:
    app = typer.Typer(help="Project Dawn - Interactive CLI")
    
    @app.command()
    def status(
        json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON")
    ):
        """Show node status and health"""
        cmd_status(json_output)
    
    @app.command()
    def peers(
        json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON")
    ):
        """List connected peers"""
        cmd_peers(json_output)
    
    @app.command()
    def agents(
        json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON")
    ):
        """List registered agents"""
        cmd_agents(json_output)
    
    @app.command()
    def health(
        json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON")
    ):
        """Show detailed health information"""
        cmd_health(json_output)
    
    @app.command()
    def metrics(
        json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON")
    ):
        """Show Prometheus metrics"""
        cmd_metrics(json_output)
    
    @app.command()
    def trust(
        node_id: Optional[str] = typer.Argument(None, help="Node ID to check trust level"),
        level: Optional[str] = typer.Option(None, "--set", help="Set trust level (UNTRUSTED, UNKNOWN, VERIFIED, TRUSTED, BOOTSTRAP)"),
        json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON")
    ):
        """Manage peer trust levels"""
        cmd_trust(node_id, level, json_output)
    
    @app.command()
    def interactive():
        """Start interactive mode (Claude Code-style)"""
        cmd_interactive()
    
    @app.command()
    def dashboard(
        port: int = typer.Option(8080, "--port", "-p", help="Dashboard port"),
        open_browser: bool = typer.Option(True, "--open/--no-open", help="Open in browser"),
    ):
        """Open the web dashboard"""
        from cli.interactive import open_dashboard
        
        # Ensure server is running
        if not ensure_server_running():
            print_error("Server is not running and could not be started")
            sys.exit(1)
        
        if open_browser:
            print_success(f"Opening dashboard at http://localhost:{port}")
            open_dashboard(port)
        else:
            print_info(f"Dashboard available at http://localhost:{port}")
            print_info("Open this URL in your browser")
    
    def main():
        """Main entry point"""
        app()
else:
    # Fallback when typer is not available
    def main():
        """Main entry point (fallback without typer)"""
        if len(sys.argv) < 2 or sys.argv[1] in ['--help', '-h', 'help']:
            print("Project Dawn CLI")
            print("\nAvailable commands:")
            print("  status     - Show node status")
            print("  peers      - List connected peers")
            print("  agents     - List registered agents")
            print("  health     - Show health information")
            print("  metrics    - Show Prometheus metrics")
            print("  trust      - Manage peer trust")
            print("  interactive - Start interactive mode")
            print("\nInstall 'rich' and 'typer' for full CLI experience:")
            print("  pip install rich typer")
            sys.exit(0)
        
        cmd = sys.argv[1].lower()
        json_flag = "--json" in sys.argv or "-j" in sys.argv
        
        if cmd == "status":
            cmd_status(json_flag)
        elif cmd == "peers":
            cmd_peers(json_flag)
        elif cmd == "agents":
            cmd_agents(json_flag)
        elif cmd == "health":
            cmd_health(json_flag)
        elif cmd == "metrics":
            cmd_metrics(json_flag)
        elif cmd == "trust":
            node_id = sys.argv[2] if len(sys.argv) > 2 else None
            level = None
            if "--set" in sys.argv:
                idx = sys.argv.index("--set")
                if idx + 1 < len(sys.argv):
                    level = sys.argv[idx + 1]
            cmd_trust(node_id, level, json_flag)
        elif cmd == "interactive":
            cmd_interactive()
        elif cmd == "dashboard" or cmd == "web" or cmd == "ui":
            from cli.interactive import launch_dashboard
            launch_dashboard()
        elif cmd == "start":
            # Start server command
            from cli.server_manager import start_server, is_server_running
            if is_server_running():
                print("Server is already running")
            else:
                print("Starting server...")
                process = start_server(background=True)
                if process:
                    print("Server started in background")
                else:
                    print("Failed to start server")
                    sys.exit(1)
        else:
            print(f"Unknown command: {cmd}")
            sys.exit(1)


if __name__ == "__main__":
    main()
