#!/usr/bin/env python3
"""
Claude Code-style Interactive CLI

A modern, clean interactive interface for Project Dawn.
"""

import sys
import os
import webbrowser
from pathlib import Path
from typing import List

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.prompt import Prompt
    from rich.layout import Layout
    from rich.live import Live
    from rich import box
    from rich.align import Align
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None

from cli.main import (
    cmd_status, cmd_peers, cmd_agents, cmd_health, 
    cmd_metrics, cmd_trust, print_error, print_success, print_info
)


def _import_commands():
    """Return dict of command functions for lazy access"""
    return {
        'cmd_status': cmd_status,
        'cmd_peers': cmd_peers,
        'cmd_agents': cmd_agents,
        'cmd_health': cmd_health,
        'cmd_metrics': cmd_metrics,
        'cmd_trust': cmd_trust,
        'print_error': print_error,
        'print_success': print_success,
        'print_info': print_info,
    }


def open_dashboard(port: int = 8080):
    """Open the web dashboard in the default browser"""
    url = f"http://localhost:{port}"
    try:
        webbrowser.open(url)
        return True
    except Exception as e:
        print(f"Failed to open browser: {e}")
        print(f"Please open manually: {url}")
        return False


def launch_dashboard():
    """Launch the dashboard and open it in browser"""
    from cli.server_manager import ensure_server_running, check_port
    import time
    import urllib.request
    import urllib.error
    
    # Ensure server is running
    if not ensure_server_running():
        print_error("Server is not running and could not be started")
        return False
    
    # Wait for HTTP server to be ready (check port 8080)
    print_info("Waiting for HTTP server to be ready...")
    max_wait = 15  # Maximum 15 seconds
    wait_interval = 0.5
    waited = 0
    server_ready = False
    
    while waited < max_wait:
        # Check if port 8080 is open
        if check_port('localhost', 8080):
            # Try to fetch the index page to ensure server is responding
            try:
                req = urllib.request.Request('http://localhost:8080/', method='HEAD')
                req.add_header('User-Agent', 'Project-Dawn-CLI/1.0')
                with urllib.request.urlopen(req, timeout=1.0) as response:
                    if response.status == 200:
                        server_ready = True
                        print_success("HTTP server is ready!")
                        break
            except (urllib.error.URLError, OSError):
                # Port might be open but server not ready yet
                pass
        
        time.sleep(wait_interval)
        waited += wait_interval
        if waited < max_wait and not server_ready:
            print_info(f"Waiting for HTTP server... ({waited:.1f}s)")
    
    if not server_ready:
        print_error("HTTP server did not become ready in time")
        print_info("The server may still be starting. Try opening http://localhost:8080 manually.")
        print_info("You can check server status with: ./dawn status")
        return False
    
    # Small additional delay to ensure config.json is written
    time.sleep(0.5)
    
    # Verify config.json exists and has correct WebSocket URL
    try:
        import json
        from pathlib import Path
        project_root = Path(__file__).parent.parent
        config_path = project_root / "frontend" / "config.json"
        
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                ws_url = config.get('wsUrl', '')
                if ws_url:
                    print_success(f"Dashboard config: WebSocket URL = {ws_url}")
                else:
                    print_error("Dashboard config missing WebSocket URL")
        else:
            print_error(f"Dashboard config not found at {config_path}")
    except Exception as e:
        print_error(f"Failed to verify dashboard config: {e}")
    
    # Open dashboard
    print_success("Opening dashboard at http://localhost:8080")
    return open_dashboard(8080)


