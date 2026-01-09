/**
 * Event Handling
 * 
 * Handles UI events and updates.
 */

class EventHandler {
    constructor(wsClient, stateManager) {
        this.wsClient = wsClient;
        this.stateManager = stateManager;
    }
    
    addMessage(type, sender, message, data = null) {
        const chatRoom = document.getElementById('chat-room');
        if (!chatRoom) return;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        
        const timestamp = new Date().toLocaleTimeString();
        messageDiv.innerHTML = `
            <span class="timestamp">[${timestamp}]</span>
            <strong>&lt;${sender}&gt;</strong> ${this.escapeHtml(message)}
        `;
        
        chatRoom.appendChild(messageDiv);
        chatRoom.scrollTop = chatRoom.scrollHeight;
    }
    
    addSystemMessage(message) {
        this.addMessage('system', 'SYSTEM', message);
    }
    
    addUserMessage(message) {
        this.addMessage('user', 'USER', message);
    }
    
    addAgentMessage(agent, message) {
        this.addMessage('agent', agent, message);
    }
    
    addErrorMessage(message) {
        this.addMessage('error', 'ERROR', message);
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    updateStatusBar(state) {
        const agentsCount = state.agents ? state.agents.length : 0;
        const toolsCount = state.tools ? state.tools.length : 0;
        
        const agentsEl = document.getElementById('status-agents');
        const toolsEl = document.getElementById('status-tools');
        const eventsEl = document.getElementById('status-events');
        const timeEl = document.getElementById('status-time');
        
        if (agentsEl) agentsEl.textContent = `AGENTS: ${agentsCount}`;
        if (toolsEl) toolsEl.textContent = `TOOLS: ${toolsCount}`;
        if (eventsEl) eventsEl.textContent = `EVENTS: ${state.events || 0}`;
        if (timeEl) {
            const now = new Date();
            timeEl.textContent = `TIME: ${now.toLocaleTimeString()}`;
        }
    }
    
    updateWhoList(agents) {
        const whoContent = document.getElementById('who-content');
        if (!whoContent) return;
        
        if (!agents || agents.length === 0) {
            whoContent.innerHTML = '<div class="who-item">No agents online</div>';
            return;
        }
        
        const items = agents.map(agent => {
            const name = agent.name || agent.agent_id || 'Unknown';
            return `<div class="who-item active">${name}</div>`;
        }).join('');
        
        whoContent.innerHTML = items;
    }
    
    clearChat() {
        const chatRoom = document.getElementById('chat-room');
        if (chatRoom) {
            chatRoom.innerHTML = '';
            this.addSystemMessage('Chat cleared.');
        }
    }
}



