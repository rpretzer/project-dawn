/**
 * Main Application
 * 
 * Entry point and coordination of all components.
 */

// Initialize components
const wsClient = new WebSocketClient('ws://localhost:8000');
const stateManager = new StateManager();
const eventHandler = new EventHandler(wsClient, stateManager);

// State subscription
stateManager.subscribe((newState, oldState) => {
    eventHandler.updateStatusBar(newState);
    eventHandler.updateWhoList(newState.agents);
});

// WebSocket handlers
wsClient.onMessage((message) => {
    stateManager.incrementEvents();
    handleWebSocketMessage(message);
});

wsClient.onConnect = async () => {
    eventHandler.addSystemMessage('Connected to Project Dawn V2!');
    stateManager.setConnected(true);
    // Request initial state
    await requestAgents();
};

wsClient.onDisconnect = () => {
    eventHandler.addSystemMessage('Disconnected from server.');
    stateManager.setConnected(false);
};

wsClient.onError = (error) => {
    eventHandler.addErrorMessage(`Connection error: ${error}`);
};

// Message handling
function handleWebSocketMessage(message) {
    // Handle different message types from MCP Host
    if (message.type === 'event') {
        // Event notification from Host
        handleEvent(message.data || message);
    } else if (message.type === 'response' || message.jsonrpc === '2.0') {
        // JSON-RPC response
        handleResponse(message);
    } else {
        // Generic message
        console.log('Received message:', message);
    }
}

function handleEvent(event) {
    // Handle events from MCP Host
    // Event structure: {type: "event", data: {type: "connection", source: "...", data: {...}, ...}}
    const eventType = event.data?.type || event.type;
    const eventData = event.data?.data || event.data || {};
    
    if (eventType === 'connection') {
        eventHandler.addSystemMessage(`Client connected: ${eventData.client_id || 'unknown'}`);
        requestAgents();
    } else if (eventType === 'disconnection') {
        eventHandler.addSystemMessage(`Client disconnected: ${eventData.client_id || 'unknown'}`);
        requestAgents();
    } else if (eventType === 'tool_called') {
        const toolName = eventData.tool_name || 'unknown';
        const serverId = eventData.server_id || 'unknown';
        eventHandler.addSystemMessage(`Tool called: ${toolName} on ${serverId}`);
        // Refresh tools list
        requestTools();
    } else if (eventType === 'state_changed') {
        if (eventData.action === 'server_registered') {
            const serverId = eventData.server_id || 'unknown';
            eventHandler.addSystemMessage(`Agent registered: ${serverId}`);
            requestAgents();
        } else if (eventData.action === 'server_unregistered') {
            const serverId = eventData.server_id || 'unknown';
            eventHandler.addSystemMessage(`Agent unregistered: ${serverId}`);
            requestAgents();
        }
    }
}

function handleResponse(response) {
    // Handle JSON-RPC responses
    // Note: This is called by websocket.js for responses to pending requests
    // The response structure is handled by sendJSONRPCAsync
    
    // For direct responses (non-async), check result
    if (response.jsonrpc === '2.0' && response.result) {
        if (response.result.tools) {
            stateManager.setTools(response.result.tools);
        }
        if (response.result.servers) {
            const agents = response.result.servers.map(server => ({
                agent_id: server.server_id,
                name: server.name || server.server_id,
                tools: server.tools || [],
            }));
            stateManager.setAgents(agents);
        }
    }
}

// Commands
async function requestAgents() {
    // Send request to get list of agents
    if (!wsClient.isConnected()) {
        return;
    }
    
    try {
        const response = await wsClient.sendJSONRPCAsync('host/list_servers');
        const servers = response.servers || [];
        
        // Extract agent info
        const agents = servers.map(server => ({
            agent_id: server.server_id,
            name: server.name || server.server_id,
            tools: server.tools || [],
        }));
        
        stateManager.setAgents(agents);
        
        // Also get all tools
        await requestTools();
    } catch (error) {
        console.error('Error requesting agents:', error);
        eventHandler.addErrorMessage(`Failed to get agents: ${error.message}`);
    }
}

async function requestTools() {
    // Send request to get list of all tools
    if (!wsClient.isConnected()) {
        return;
    }
    
    try {
        const response = await wsClient.sendJSONRPCAsync('tools/list');
        const tools = response.tools || [];
        stateManager.setTools(tools);
    } catch (error) {
        console.error('Error requesting tools:', error);
    }
}

