/**
 * Project Dawn - Simplified UI
 * Clean chat interface with Simple/Advanced mode toggle
 */

class WebSocketClient {
    constructor() {
        this.ws = null;
        this.url = 'ws://localhost:8000';
        this.connected = false;
        this.pending = new Map();
        this.requestId = 0;
        this.onConnect = null;
        this.onDisconnect = null;
        this.onMessage = null;
    }

    connect(url) {
        if (url) this.url = url;
        if (this.ws?.readyState === WebSocket.OPEN) return;

        try {
            this.ws = new WebSocket(this.url);

            this.ws.onopen = () => {
                this.connected = true;
                this.updateUI(true);
                if (this.onConnect) this.onConnect();
            };

            this.ws.onclose = () => {
                this.connected = false;
                this.updateUI(false);
                if (this.onDisconnect) this.onDisconnect();
                // Reconnect after 3 seconds
                setTimeout(() => this.connect(), 3000);
            };

            this.ws.onerror = (err) => {
                console.error('WebSocket error:', err);
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    // Handle pending request responses
                    if (data.id && this.pending.has(data.id)) {
                        const { resolve, reject } = this.pending.get(data.id);
                        this.pending.delete(data.id);
                        if (data.error) {
                            reject(data.error);
                        } else {
                            resolve(data.result ?? data);
                        }
                        return;
                    }
                    // Handle other messages
                    if (this.onMessage) this.onMessage(data);
                } catch (e) {
                    console.error('Parse error:', e);
                }
            };
        } catch (err) {
            console.error('Connection failed:', err);
            this.updateUI(false);
        }
    }

    updateUI(connected) {
        const indicator = document.querySelector('.status-indicator');
        const text = document.querySelector('.status-text');
        if (indicator) {
            indicator.classList.toggle('connected', connected);
        }
        if (text) {
            text.textContent = connected ? 'Connected' : 'Connecting...';
        }
    }

    async request(method, params = {}) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            throw new Error('Not connected');
        }
        const id = `req-${Date.now()}-${this.requestId++}`;
        return new Promise((resolve, reject) => {
            this.pending.set(id, { resolve, reject });
            this.ws.send(JSON.stringify({
                jsonrpc: '2.0',
                id,
                method,
                params
            }));
            // Timeout after 30s
            setTimeout(() => {
                if (this.pending.has(id)) {
                    this.pending.delete(id);
                    reject(new Error('Request timeout'));
                }
            }, 30000);
        });
    }

    isConnected() {
        return this.connected && this.ws?.readyState === WebSocket.OPEN;
    }
}

class App {
    constructor() {
        this.ws = new WebSocketClient();
        // Use unique keys to avoid conflicts with old settings
        this.mode = localStorage.getItem('dawn_mode') || 'simple';
        this.theme = localStorage.getItem('dawn_theme') || 'light';
        this.agentId = 'agent1';
        this.selectedItem = null;

        this.init();
    }

    init() {
        // Apply saved settings
        document.body.classList.remove('mode-simple', 'mode-advanced');
        document.body.classList.add(`mode-${this.mode}`);
        document.body.classList.remove('theme-light', 'theme-dark');
        document.body.classList.add(`theme-${this.theme}`);

        // Update mode toggle label
        this.updateModeLabel();

        // Setup event handlers
        this.setupModeToggle();
        this.setupThemeToggle();
        this.setupChat();
        this.setupTabs();
        this.setupLLM();
        this.setupAgentSelect();

        // WebSocket callbacks
        this.ws.onConnect = () => this.onConnected();
        this.ws.onDisconnect = () => this.onDisconnected();
        this.ws.onMessage = (data) => this.onMessage(data);

        // Load config and connect
        this.loadConfigAndConnect();
    }

    async loadConfigAndConnect() {
        try {
            const res = await fetch('config.json', { cache: 'no-store' });
            if (res.ok) {
                const config = await res.json();
                if (config.wsUrl) {
                    this.ws.connect(config.wsUrl);
                    return;
                }
            }
        } catch (e) {
            console.warn('Config not found, using default');
        }
        this.ws.connect();
    }

    onConnected() {
        this.loadAgents();
        this.loadPeers();
        if (this.mode === 'advanced') {
            this.loadInventory();
            this.loadLLMConfig();
        }
    }

