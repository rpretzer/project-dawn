/**
 * Agent List Component
 * Displays and manages agent list
 */

export class AgentList {
    constructor(state, ws) {
        this.state = state;
        this.ws = ws;
        this.container = document.getElementById('agent-list');
        
        this.setupStateSubscription();
        this.setupWebSocketListeners();
    }
    
    setupStateSubscription() {
        this.state.subscribe((newState, prevState) => {
            if (newState.agents !== prevState.agents) {
                this.renderAgents(newState.agents, newState.selectedAgent);
            }
            
            if (newState.selectedAgent !== prevState.selectedAgent) {
                this.renderAgents(newState.agents, newState.selectedAgent);
            }
        });
    }
    
    setupWebSocketListeners() {
        this.ws.on('connected', () => {
            // Fetch agents on connection
        });
        
        this.ws.on('event', (event) => {
            if (event.data && event.data.type === 'agent_registered') {
                // Refresh agents list
                const currentState = this.state.getState();
                // Trigger refresh (would be handled by app.js)
            }
        });
    }
    
    renderAgents(agents, selectedAgent) {
        if (!agents || agents.length === 0) {
            this.container.innerHTML = '<div class="empty-state">No agents available</div>';
            console.log('AgentList: No agents to render');
            return;
        }
        
        console.log(`AgentList: Rendering ${agents.length} agents`);
        
        this.container.innerHTML = agents.map(agent => {
            const isSelected = selectedAgent && selectedAgent.agent_id === agent.agent_id;
            const statusClass = agent.available !== false ? 'online' : 'offline';
            
            return `
                <div class="agent-item ${isSelected ? 'selected' : ''}" data-agent-id="${agent.agent_id}">
                    <div class="agent-item-header">
                        <span class="agent-name">${this.escapeHtml(agent.name || agent.agent_id)}</span>
                        <span class="agent-status ${statusClass}"></span>
                    </div>
                    ${agent.description ? `
                        <div class="agent-description">${this.escapeHtml(agent.description)}</div>
                    ` : ''}
                    <div class="agent-capabilities">
                        ${agent.tools ? `<span>${agent.tools.length} tools</span>` : ''}
                        ${agent.resources ? `<span>${agent.resources.length} resources</span>` : ''}
                        ${agent.prompts ? `<span>${agent.prompts.length} prompts</span>` : ''}
                    </div>
                </div>
            `;
        }).join('');
        
        // Add click handlers
        this.container.querySelectorAll('.agent-item').forEach(item => {
            item.addEventListener('click', () => {
                const agentId = item.dataset.agentId;
                const agent = agents.find(a => a.agent_id === agentId);
                if (agent) {
                    this.selectAgent(agent);
                }
            });
        });
    }
    
    selectAgent(agent) {
        this.state.setState({ selectedAgent: agent });
        
        // Add system message
        const chatWindow = window.app.chatWindow;
        if (chatWindow) {
            chatWindow.addMessage({
                type: 'system',
                content: `Connected to ${agent.name || agent.agent_id}`,
                timestamp: Date.now(),
            });
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