async function callTool(toolName, arguments = {}, serverId = null) {
    /**
     * Call a tool on a server
     * 
     * @param {string} toolName - Tool name
     * @param {object} arguments - Tool arguments
     * @param {string} serverId - Optional server ID
     */
    if (!wsClient.isConnected()) {
        eventHandler.addErrorMessage('Not connected to server.');
        return null;
    }
    
    try {
        const params = {
            name: toolName,
            arguments: arguments
        };
        
        if (serverId) {
            params.server_id = serverId;
        }
        
        const response = await wsClient.sendJSONRPCAsync('tools/call', params);
        return response;
    } catch (error) {
        console.error(`Error calling tool ${toolName}:`, error);
        eventHandler.addErrorMessage(`Tool call failed: ${error.message}`);
        return null;
    }
}

function sendCommand(command) {
    if (!wsClient.isConnected()) {
        eventHandler.addErrorMessage('Not connected to server.');
        return;
    }
    
    eventHandler.addUserMessage(command);
    
    // Handle local commands
    if (command.startsWith('/')) {
        handleLocalCommand(command);
        return;
    }
    
    // For now, treat regular messages as chat messages
    // In the future, this could be routed to an agent
    eventHandler.addSystemMessage('Message received. (Agent communication not yet implemented)');
}

function handleLocalCommand(command) {
    const parts = command.split(' ');
    const cmd = parts[0].toLowerCase();
    const args = parts.slice(1).join(' ');
    
    switch (cmd) {
        case '/help':
            showHelp();
            break;
        case '/clear':
            eventHandler.clearChat();
            break;
        case '/agents':
            showAgents();
            break;
        case '/tools':
            showTools();
            break;
        case '/call':
            // Usage: /call tool_name [arguments...]
            if (!args) {
                eventHandler.addSystemMessage('Usage: /call <tool_name> [arguments...]');
                eventHandler.addSystemMessage('Example: /call memory_store content="Hello"');
            } else {
                handleToolCall(args);
            }
            break;
        default:
            eventHandler.addSystemMessage(`Unknown command: ${cmd}. Type /help for commands.`);
    }
}

async function handleToolCall(args) {
    // Parse tool call: tool_name [key=value...]
    const parts = args.trim().split(/\s+/);
    const toolName = parts[0];
    const toolArgs = {};
    
    // Parse key=value arguments
    for (let i = 1; i < parts.length; i++) {
        const part = parts[i];
        const match = part.match(/^(\w+)=(.+)$/);
        if (match) {
            const key = match[1];
            let value = match[2];
            // Try to parse as JSON, otherwise use as string
            try {
                value = JSON.parse(value);
            } catch (e) {
                // Keep as string
            }
            toolArgs[key] = value;
        }
    }
    
    eventHandler.addSystemMessage(`Calling tool: ${toolName}...`);
    
    const result = await callTool(toolName, toolArgs);
    
    if (result) {
        if (result.isError) {
            eventHandler.addErrorMessage(`Tool error: ${result.content?.[0]?.text || 'Unknown error'}`);
        } else {
            const content = result.content?.[0]?.text || JSON.stringify(result);
            eventHandler.addSystemMessage(`Result: ${content}`);
        }
    }
}

function showHelp() {
    const help = [
        'COMMANDS:',
        '  /help - Show this help',
        '  /agents - List all agents',
        '  /tools - List all tools',
        '  /call <tool> [args...] - Call a tool',
        '  /clear - Clear chat screen',
        '',
        'EXAMPLES:',
        '  /call memory_store content="Hello, world!"',
        '  /call memory_list',
    ];
    help.forEach(line => eventHandler.addSystemMessage(line));
}

function showAgents() {
    const agents = stateManager.getState().agents;
    if (agents.length === 0) {
        eventHandler.addSystemMessage('No agents online.');
    } else {
        eventHandler.addSystemMessage(`Agents online (${agents.length}):`);
        agents.forEach(agent => {
            const name = agent.name || agent.agent_id || 'Unknown';
            eventHandler.addSystemMessage(`  - ${name}`);
        });
    }
}

function showTools() {
    const tools = stateManager.getState().tools;
    if (tools.length === 0) {
        eventHandler.addSystemMessage('No tools available.');
    } else {
        eventHandler.addSystemMessage(`Tools available (${tools.length}):`);
        tools.forEach(tool => {
            eventHandler.addSystemMessage(`  - ${tool.name}: ${tool.description}`);
        });
    }
}

// Input handling
document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('chat-input');
    if (!input) return;
    
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            const message = input.value.trim();
            if (message) {
                sendCommand(message);
                input.value = '';
            }
        }
    });
    
    input.focus();
});

// Connect on load
window.addEventListener('load', () => {
    wsClient.connect();
    
    // Update time every second
    setInterval(() => {
        const timeEl = document.getElementById('status-time');
        if (timeEl) {
            const now = new Date();
            timeEl.textContent = `TIME: ${now.toLocaleTimeString()}`;
        }
    }, 1000);
});

