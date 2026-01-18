"""
API Documentation Generator

Introspects all registered agents and generates a comprehensive Markdown API reference.
"""

import os
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agents import FirstAgent, CoordinationAgent, CodeAgent
from crypto import NodeIdentity

def generate_markdown():
    """Generate Markdown documentation for all agents"""
    
    # Initialize a dummy P2P node for agents that need it
    identity = NodeIdentity()
    # Mock node object
    class MockNode:
        def __init__(self):
            self.node_id = "local_node"
            self.agent_registry = type('obj', (object,), {'list_agents': lambda: []})()
            self.agents = {}
            self.address = "ws://localhost:8000"
    
    node = MockNode()
    
    agents = [
        FirstAgent("agent1", "FirstAgent"),
        CoordinationAgent("coordinator", node, "CoordinationAgent"),
        CodeAgent("code", workspace_path=project_root, name="CodeAgent")
    ]
    
    md = "# Project Dawn - MCP API Reference\n\n"
    md += "This document provides a comprehensive list of all tools, resources, and prompts available in the Project Dawn multi-agent system.\n\n"
    
    for agent in agents:
        md += f"## 🤖 Agent: {agent.name} (`{agent.agent_id}`)\n\n"
        
        # Tools
        md += "### 🛠️ Tools\n\n"
        tools = agent.get_tools()
        if not tools:
            md += "No tools registered.\n\n"
        else:
            for tool in tools:
                md += f"#### `{tool['name']}`\n"
                md += f"{tool['description']}\n\n"
                
                input_schema = tool.get("inputSchema")
                if input_schema and "properties" in input_schema:
                    md += "**Parameters:**\n\n"
                    md += "| Parameter | Type | Description | Required |\n"
                    md += "|-----------|------|-------------|----------|\n"
                    
                    required = input_schema.get("required", [])
                    for prop_name, prop_info in input_schema["properties"].items():
                        p_type = prop_info.get("type", "any")
                        p_desc = prop_info.get("description", "")
                        is_req = "✅" if prop_name in required else ""
                        md += f"| `{prop_name}` | `{p_type}` | {p_desc} | {is_req} |\n"
                    md += "\n"
        
        # Resources
        md += "### 📂 Resources\n\n"
        resources = agent.server.resource_registry.list_resources()
        if not resources:
            md += "No resources registered.\n\n"
        else:
            md += "| URI | Name | Description | MIME Type |\n"
            md += "|-----|------|-------------|-----------|\n"
            for res in resources:
                md += f"| `{res['uri']}` | {res['name']} | {res['description']} | `{res['mimeType']}` |\n"
            md += "\n"
            
        # Prompts
        md += "### 📝 Prompts\n\n"
        prompts = agent.server.prompt_registry.list_prompts()
        if not prompts:
            md += "No prompts registered.\n\n"
        else:
            for prompt in prompts:
                md += f"#### `{prompt['name']}`\n"
                md += f"{prompt['description']}\n\n"
                if prompt.get('arguments'):
                    md += "**Arguments:**\n\n"
                    for arg in prompt['arguments']:
                        is_req = "(Required)" if arg.get('required') else "(Optional)"
                        md += f"- `{arg['name']}` {is_req}: {arg.get('description', '')}\n"
                    md += "\n"
        
        md += "---\n\n"
        
    return md

if __name__ == "__main__":
    print("Generating API documentation...")
    markdown_content = generate_markdown()
    
    output_path = project_root / "API_REFERENCE.md"
    output_path.write_text(markdown_content, encoding="utf-8")
    
    print(f"Documentation generated successfully at {output_path}")
