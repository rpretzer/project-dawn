/**
 * Tool Browser Component
 * Displays tools, resources, and prompts
 */

export class ToolBrowser {
    constructor(state, ws) {
        this.state = state;
        this.ws = ws;
        
        this.setupStateSubscription();
    }
    
    setupStateSubscription() {
        this.state.subscribe((newState, prevState) => {
            if (newState.tools !== prevState.tools) {
                this.renderTools(newState.tools);
            }
            
            if (newState.resources !== prevState.resources) {
                this.renderResources(newState.resources);
            }
            
            if (newState.prompts !== prevState.prompts) {
                this.renderPrompts(newState.prompts);
            }
        });
    }
    
    renderTools(tools) {
        const container = document.getElementById('tool-list');
        
        if (!tools || tools.length === 0) {
            container.innerHTML = '<div class="empty-state">No tools available</div>';
            return;
        }
        
        container.innerHTML = tools.map(tool => `
            <div class="tool-item" data-tool-name="${tool.name}">
                <div class="item-name">${this.escapeHtml(tool.name)}</div>
                <div class="item-description">${this.escapeHtml(tool.description || '')}</div>
                ${tool.agent_id ? `
                    <div class="item-meta" style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">
                        From: ${this.escapeHtml(tool.agent_id)}
                    </div>
                ` : ''}
            </div>
        `).join('');
        
        // Add click handlers
        container.querySelectorAll('.tool-item').forEach(item => {
            item.addEventListener('click', () => {
                const toolName = item.dataset.toolName;
                const tool = tools.find(t => t.name === toolName);
                if (tool) {
                    this.handleToolClick(tool);
                }
            });
        });
    }
    
    renderResources(resources) {
        const container = document.getElementById('resource-list');
        
        if (!resources || resources.length === 0) {
            container.innerHTML = '<div class="empty-state">No resources available</div>';
            return;
        }
        
        container.innerHTML = resources.map(resource => `
            <div class="resource-item" data-resource-uri="${resource.uri}">
                <div class="item-name">${this.escapeHtml(resource.uri)}</div>
                <div class="item-description">${this.escapeHtml(resource.description || '')}</div>
            </div>
        `).join('');
    }
    
    renderPrompts(prompts) {
        const container = document.getElementById('prompt-list');
        
        if (!prompts || prompts.length === 0) {
            container.innerHTML = '<div class="empty-state">No prompts available</div>';
            return;
        }
        
        container.innerHTML = prompts.map(prompt => `
            <div class="prompt-item" data-prompt-name="${prompt.name}">
                <div class="item-name">${this.escapeHtml(prompt.name)}</div>
                <div class="item-description">${this.escapeHtml(prompt.description || '')}</div>
            </div>
        `).join('');
    }
    
    async handleToolClick(tool) {
        // For now, just show an alert
        // In the future, this would open a tool execution dialog
        alert(`Tool: ${tool.name}\nDescription: ${tool.description || 'No description'}`);
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}