    onDisconnected() {
        document.getElementById('peer-count').textContent = '0';
    }

    onMessage(data) {
        if (data?.content) {
            this.addMessage(data.actor || 'Agent', data.content, 'agent');
        }
    }

    // Mode Toggle
    setupModeToggle() {
        const btn = document.getElementById('mode-toggle');
        if (btn) {
            btn.addEventListener('click', () => {
                this.mode = this.mode === 'simple' ? 'advanced' : 'simple';
                localStorage.setItem('dawn_mode', this.mode);
                document.body.classList.remove('mode-simple', 'mode-advanced');
                document.body.classList.add(`mode-${this.mode}`);
                this.updateModeLabel();

                // Load advanced data if switching to advanced
                if (this.mode === 'advanced' && this.ws.isConnected()) {
                    this.loadInventory();
                    this.loadLLMConfig();
                }
            });
        }
    }

    updateModeLabel() {
        const label = document.querySelector('.mode-label');
        if (label) {
            label.textContent = this.mode === 'simple' ? 'Simple' : 'Advanced';
        }
    }

    // Theme Toggle
    setupThemeToggle() {
        const btn = document.getElementById('theme-toggle');
        if (btn) {
            btn.addEventListener('click', () => {
                this.theme = this.theme === 'light' ? 'dark' : 'light';
                localStorage.setItem('dawn_theme', this.theme);
                document.body.classList.remove('theme-light', 'theme-dark');
                document.body.classList.add(`theme-${this.theme}`);
            });
        }
    }