class ClaudeCodeInterface:
    """Claude Code-style interactive interface"""
    
    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None
        self.command_history: List[str] = []
        self.history_index = -1
        
    def render_header(self) -> str:
        """Render the header bar"""
        if not self.console:
            return "Project Dawn - Interactive CLI"
        
        header_text = Text()
        header_text.append("Project Dawn", style="bold cyan")
        header_text.append(" • ", style="dim")
        header_text.append("Interactive CLI", style="dim white")
        return str(header_text)
    
    def render_prompt(self) -> str:
        """Render the command prompt"""
        if not self.console:
            return "dawn> "
        
        prompt = Text()
        prompt.append("dawn", style="bold cyan")
        prompt.append(" → ", style="dim")
        return str(prompt)
    
    def show_help(self):
        """Show help information"""
        if self.console:
            help_text = """
[bold]Available Commands:[/bold]

  [cyan]status[/cyan]          Show node status and health
  [cyan]peers[/cyan]           List connected peers
  [cyan]agents[/cyan]          List registered agents
  [cyan]health[/cyan]           Show detailed health information
  [cyan]metrics[/cyan]         Show Prometheus metrics
  [cyan]trust <node_id>[/cyan] Check or set peer trust level
  [cyan]dashboard[/cyan]       Open web dashboard in browser
  [cyan]clear[/cyan]           Clear the screen
  [cyan]help[/cyan]            Show this help message
  [cyan]exit[/cyan]            Exit interactive mode

[dim]Tip: Use arrow keys to navigate command history[/dim]
"""
            self.console.print(Panel(help_text, title="Help", border_style="blue", box=box.ROUNDED))
        else:
            print("\nAvailable Commands:")
            print("  status          - Show node status")
            print("  peers           - List connected peers")
            print("  agents          - List registered agents")
            print("  health          - Show health information")
            print("  metrics         - Show Prometheus metrics")
            print("  trust <node_id> - Check trust level")
            print("  dashboard       - Open web dashboard")
            print("  clear           - Clear screen")
            print("  help            - Show help")
            print("  exit            - Exit\n")
    
    def clear_screen(self):
        """Clear the screen"""
        if self.console:
            self.console.clear()
        else:
            os.system('clear' if os.name != 'nt' else 'cls')
    
    def execute_command(self, command: str) -> bool:
        """
        Execute a command
        
        Returns:
            True if should continue, False if should exit
        """
        if not command.strip():
            return True
        
        parts = command.strip().split()
        cmd = parts[0].lower()
        args = parts[1:]
        
        # Add to history
        if command not in self.command_history:
            self.command_history.append(command)
        self.history_index = len(self.command_history)
        
        try:
            if cmd == 'exit' or cmd == 'quit' or cmd == 'q':
                return False
            
            elif cmd == 'help' or cmd == '?':
                self.show_help()
            
            elif cmd == 'clear':
                self.clear_screen()
            
            elif cmd == 'dashboard' or cmd == 'web' or cmd == 'ui':
                launch_dashboard()
            
            elif cmd == 'status':
                commands = _import_commands()
                commands['cmd_status'](json_output=False)
            
            elif cmd == 'peers':
                commands = _import_commands()
                commands['cmd_peers'](json_output=False)
            
            elif cmd == 'agents':
                commands = _import_commands()
                commands['cmd_agents'](json_output=False)
            
            elif cmd == 'health':
                commands = _import_commands()
                commands['cmd_health'](json_output=False)
            
            elif cmd == 'metrics':
                commands = _import_commands()
                commands['cmd_metrics'](json_output=False)
            
            elif cmd == 'trust':
                commands = _import_commands()
                if len(args) > 0:
                    node_id = args[0]
                    level = args[2] if len(args) > 2 and args[1] == '--set' else None
                    commands['cmd_trust'](node_id, level, json_output=False)
                else:
                    commands['print_info']("Usage: trust <node_id> [--set <level>]")
            
            else:
                commands = _import_commands()
                if self.console:
                    self.console.print(f"[red]Unknown command: {cmd}[/red]")
                    self.console.print("[dim]Type 'help' for available commands[/dim]")
                else:
                    commands['print_error'](f"Unknown command: {cmd}")
                    commands['print_info']("Type 'help' for available commands")
        
        except KeyboardInterrupt:
            if self.console:
                self.console.print("\n[yellow]Command interrupted[/yellow]")
            else:
                print("\nCommand interrupted")
        except Exception as e:
            commands = _import_commands()
            commands['print_error'](f"Error executing command: {e}")
        
        return True
    
    def run(self):
        """Run the interactive interface"""
        # Clear screen and show welcome
        self.clear_screen()
        
        if self.console:
            # Claude Code-style welcome
            welcome = Panel(
                Align.center(
                    Text.from_markup(
                        "[bold cyan]Project Dawn[/bold cyan]\n"
                        "[dim]Decentralized Multi-Agent System[/dim]"
                    )
                ),
                box=box.ROUNDED,
                border_style="cyan",
                padding=(1, 2)
            )
            self.console.print(welcome)
            self.console.print()
            self.console.print("[dim]Type 'help' for commands, 'exit' to quit[/dim]\n")
        else:
            print("Project Dawn - Interactive CLI")
            print("Type 'help' for commands, 'exit' to quit\n")
        
        # Main loop
        while True:
            try:
                # Get command
                if self.console:
                    prompt_text = self.render_prompt()
                    command = Prompt.ask(prompt_text, default="")
                else:
                    command = input("dawn> ").strip()
                
                # Execute command
                if not self.execute_command(command):
                    break
                
                # Add spacing between commands
                if self.console:
                    self.console.print()
            
            except KeyboardInterrupt:
                if self.console:
                    self.console.print("\n[yellow]Goodbye![/yellow]")
                else:
                    print("\nGoodbye!")
                break
            except EOFError:
                break
        
        # Exit message
        if self.console:
            self.console.print("[dim]Session ended[/dim]")
        else:
            print("Session ended")


def run_interactive():
    """Run Claude Code-style interactive interface"""
    interface = ClaudeCodeInterface()
    interface.run()