    // Chat
    setupChat() {
        const input = document.getElementById('chat-input');
        const sendBtn = document.getElementById('send-button');

        const send = () => {
            const text = input?.value.trim();
            if (!text) return;

            // Show user message
            this.addMessage('You', text, 'user');
            input.value = '';
            input.style.height = 'auto';

            // Clear welcome message
            const welcome = document.querySelector('.welcome-message');
            if (welcome) welcome.remove();

            // Send to agent
            if (this.ws.isConnected()) {
                this.ws.request(`${this.agentId}/chat/message`, {
                    message: text,
                    room_id: 'main'
                }).then(result => {
                    if (result?.content) {
                        this.addMessage(result.agent_id || this.agentId, result.content, 'agent');
                    }
                }).catch(err => {
                    this.addMessage('System', `Error: ${err.message}`, 'system');
                });
            } else {
                this.addMessage('System', 'Not connected to server', 'system');
            }
        };

        sendBtn?.addEventListener('click', send);
        input?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                send();
            }
        });

        // Auto-resize
        input?.addEventListener('input', () => {
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 120) + 'px';
        });
    }

    addMessage(sender, content, type = 'agent') {
        const container = document.getElementById('messages');
        if (!container) return;

        const msg = document.createElement('div');
        msg.className = `message ${type}`;

        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        msg.innerHTML = `
            <div class="message-header">
                <span class="message-sender">${this.escapeHtml(sender)}</span>
                <span class="message-time">${time}</span>
            </div>
            <div class="message-content">${this.escapeHtml(content)}</div>
        `;

        container.appendChild(msg);
        container.scrollTop = container.scrollHeight;
    }

    // Agents
    setupAgentSelect() {
        const select = document.getElementById('agent-select');
        select?.addEventListener('change', () => {
            this.agentId = select.value || 'agent1';
            if (this.mode === 'advanced') {
                this.loadInventory();
            }
        });
    }

    async loadAgents() {
        if (!this.ws.isConnected()) return;
        try {
            const result = await this.ws.request('node/list_agents');
            const agents = result.agents || [];

            document.getElementById('agent-count').textContent = agents.length;

            const select = document.getElementById('agent-select');
            if (select) {
                select.innerHTML = agents.map(a =>
                    `<option value="${a.agent_id}" ${a.agent_id === this.agentId ? 'selected' : ''}>
                        ${this.escapeHtml(a.name || a.agent_id)}
                    </option>`
                ).join('');
            }
        } catch (e) {
            console.warn('Failed to load agents:', e);
        }
    }

    // Peers
    async loadPeers() {
        if (!this.ws.isConnected()) return;
        try {
            const result = await this.ws.request('node/list_peers');
            const peers = result.peers || [];

            document.getElementById('peer-count').textContent = peers.length;

            const list = document.getElementById('peer-list-compact');
            if (list) {
                if (peers.length === 0) {
                    list.innerHTML = '<div class="empty-state">No peers connected</div>';
                } else {
                    list.innerHTML = peers.map(p => `
                        <div class="peer-item">
                            <div class="peer-avatar">${(p.peerId || p.peer_id || '??').slice(0, 2).toUpperCase()}</div>
                            <div class="peer-info">
                                <div class="peer-name">${this.escapeHtml(p.peerId || p.peer_id || 'Unknown')}</div>
                                <div class="peer-status">${this.escapeHtml(p.address || 'Connected')}</div>
                            </div>
                        </div>
                    `).join('');
                }
            }
        } catch (e) {
            console.warn('Failed to load peers:', e);
        }
    }

    // Tabs (Advanced mode)
    setupTabs() {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const tab = btn.dataset.tab;

                // Update buttons
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                // Update panels
                document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
                document.getElementById(`${tab}-panel`)?.classList.add('active');

                this.clearDetail();
            });
        });
    }

    // Inventory (Tools/Resources/Prompts)
    async loadInventory() {
        if (!this.ws.isConnected()) return;
        try {
            const [tools, resources, prompts] = await Promise.all([
                this.ws.request(`${this.agentId}/tools/list`),
                this.ws.request(`${this.agentId}/resources/list`),
                this.ws.request(`${this.agentId}/prompts/list`)
            ]);

            this.renderItemList('tool-list', tools.tools || [], 'tool');
            this.renderItemList('resource-list', resources.resources || [], 'resource');
            this.renderItemList('prompt-list', prompts.prompts || [], 'prompt');
        } catch (e) {
            console.warn('Failed to load inventory:', e);
        }
    }

    renderItemList(containerId, items, type) {
        const container = document.getElementById(containerId);
        if (!container) return;

        if (items.length === 0) {
            container.innerHTML = '<div class="empty-state">No items available</div>';
            return;
        }

        container.innerHTML = items.map((item, i) => `
            <div class="item-card" data-type="${type}" data-index="${i}" data-item='${JSON.stringify(item)}'>
                <div class="item-name">${this.escapeHtml(item.name || item.uri || 'Unnamed')}</div>
                <div class="item-desc">${this.escapeHtml(item.description || '')}</div>
            </div>
        `).join('');

        // Click handlers
        container.querySelectorAll('.item-card').forEach(card => {
            card.addEventListener('click', () => {
                container.querySelectorAll('.item-card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                this.showDetail(card.dataset.type, JSON.parse(card.dataset.item));
            });
        });
    }

    showDetail(type, item) {
        this.selectedItem = { type, item };

        const title = document.getElementById('detail-title');
        const desc = document.getElementById('detail-desc');
        const form = document.getElementById('detail-form');
        const actions = document.getElementById('detail-actions');
        const output = document.getElementById('detail-output');

        if (title) title.textContent = item.name || item.uri || 'Item';
        if (desc) desc.textContent = item.description || 'No description';
        if (form) form.innerHTML = '';
        if (actions) actions.innerHTML = '';
        if (output) output.textContent = '';

        if (type === 'tool') {
            form.innerHTML = '<textarea placeholder="Arguments (JSON)"></textarea>';
            actions.innerHTML = '<button class="btn-primary" id="run-action">Run Tool</button>';
            document.getElementById('run-action')?.addEventListener('click', () => this.runTool(item));
        } else if (type === 'resource') {
            actions.innerHTML = '<button class="btn-primary" id="run-action">Read Resource</button>';
            document.getElementById('run-action')?.addEventListener('click', () => this.readResource(item));
        } else if (type === 'prompt') {
            form.innerHTML = '<textarea placeholder="Arguments (JSON)"></textarea>';
            actions.innerHTML = '<button class="btn-primary" id="run-action">Load Prompt</button>';
            document.getElementById('run-action')?.addEventListener('click', () => this.loadPrompt(item));
        }
    }

    clearDetail() {
        this.selectedItem = null;
        const title = document.getElementById('detail-title');
        const desc = document.getElementById('detail-desc');
        if (title) title.textContent = 'Select an item';
        if (desc) desc.textContent = 'Choose a tool, resource, or prompt from the list above.';
        document.getElementById('detail-form').innerHTML = '';
        document.getElementById('detail-actions').innerHTML = '';
        document.getElementById('detail-output').textContent = '';
    }

    async runTool(item) {
        const textarea = document.querySelector('#detail-form textarea');
        const output = document.getElementById('detail-output');
        let args = {};

        try {
            const raw = textarea?.value.trim();
            if (raw) args = JSON.parse(raw);
        } catch (e) {
            output.textContent = 'Invalid JSON';
            return;
        }

        try {
            const result = await this.ws.request(`${this.agentId}/tools/call`, {
                name: item.name,
                arguments: args
            });
            output.textContent = JSON.stringify(result, null, 2);
        } catch (e) {
            output.textContent = `Error: ${e.message}`;
        }
    }

    async readResource(item) {
        const output = document.getElementById('detail-output');
        try {
            const result = await this.ws.request(`${this.agentId}/resources/read`, { uri: item.uri });
            const contents = result.contents || [];
            output.textContent = contents.map(c => c.text || '').join('\n');
        } catch (e) {
            output.textContent = `Error: ${e.message}`;
        }
    }

    async loadPrompt(item) {
        const textarea = document.querySelector('#detail-form textarea');
        const output = document.getElementById('detail-output');
        let args = {};

        try {
            const raw = textarea?.value.trim();
            if (raw) args = JSON.parse(raw);
        } catch (e) {
            output.textContent = 'Invalid JSON';
            return;
        }

        try {
            const result = await this.ws.request(`${this.agentId}/prompts/get`, {
                name: item.name,
                arguments: args
            });
            const msg = result.messages?.[0]?.content;
            const text = msg?.text || '';
            output.textContent = text;

            // Also put in chat input
            const chatInput = document.getElementById('chat-input');
            if (chatInput) {
                chatInput.value = text;
                chatInput.focus();
            }
        } catch (e) {
            output.textContent = `Error: ${e.message}`;
        }
    }

    // LLM Config
    setupLLM() {
        const refreshBtn = document.getElementById('llm-refresh');
        const saveBtn = document.getElementById('llm-save');

        refreshBtn?.addEventListener('click', () => this.refreshModels());
        saveBtn?.addEventListener('click', () => this.saveLLMConfig());
    }

    async loadLLMConfig() {
        if (!this.ws.isConnected()) return;
        try {
            const config = await this.ws.request('llm_get_config');
            const endpoint = document.getElementById('llm-endpoint');
            const model = document.getElementById('llm-model');
            const status = document.getElementById('llm-status');

            if (endpoint && config.endpoint) endpoint.value = config.endpoint;
            if (model && config.model) model.value = config.model;
            if (status) status.textContent = config.model ? `Using ${config.model}` : 'No model selected';

            this.refreshModels();
        } catch (e) {
            console.warn('Failed to load LLM config:', e);
        }
    }

    async refreshModels() {
        if (!this.ws.isConnected()) return;
        const endpoint = document.getElementById('llm-endpoint')?.value.trim();
        if (!endpoint) return;

        try {
            const result = await this.ws.request('llm_list_models', { endpoint });
            const select = document.getElementById('llm-model');
            if (select) {
                const models = result.models || [];
                select.innerHTML = models.length
                    ? models.map(m => `<option value="${m}">${m}</option>`).join('')
                    : '<option value="">No models found</option>';
            }
        } catch (e) {
            console.warn('Failed to list models:', e);
        }
    }

    async saveLLMConfig() {
        if (!this.ws.isConnected()) return;
        const endpoint = document.getElementById('llm-endpoint')?.value.trim();
        const model = document.getElementById('llm-model')?.value;
        const status = document.getElementById('llm-status');

        try {
            const result = await this.ws.request('llm_set_config', {
                provider: 'ollama',
                endpoint,
                model
            });
            if (status) status.textContent = result.model ? `Using ${result.model}` : 'Saved';
        } catch (e) {
            if (status) status.textContent = 'Save failed';
        }
    }

    // Utility
    escapeHtml(str) {
        return String(str || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
}

// Start app
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new App());
} else {
    new App();
}
