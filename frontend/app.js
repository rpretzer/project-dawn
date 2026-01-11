/**
 * Project Dawn - Minimal UI
 * Clean, simple implementation matching the minimal UI design
 */

// Simple WebSocket connection
class WebSocketService {
    constructor() {
        this.ws = null;
        this.url = 'ws://localhost:8000';
        this.connected = false;
        this.listeners = {};
        this.pending = new Map();
        this.requestId = 0;
    }

    connect(url = this.url) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            return;
        }

        this.url = url;
        try {
            this.ws = new WebSocket(url);
            this.ws.onopen = () => {
                this.connected = true;
                this.emit('connected');
                this.updateStatus('Connected', 'connected');
            };
            this.ws.onclose = () => {
                this.connected = false;
                this.emit('disconnected');
                this.updateStatus('Disconnected', 'disconnected');
            };
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateStatus('Error', 'error');
            };
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data && data.id && this.pending.has(data.id)) {
                        const { resolve, reject } = this.pending.get(data.id);
                        this.pending.delete(data.id);
                        if (data.error) {
                            reject(data.error);
                        } else {
                            resolve(data.result ?? data);
                        }
                        return;
                    }
                    this.emit('message', data);
                } catch (e) {
                    console.error('Failed to parse message:', e);
                }
            };
        } catch (error) {
            console.error('Failed to connect:', error);
            this.updateStatus('Connection Failed', 'error');
        }
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.connected = false;
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    sendRequest(method, params = {}) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            return Promise.reject(new Error('WebSocket not connected'));
        }
        const id = `req-${Date.now()}-${this.requestId++}`;
        const payload = {
            jsonrpc: '2.0',
            id,
            method,
            params
        };
        return new Promise((resolve, reject) => {
            this.pending.set(id, { resolve, reject });
            this.ws.send(JSON.stringify(payload));
        });
    }

    on(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(callback);
    }

    emit(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(callback => callback(data));
        }
    }

    updateStatus(text, status) {
        const statusText = document.getElementById('status-text') || document.querySelector('.status-text');
        const statusIndicator = document.querySelector('.status-indicator');
        
        if (statusText) {
            statusText.textContent = text;
        }
        
        if (statusIndicator) {
            statusIndicator.style.backgroundColor = 
                status === 'connected' ? 'var(--status-connected)' : 'var(--status-connecting)';
        }
    }

    isConnected() {
        return this.connected && this.ws && this.ws.readyState === WebSocket.OPEN;
    }
}

// Main App
class App {
    constructor() {
        this.ws = new WebSocketService();
        this.tauri = window.__TAURI__ || null;
        this.volunteerEnabled = false;
        this.localAgent = null;
        this.peers = [];
        this.feedItems = [];
        this.pollInterval = null;
        this.chatAgentId = 'agent1';
        this.inventoryItems = { tool: [], resource: [], prompt: [] };
        this.selectedInventory = null;
        this.clientConfig = null;
        this.init();
    }

    init() {
        // Setup event listeners
        this.setupTabs();
        this.setupChatInput();
        this.setupThemeToggle();
        this.setupHeaderActions();
        this.setupVolunteerToggle();
        this.setupObserver();
        this.setupLlmPanel();
        this.setupAgentPicker();
        this.setupInventoryInteractions();
        this.setupKeyboardNav();
        
        // Listen for WebSocket events
        this.ws.on('connected', () => {
            console.log('Connected to server');
            this.loadLlmConfig();
            this.refreshModels();
            this.loadInventory();
            this.refreshAgents();
        });
        
        this.ws.on('message', (data) => {
            if (data && data.content) {
                this.addFeedEntry({
                    actor: data.actor || 'Mesh',
                    text: data.content,
                    timestamp: Date.now()
                });
            }
        });

        if (this.tauri && this.tauri.invoke) {
            this.refreshVolunteerStatus();
            this.loadObserverData();
            this.startPolling();
            this.setupResourceMonitor();
        } else {
            this.loadConfigAndConnect();
        }
    }

    async loadConfigAndConnect() {
        try {
            const response = await fetch('config.json', { cache: 'no-store' });
            if (response.ok) {
                const config = await response.json();
                this.clientConfig = config;
                if (config.wsUrl) {
                    this.ws.connect(config.wsUrl);
                    return;
                }
            }
        } catch (error) {
            console.warn('Failed to load config.json, falling back to default WS URL', error);
        }
        this.ws.connect();
    }

    setupTabs() {
        const tabButtons = document.querySelectorAll('.tab-button');
        const tabContents = {
            tools: document.getElementById('tools-tab'),
            resources: document.getElementById('resources-tab'),
            prompts: document.getElementById('prompts-tab')
        };

        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                this.activateTab(button.dataset.tab);
            });
        });
    }

    setupChatInput() {
        const chatInput = document.getElementById('chat-input');
        const sendButton = document.getElementById('send-button');

        const sendMessage = () => {
            const text = chatInput.value.trim();
            if (!text) return;

            this.addFeedEntry({
                actor: this.localAgent ? this.localAgent.name : 'Local Agent',
                text,
                timestamp: Date.now()
            });

            // Send via JSON-RPC chat method
            if (this.ws.isConnected()) {
                this.ws.sendRequest(`${this.chatAgentId}/chat/message`, {
                    message: text,
                    room_id: 'main'
                }).then((result) => {
                    if (result && result.content) {
                        this.addFeedEntry({
                            actor: result.agent_id || this.chatAgentId,
                            text: result.content,
                            timestamp: Date.now()
                        });
                    }
                }).catch((error) => {
                    this.addFeedEntry({
                        actor: 'System',
                        text: `Chat failed: ${error.message || 'Unknown error'}`,
                        timestamp: Date.now()
                    });
                });
            }

            // Clear input
            chatInput.value = '';
            chatInput.style.height = 'auto';
        };

        if (sendButton) {
            sendButton.addEventListener('click', sendMessage);
        }

        if (chatInput) {
            chatInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });

            // Auto-resize textarea
            chatInput.addEventListener('input', () => {
                chatInput.style.height = 'auto';
                chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
            });
        }
    }

    setupHeaderActions() {
        const refreshButton = document.getElementById('refresh-agents');
        const newAgentButton = document.getElementById('new-agent');
        const peopleButton = document.getElementById('people-button');
        const settingsButton = document.getElementById('settings-button');
        const attachButton = document.getElementById('attach-button');
        const modalClose = document.getElementById('modal-close');
        const modalOverlay = document.getElementById('modal-overlay');
        if (refreshButton) {
            refreshButton.addEventListener('click', () => {
                this.refreshAgents();
                this.loadInventory();
                this.loadObserverData();
                this.refreshModels();
            });
        }
        if (newAgentButton) {
            newAgentButton.addEventListener('click', () => this.showCreateAgentModal());
        }
        if (peopleButton) {
            peopleButton.addEventListener('click', () => this.showPeopleModal());
        }
        if (settingsButton) {
            settingsButton.addEventListener('click', () => this.showSettingsModal());
        }
        if (attachButton) {
            attachButton.addEventListener('click', () => this.handleAttach());
        }
        if (modalClose) {
            modalClose.addEventListener('click', () => this.closeModal());
        }
        if (modalOverlay) {
            modalOverlay.addEventListener('click', (event) => {
                if (event.target === modalOverlay) {
                    this.closeModal();
                }
            });
        }
    }

    setupObserver() {
        this.seedObserverData();
        this.renderLocalAgent();
        this.renderPeerGallery();
        this.renderStage();
        this.renderFeed();
    }

    setupAgentPicker() {
        this.agentSelect = document.getElementById('agent-select');
        this.agentRefreshButton = document.getElementById('agent-refresh');
        this.agentStatus = document.getElementById('agent-status');

        if (this.agentRefreshButton) {
            this.agentRefreshButton.addEventListener('click', () => this.refreshAgents());
        }
        if (this.agentSelect) {
            this.agentSelect.addEventListener('change', () => {
                this.chatAgentId = this.agentSelect.value || 'agent1';
                if (this.agentStatus) {
                    this.agentStatus.textContent = `Using ${this.chatAgentId}`;
                }
                this.loadInventory();
            });
        }
    }

    async refreshAgents() {
        if (!this.ws.isConnected()) {
            return;
        }
        try {
            const result = await this.ws.sendRequest('node/list_agents');
            const agents = result.agents || [];
            if (this.agentSelect) {
                this.agentSelect.innerHTML = '';
                agents.forEach((agent) => {
                    const option = document.createElement('option');
                    option.value = agent.agent_id;
                    option.textContent = agent.name || agent.agent_id;
                    if (agent.agent_id === this.chatAgentId) {
                        option.selected = true;
                    }
                    this.agentSelect.appendChild(option);
                });
                if (!agents.length) {
                    const option = document.createElement('option');
                    option.value = this.chatAgentId;
                    option.textContent = this.chatAgentId;
                    this.agentSelect.appendChild(option);
                }
            }
            if (this.agentStatus) {
                this.agentStatus.textContent = `Using ${this.chatAgentId}`;
            }
        } catch (error) {
            console.warn('Failed to load agents', error);
        }
    }

    async loadInventory() {
        if (!this.ws.isConnected()) {
            return;
        }
        try {
            const [toolsResult, resourcesResult, promptsResult] = await Promise.all([
                this.ws.sendRequest(`${this.chatAgentId}/tools/list`),
                this.ws.sendRequest(`${this.chatAgentId}/resources/list`),
                this.ws.sendRequest(`${this.chatAgentId}/prompts/list`)
            ]);
            this.renderInventoryList('tool-list', toolsResult.tools || []);
            this.renderInventoryList('resource-list', resourcesResult.resources || []);
            this.renderInventoryList('prompt-list', promptsResult.prompts || []);
            this.clearInventoryDetail();
        } catch (error) {
            console.warn('Failed to load inventory', error);
        }
    }

    renderInventoryList(containerId, items) {
        const container = document.getElementById(containerId);
        if (!container) {
            return;
        }
        if (!items.length) {
            container.innerHTML = '<div class="empty-state">No items available</div>';
            return;
        }
        const typeLabel = containerId.replace('-list', '');
        this.inventoryItems[typeLabel] = items.slice();
        container.innerHTML = items.map((item, index) => {
            const name = item.name || item.uri || item.id || 'Unnamed';
            const description = item.description || item.summary || '';
            const icon = this.inventoryIcon(typeLabel);
            return `
                <div class="inventory-item" tabindex="0" data-kind="${this.escapeHtml(typeLabel)}" data-index="${index}">
                    <span class="inventory-badge">${this.escapeHtml(typeLabel)}</span>
                    <div class="inventory-title"><span class="inventory-icon">${icon}</span>${this.escapeHtml(name)}</div>
                    <div class="inventory-desc">${this.escapeHtml(description)}</div>
                    <div class="inventory-meta">${this.inventoryMeta(item)}</div>
                </div>
            `;
        }).join('');
    }

    setupLlmPanel() {
        this.llmEndpointInput = document.getElementById('llm-endpoint');
        this.llmModelSelect = document.getElementById('llm-model');
        this.llmRefreshButton = document.getElementById('llm-refresh');
        this.llmSaveButton = document.getElementById('llm-save');
        this.llmStatus = document.getElementById('llm-status');

        if (this.llmRefreshButton) {
            this.llmRefreshButton.addEventListener('click', () => this.refreshModels());
        }
        if (this.llmSaveButton) {
            this.llmSaveButton.addEventListener('click', () => this.saveLlmConfig());
        }
    }

    async loadLlmConfig() {
        if (!this.ws.isConnected()) {
            return;
        }
        try {
            const config = await this.ws.sendRequest('llm_get_config');
            if (this.llmEndpointInput && config.endpoint) {
                this.llmEndpointInput.value = config.endpoint;
            }
            if (this.llmModelSelect && config.model) {
                this.llmModelSelect.value = config.model;
            }
            if (this.llmStatus) {
                this.llmStatus.textContent = config.model ? `Using ${config.model}` : 'No model selected';
            }
        } catch (error) {
            console.warn('Failed to load LLM config', error);
        }
    }

    async refreshModels() {
        if (!this.ws.isConnected()) {
            return;
        }
        const endpoint = this.llmEndpointInput ? this.llmEndpointInput.value.trim() : '';
        if (!endpoint) {
            return;
        }
        try {
            const result = await this.ws.sendRequest('llm_list_models', { endpoint });
            if (this.llmModelSelect) {
                this.llmModelSelect.innerHTML = '';
                const models = result.models || [];
                models.forEach((model) => {
                    const option = document.createElement('option');
                    option.value = model;
                    option.textContent = model;
                    this.llmModelSelect.appendChild(option);
                });
                if (models.length === 0) {
                    const option = document.createElement('option');
                    option.value = '';
                    option.textContent = 'No models found';
                    this.llmModelSelect.appendChild(option);
                }
            }
        } catch (error) {
            console.warn('Failed to list models', error);
        }
    }

    async saveLlmConfig() {
        if (!this.ws.isConnected()) {
            return;
        }
        const endpoint = this.llmEndpointInput ? this.llmEndpointInput.value.trim() : '';
        const model = this.llmModelSelect ? this.llmModelSelect.value : '';
        try {
            const result = await this.ws.sendRequest('llm_set_config', {
                provider: 'ollama',
                endpoint,
                model
            });
            if (this.llmStatus) {
                this.llmStatus.textContent = result.model ? `Using ${result.model}` : 'No model selected';
            }
        } catch (error) {
            console.warn('Failed to save LLM config', error);
        }
    }

    escapeHtml(value) {
        return String(value || '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#39;');
    }

    setupKeyboardNav() {
        document.addEventListener('keydown', (event) => {
            const tag = (event.target && event.target.tagName) || '';
            if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) {
                return;
            }

            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                const container = this.activeInventoryContainer();
                if (!container) {
                    return;
                }
                const items = Array.from(container.querySelectorAll('.inventory-item'));
                if (!items.length) {
                    return;
                }
                event.preventDefault();
                const currentIndex = items.findIndex((item) => item.classList.contains('inventory-selected'));
                let nextIndex = currentIndex;
                if (event.key === 'ArrowDown') {
                    nextIndex = currentIndex < 0 ? 0 : Math.min(currentIndex + 1, items.length - 1);
                } else {
                    nextIndex = currentIndex < 0 ? items.length - 1 : Math.max(currentIndex - 1, 0);
                }
                items.forEach((item) => item.classList.remove('inventory-selected'));
                const selected = items[nextIndex];
                selected.classList.add('inventory-selected');
                selected.focus({ preventScroll: true });
                selected.scrollIntoView({ block: 'nearest' });
                this.selectInventoryItem(selected, { updateSelection: false });
            }

            if (event.key === 'Enter') {
                const container = this.activeInventoryContainer();
                if (!container) {
                    return;
                }
                const selected = container.querySelector('.inventory-item.inventory-selected');
                if (!selected) {
                    return;
                }
                const actionButton = document.querySelector('.inventory-detail-actions .inventory-detail-button.primary');
                if (actionButton) {
                    actionButton.click();
                } else {
                    const title = selected.querySelector('.inventory-title');
                    const chatInput = document.getElementById('chat-input');
                    if (title && chatInput) {
                        const text = title.textContent.trim();
                        chatInput.value = text;
                        chatInput.focus();
                    }
                }
            }
        });
    }

    activeInventoryContainer() {
        const activeTab = document.querySelector('.tab-button.active');
        if (!activeTab) {
            return null;
        }
        const tabName = activeTab.dataset.tab;
        const id = `${tabName}-list`;
        return document.getElementById(id);
    }

    inventoryIcon(typeLabel) {
        if (typeLabel === 'tool') return '🗡️';
        if (typeLabel === 'resource') return '🧰';
        if (typeLabel === 'prompt') return '📜';
        return '✨';
    }

    inventoryMeta(item) {
        const meta = [];
        if (item.inputSchema && item.inputSchema.required) {
            meta.push(`${item.inputSchema.required.length} req`);
        }
        if (item.arguments && Array.isArray(item.arguments)) {
            const required = item.arguments.filter((arg) => arg.required).length;
            if (required) {
                meta.push(`${required} req`);
            }
        }
        if (item.uri) {
            meta.push('URI');
        }
        if (item.name) {
            meta.push('Skill');
        }
        return meta.join(' • ');
    }

    async loadObserverData() {
        if (!this.tauri || !this.tauri.invoke) {
            return;
        }

        try {
            const [manifestRaw, peersRaw, feedLines] = await Promise.all([
                this.tauri.invoke('get_manifest'),
                this.tauri.invoke('get_peers'),
                this.tauri.invoke('get_feed', { limit: 80 })
            ]);

            if (manifestRaw) {
                const manifest = JSON.parse(manifestRaw);
                this.localAgent = {
                    name: manifest.displayName || 'Local Agent',
                    peerId: this.formatPeerId(manifest.peerId),
                    logit: this.formatLogit(manifest.logitFingerprint),
                    status: 'Online'
                };
            }

            if (peersRaw) {
                const peersPayload = JSON.parse(peersRaw);
                const peers = peersPayload.peers || [];
                this.peers = peers.map((peer) => {
                    const score = Number(peer.reputationScore || 0);
                    const { x, y } = this.positionFromId(peer.peerId || peer.peer_id || '');
                    return {
                        id: peer.peerId,
                        name: this.formatPeerId(peer.peerId),
                        trust: score,
                        status: score >= 0.7 ? 'trusted' : 'unknown',
                        x,
                        y
                    };
                });
            }

            if (Array.isArray(feedLines) && feedLines.length) {
                this.feedItems = feedLines
                    .map((line) => {
                        try {
                            return JSON.parse(line);
                        } catch (error) {
                            return null;
                        }
                    })
                    .filter(Boolean)
                    .map((event) => {
                        return {
                            actor: event.peerId ? this.formatPeerId(event.peerId) : (event.actor || 'Mesh'),
                            text: this.describeFeedEvent(event),
                            timestamp: (event.timestamp || Date.now() * 0.001) * 1000,
                            type: event.type
                        };
                    });
            }

            this.renderLocalAgent();
            this.renderPeerGallery();
            this.renderStage();
            this.renderFeed();
        } catch (error) {
            console.warn('Failed to load observer data:', error);
        }
    }

    startPolling() {
        if (this.pollInterval) {
            return;
        }
        this.pollInterval = setInterval(() => {
            this.loadObserverData();
        }, 2500);
    }

    async setupResourceMonitor() {
        if (!this.tauri || !this.tauri.invoke) {
            return;
        }

        try {
            const stateRaw = await this.tauri.invoke('get_resource_state');
            if (stateRaw) {
                this.updateResourceState(JSON.parse(stateRaw));
            }
        } catch (error) {
            console.warn('Failed to load resource state:', error);
        }

        const tauriEvent = this.tauri.event;
        if (tauriEvent && tauriEvent.listen) {
            tauriEvent.listen('resource_state', (event) => {
                if (event && event.payload) {
                    this.updateResourceState(event.payload);
                }
            });
        }
    }

    seedObserverData() {
        this.localAgent = {
            name: 'Radiator-01',
            peerId: '0xLOCAL',
            logit: 'LF-004',
            status: 'Online'
        };

        this.peers = [
            { id: '0x4f2', name: 'Peer 0x4f2', trust: 0.98, status: 'trusted', x: 22, y: 38 },
            { id: '0x91a', name: 'Peer 0x91a', trust: 0.76, status: 'trusted', x: 68, y: 28 },
            { id: '0x7bd', name: 'Peer 0x7bd', trust: 0.54, status: 'unknown', x: 35, y: 70 },
            { id: '0x2c0', name: 'Peer 0x2c0', trust: 0.31, status: 'unknown', x: 75, y: 62 }
        ];

        this.feedItems = [
            {
                actor: 'Local Agent',
                text: 'Presence broadcast acknowledged. Mesh pulse stable.',
                timestamp: Date.now() - 30000
            },
            {
                actor: 'Peer 0x4f2',
                text: 'Handshake unit received. Trust verification: 98%.',
                timestamp: Date.now() - 18000
            },
            {
                actor: 'Local Agent',
                text: 'Negotiating a work unit with Peer 0x91a.',
                timestamp: Date.now() - 7000
            }
        ];
    }

    formatPeerId(peerId) {
        if (!peerId) {
            return '0x----';
        }
        return `0x${peerId.slice(0, 6)}`;
    }

    formatLogit(logit) {
        if (!logit) {
            return 'LF-000';
        }
        return `LF-${logit.slice(0, 3).toUpperCase()}`;
    }

    positionFromId(peerId) {
        let hash = 0;
        for (let i = 0; i < peerId.length; i++) {
            hash = (hash * 31 + peerId.charCodeAt(i)) % 100000;
        }
        const x = 20 + (hash % 60);
        const y = 20 + (Math.floor(hash / 60) % 60);
        return { x, y };
    }

    describeFeedEvent(event) {
        if (event.type === 'presence') {
            return `Presence: ${event.status || 'unknown'}`;
        }
        if (event.type === 'resource') {
            return `Resources: ${event.status || 'unknown'}`;
        }
        if (event.text) {
            return event.text;
        }
        return 'Mesh activity recorded.';
    }

    updateResourceState(state) {
        const pill = document.getElementById('resource-pill');
        const value = document.getElementById('resource-value');
        if (!pill || !value || !state) {
            return;
        }
        const throttled = Boolean(state.throttled);
        pill.classList.toggle('throttled', throttled);
        value.textContent = throttled ? 'Throttled' : 'Stable';
        if (this.localAgent) {
            this.localAgent.throttled = throttled;
            this.renderStage();
        }
    }

    renderLocalAgent() {
        const nameEl = document.getElementById('local-agent-name');
        const peerEl = document.getElementById('local-agent-peer');
        const logitEl = document.getElementById('local-agent-logit');
        const statusEl = document.getElementById('local-agent-status');

        if (nameEl) nameEl.textContent = this.localAgent.name;
        if (peerEl) peerEl.textContent = this.localAgent.peerId;
        if (logitEl) logitEl.textContent = this.localAgent.logit;
        if (statusEl) statusEl.textContent = this.localAgent.status;
    }

    renderPeerGallery() {
        const container = document.getElementById('peer-gallery');
        if (!container) return;

        if (!this.peers.length) {
            container.innerHTML = '<div class="empty-state">No peers discovered</div>';
            return;
        }

        container.innerHTML = this.peers
            .map((peer) => `
                <div class="peer-card">
                    <strong>${peer.name}</strong>
                    <span>Trust ${Math.round(peer.trust * 100)}%</span>
                </div>
            `)
            .join('');
    }

    renderStage() {
        const stage = document.getElementById('stage-canvas');
        if (!stage) return;

        stage.innerHTML = '';

        const local = document.createElement('div');
        local.className = `stage-node local${this.localAgent.throttled ? ' throttled' : ''}`;
        local.style.setProperty('--x', 50);
        local.style.setProperty('--y', 50);
        local.textContent = this.localAgent.name;
        stage.appendChild(local);

        this.peers.forEach(peer => {
            const node = document.createElement('div');
            node.className = `stage-node ${peer.status}`;
            node.style.setProperty('--x', peer.x);
            node.style.setProperty('--y', peer.y);
            node.textContent = peer.name;
            stage.appendChild(node);
        });
    }

    renderFeed() {
        const feed = document.getElementById('mesh-feed');
        if (!feed) return;

        if (!this.feedItems.length) {
            feed.innerHTML = '<div class="feed-empty">No activity yet</div>';
            return;
        }

        feed.innerHTML = '';
        this.feedItems.forEach(item => this.appendFeedItem(feed, item));
    }

    addFeedEntry(entry) {
        const feed = document.getElementById('mesh-feed');
        if (!feed) return;

        const emptyState = feed.querySelector('.feed-empty');
        if (emptyState) {
            emptyState.remove();
        }

        this.appendFeedItem(feed, entry);
        feed.scrollTop = feed.scrollHeight;
    }

    appendFeedItem(feed, entry) {
        const item = document.createElement('div');
        item.className = `feed-item${entry.type === 'resource' ? ' resource' : ''}`;

        const actor = document.createElement('strong');
        actor.textContent = entry.actor || 'Mesh';

        const text = document.createElement('span');
        text.textContent = entry.text || '';

        const time = document.createElement('span');
        const ts = entry.timestamp ? new Date(entry.timestamp) : new Date();
        time.textContent = ts.toLocaleTimeString();
        time.style.fontSize = '11px';
        time.style.color = 'var(--text-muted)';

        item.appendChild(actor);
        item.appendChild(text);
        item.appendChild(time);
        feed.appendChild(item);
    }

    setupThemeToggle() {
        const themeToggle = document.getElementById('theme-toggle');
        if (!themeToggle) return;

        // Load saved theme
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.body.className = `theme-${savedTheme}`;

        themeToggle.addEventListener('click', () => {
            const currentTheme = document.body.classList.contains('theme-dark') ? 'dark' : 'light';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.body.className = `theme-${newTheme}`;
            localStorage.setItem('theme', newTheme);
        });
    }

    setupVolunteerToggle() {
        const toggleButton = document.getElementById('volunteer-toggle');
        const statusLabel = document.getElementById('volunteer-status');

        if (!toggleButton || !statusLabel) return;

        if (!this.tauri || !this.tauri.invoke) {
            toggleButton.disabled = true;
            statusLabel.textContent = 'Unavailable';
            return;
        }

        toggleButton.addEventListener('click', async () => {
            toggleButton.disabled = true;
            try {
                if (this.volunteerEnabled) {
                    await this.tauri.invoke('stop_sidecar');
                    this.setVolunteerState(false);
                } else {
                    await this.tauri.invoke('start_sidecar');
                    this.setVolunteerState(true);
                }
            } catch (error) {
                console.error('Volunteer toggle failed:', error);
                statusLabel.textContent = 'Error';
            } finally {
                toggleButton.disabled = false;
            }
        });
    }

    async refreshVolunteerStatus() {
        try {
            const running = await this.tauri.invoke('sidecar_status');
            this.setVolunteerState(Boolean(running));
        } catch (error) {
            console.error('Failed to get sidecar status:', error);
            this.setVolunteerState(false);
        }
    }

    setVolunteerState(enabled) {
        const toggleButton = document.getElementById('volunteer-toggle');
        const statusLabel = document.getElementById('volunteer-status');
        if (!toggleButton || !statusLabel) return;

        this.volunteerEnabled = enabled;
        statusLabel.textContent = enabled ? 'On' : 'Off';
        toggleButton.classList.toggle('active', enabled);

        if (enabled) {
            if (!this.ws.isConnected()) {
                this.ws.connect();
            }
        } else {
            this.ws.disconnect();
        }
    }

    activateTab(tabName) {
        const tabButtons = document.querySelectorAll('.tab-button');
        const tabContents = {
            tools: document.getElementById('tools-tab'),
            resources: document.getElementById('resources-tab'),
            prompts: document.getElementById('prompts-tab')
        };

        tabButtons.forEach(btn => btn.classList.remove('active'));
        Object.values(tabContents).forEach(content => {
            if (content) {
                content.classList.remove('active');
                content.style.display = 'none';
            }
        });

        const targetButton = Array.from(tabButtons).find(btn => btn.dataset.tab === tabName);
        if (targetButton) {
            targetButton.classList.add('active');
        }
        if (tabContents[tabName]) {
            tabContents[tabName].classList.add('active');
            tabContents[tabName].style.display = 'block';
        }
        this.clearInventoryDetail();
    }

    setupInventoryInteractions() {
        const listIds = ['tool-list', 'resource-list', 'prompt-list'];
        listIds.forEach((id) => {
            const container = document.getElementById(id);
            if (!container) {
                return;
            }
            container.addEventListener('click', (event) => {
                const target = event.target.closest('.inventory-item');
                if (!target) {
                    return;
                }
                this.selectInventoryItem(target, { updateSelection: true });
            });
        });
    }

    selectInventoryItem(itemEl, { updateSelection = true } = {}) {
        const kind = itemEl.dataset.kind;
        const index = Number(itemEl.dataset.index || -1);
        if (!kind || Number.isNaN(index) || index < 0) {
            return;
        }

        if (updateSelection) {
            const container = itemEl.parentElement;
            if (container) {
                Array.from(container.querySelectorAll('.inventory-item')).forEach((item) => {
                    item.classList.remove('inventory-selected');
                });
            }
            itemEl.classList.add('inventory-selected');
        }

        const item = this.inventoryItemData(kind, index);
        if (!item) {
            return;
        }
        this.selectedInventory = { kind, index, item };
        this.renderInventoryDetail(kind, item);
    }

    inventoryItemData(kind, index) {
        const list = this.inventoryItems[kind];
        if (!list || index < 0 || index >= list.length) {
            return null;
        }
        return list[index];
    }

    clearInventoryDetail() {
        this.selectedInventory = null;
        const title = document.getElementById('inventory-detail-title');
        const desc = document.getElementById('inventory-detail-desc');
        const meta = document.getElementById('inventory-detail-meta');
        const form = document.getElementById('inventory-detail-form');
        const actions = document.getElementById('inventory-detail-actions');
        const output = document.getElementById('inventory-detail-output');
        if (title) title.textContent = 'Select an item';
        if (desc) desc.textContent = 'Choose a tool, resource, or prompt to inspect.';
        if (meta) meta.textContent = '';
        if (form) form.innerHTML = '';
        if (actions) actions.innerHTML = '';
        if (output) output.textContent = '';
    }

    renderInventoryDetail(kind, item) {
        const title = document.getElementById('inventory-detail-title');
        const desc = document.getElementById('inventory-detail-desc');
        const meta = document.getElementById('inventory-detail-meta');
        const form = document.getElementById('inventory-detail-form');
        const actions = document.getElementById('inventory-detail-actions');
        const output = document.getElementById('inventory-detail-output');
        if (!title || !desc || !meta || !form || !actions || !output) {
            return;
        }

        const label = item.name || item.uri || item.id || 'Unnamed';
        title.textContent = label;
        desc.textContent = item.description || item.summary || 'No description provided.';
        meta.textContent = this.inventoryMeta(item);
        form.innerHTML = '';
        actions.innerHTML = '';
        output.textContent = '';

        if (kind === 'tool') {
            const textarea = document.createElement('textarea');
            textarea.placeholder = 'Arguments (JSON)';
            form.appendChild(textarea);

            const button = document.createElement('button');
            button.className = 'inventory-detail-button primary';
            button.textContent = 'Run Tool';
            button.addEventListener('click', async () => {
                if (!this.ws.isConnected()) {
                    output.textContent = 'WebSocket not connected.';
                    return;
                }
                let argumentsPayload = {};
                const raw = textarea.value.trim();
                if (raw) {
                    try {
                        argumentsPayload = JSON.parse(raw);
                    } catch (error) {
                        output.textContent = 'Arguments must be valid JSON.';
                        return;
                    }
                }
                try {
                    const result = await this.ws.sendRequest(`${this.chatAgentId}/tools/call`, {
                        name: item.name,
                        arguments: argumentsPayload
                    });
                    output.textContent = JSON.stringify(result, null, 2);
                } catch (error) {
                    output.textContent = `Tool failed: ${error.message || 'Unknown error'}`;
                }
            });
            actions.appendChild(button);
        } else if (kind === 'resource') {
            const button = document.createElement('button');
            button.className = 'inventory-detail-button primary';
            button.textContent = 'Read Resource';
            button.addEventListener('click', async () => {
                if (!this.ws.isConnected()) {
                    output.textContent = 'WebSocket not connected.';
                    return;
                }
                try {
                    const result = await this.ws.sendRequest(`${this.chatAgentId}/resources/read`, {
                        uri: item.uri
                    });
                    const contents = result.contents || [];
                    output.textContent = contents.map((entry) => entry.text || '').join('\n');
                } catch (error) {
                    output.textContent = `Read failed: ${error.message || 'Unknown error'}`;
                }
            });
            actions.appendChild(button);
        } else if (kind === 'prompt') {
            const textarea = document.createElement('textarea');
            textarea.placeholder = 'Arguments (JSON)';
            form.appendChild(textarea);

            const button = document.createElement('button');
            button.className = 'inventory-detail-button primary';
            button.textContent = 'Load Prompt';
            button.addEventListener('click', async () => {
                if (!this.ws.isConnected()) {
                    output.textContent = 'WebSocket not connected.';
                    return;
                }
                let argumentsPayload = {};
                const raw = textarea.value.trim();
                if (raw) {
                    try {
                        argumentsPayload = JSON.parse(raw);
                    } catch (error) {
                        output.textContent = 'Arguments must be valid JSON.';
                        return;
                    }
                }
                try {
                    const result = await this.ws.sendRequest(`${this.chatAgentId}/prompts/get`, {
                        name: item.name,
                        arguments: argumentsPayload
                    });
                    const message = result.messages && result.messages[0] && result.messages[0].content;
                    const text = message && message.text ? message.text : '';
                    output.textContent = text;
                    const chatInput = document.getElementById('chat-input');
                    if (chatInput) {
                        chatInput.value = text;
                        chatInput.focus();
                    }
                } catch (error) {
                    output.textContent = `Prompt failed: ${error.message || 'Unknown error'}`;
                }
            });
            actions.appendChild(button);
        }
        }
    }

    openModal(title, bodyNodes = [], footerNodes = []) {
        const overlay = document.getElementById('modal-overlay');
        const titleEl = document.getElementById('modal-title');
        const bodyEl = document.getElementById('modal-body');
        const footerEl = document.getElementById('modal-footer');
        if (!overlay || !titleEl || !bodyEl || !footerEl) {
            return;
        }
        titleEl.textContent = title;
        bodyEl.innerHTML = '';
        footerEl.innerHTML = '';
        bodyNodes.forEach((node) => bodyEl.appendChild(node));
        footerNodes.forEach((node) => footerEl.appendChild(node));
        overlay.classList.remove('hidden');
    }

    closeModal() {
        const overlay = document.getElementById('modal-overlay');
        if (overlay) {
            overlay.classList.add('hidden');
        }
    }

    modalButton(label, { primary = false, onClick } = {}) {
        const button = document.createElement('button');
        button.className = `inventory-detail-button${primary ? ' primary' : ''}`;
        button.textContent = label;
        if (onClick) {
            button.addEventListener('click', onClick);
        }
        return button;
    }

    showCreateAgentModal() {
        if (!this.ws.isConnected()) {
            this.addFeedEntry({
                actor: 'System',
                text: 'Connect to the node before creating agents.',
                timestamp: Date.now()
            });
            return;
        }

        const nameInput = document.createElement('input');
        nameInput.placeholder = 'Agent display name';

        const idInput = document.createElement('input');
        idInput.placeholder = 'Agent ID (letters, numbers, - or _)';

        const status = document.createElement('div');
        status.className = 'llm-status';
        status.textContent = '';

        const body = [
            this.modalLabel('Display Name'),
            nameInput,
            this.modalLabel('Agent ID'),
            idInput,
            status
        ];

        const createButton = this.modalButton('Create', {
            primary: true,
            onClick: async () => {
                const name = nameInput.value.trim() || 'UnnamedAgent';
                const agentId = idInput.value.trim() || this.slugify(name);
                if (!agentId) {
                    status.textContent = 'Agent ID is required.';
                    return;
                }
                try {
                    const result = await this.ws.sendRequest('node/create_agent', {
                        agent_id: agentId,
                        name
                    });
                    status.textContent = result.status ? `Created ${result.agent_id}` : 'Created';
                    await this.refreshAgents();
                    this.closeModal();
                } catch (error) {
                    status.textContent = error.message || 'Failed to create agent.';
                }
            }
        });

        const cancelButton = this.modalButton('Cancel', { onClick: () => this.closeModal() });
        this.openModal('Create Agent', body, [cancelButton, createButton]);
    }

    showPeopleModal() {
        if (!this.ws.isConnected()) {
            this.addFeedEntry({
                actor: 'System',
                text: 'Connect to the node to see peers and agents.',
                timestamp: Date.now()
            });
            return;
        }

        const agentsSection = document.createElement('div');
        const peersSection = document.createElement('div');
        const status = document.createElement('div');
        status.className = 'llm-status';
        status.textContent = 'Loading...';

        const body = [
            this.modalLabel('Agents'),
            agentsSection,
            this.modalLabel('Peers'),
            peersSection,
            status
        ];

        const refreshButton = this.modalButton('Refresh', {
            primary: true,
            onClick: () => this.populatePeopleModal(agentsSection, peersSection, status)
        });

        const closeButton = this.modalButton('Close', { onClick: () => this.closeModal() });
        this.openModal('People', body, [closeButton, refreshButton]);
        this.populatePeopleModal(agentsSection, peersSection, status);
    }

    async populatePeopleModal(agentsSection, peersSection, status) {
        try {
            const [agentsResult, peersResult] = await Promise.all([
                this.ws.sendRequest('node/list_agents'),
                this.ws.sendRequest('node/list_peers')
            ]);
            const agents = agentsResult.agents || [];
            const peers = peersResult.peers || [];
            agentsSection.innerHTML = this.renderModalList(
                agents.map((agent) => ({
                    label: agent.name || agent.agent_id,
                    meta: agent.agent_id
                }))
            );
            peersSection.innerHTML = this.renderModalList(
                peers.map((peer) => ({
                    label: peer.peerId || peer.peer_id || 'Peer',
                    meta: peer.address || ''
                }))
            );
            status.textContent = '';
        } catch (error) {
            status.textContent = error.message || 'Failed to load people.';
        }
    }

    showSettingsModal() {
        if (!this.ws.isConnected()) {
            this.addFeedEntry({
                actor: 'System',
                text: 'Connect to the node to view settings.',
                timestamp: Date.now()
            });
            return;
        }

        const infoSection = document.createElement('div');
        const privacySection = document.createElement('div');
        const status = document.createElement('div');
        status.className = 'llm-status';
        status.textContent = 'Loading...';

        const body = [
            this.modalLabel('Runtime'),
            infoSection,
            this.modalLabel('Privacy'),
            privacySection,
            status
        ];

        const closeButton = this.modalButton('Close', { onClick: () => this.closeModal() });
        this.openModal('Settings', body, [closeButton]);
        this.populateSettingsModal(infoSection, privacySection, status);
    }

    async populateSettingsModal(infoSection, privacySection, status) {
        try {
            const [infoResult, llmConfig] = await Promise.all([
                this.ws.sendRequest('node/get_info'),
                this.ws.sendRequest('llm_get_config')
            ]);
            const info = infoResult || {};
            const rows = [
                { label: 'Node ID', value: info.node_id || 'unknown' },
                { label: 'Address', value: info.address || 'unknown' },
                { label: 'Peers', value: String(info.peer_count || 0) },
                { label: 'HTTP', value: this.clientConfig?.httpUrl || 'n/a' },
                { label: 'WebSocket', value: this.clientConfig?.wsUrl || 'n/a' },
                { label: 'LLM Model', value: llmConfig.model || 'none' }
            ];
            infoSection.innerHTML = this.renderModalList(rows.map(row => ({
                label: row.label,
                meta: row.value
            })));

            if (info.privacy) {
                privacySection.innerHTML = '';
                const onionToggle = this.privacyToggle('Onion routing', info.privacy.onion_routing);
                const paddingToggle = this.privacyToggle('Message padding', info.privacy.message_padding);
                const timingToggle = this.privacyToggle('Timing obfuscation', info.privacy.timing_obfuscation);
                privacySection.appendChild(onionToggle.wrapper);
                privacySection.appendChild(paddingToggle.wrapper);
                privacySection.appendChild(timingToggle.wrapper);
                const saveButton = this.modalButton('Save privacy', {
                    primary: true,
                    onClick: async () => {
                        const config = {
                            onion_routing: onionToggle.input.checked,
                            message_padding: paddingToggle.input.checked,
                            timing_obfuscation: timingToggle.input.checked
                        };
                        try {
                            await this.ws.sendRequest('node/configure_privacy', { config });
                            status.textContent = 'Privacy settings updated.';
                        } catch (error) {
                            status.textContent = error.message || 'Failed to update privacy.';
                        }
                    }
                });
                privacySection.appendChild(saveButton);
            } else {
                privacySection.textContent = 'Privacy layer not enabled.';
            }
            status.textContent = '';
        } catch (error) {
            status.textContent = error.message || 'Failed to load settings.';
        }
    }

    handleAttach() {
        this.activateTab('resources');
        const container = document.getElementById('resource-list');
        if (!container) {
            return;
        }
        const firstItem = container.querySelector('.inventory-item');
        if (firstItem) {
            this.selectInventoryItem(firstItem, { updateSelection: true });
            firstItem.scrollIntoView({ block: 'nearest' });
        } else {
            this.addFeedEntry({
                actor: 'System',
                text: 'No resources available to attach.',
                timestamp: Date.now()
            });
        }
    }

    modalLabel(text) {
        const label = document.createElement('label');
        label.textContent = text;
        return label;
    }

    renderModalList(items) {
        if (!items.length) {
            return '<div class="empty-state">None found</div>';
        }
        return `
            <div class="modal-list">
                ${items.map((item) => `
                    <div class="modal-list-item">
                        <span>${this.escapeHtml(item.label)}</span>
                        <span class="modal-pill">${this.escapeHtml(item.meta || '')}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    privacyToggle(labelText, checked) {
        const wrapper = document.createElement('div');
        wrapper.className = 'modal-list-item';
        const label = document.createElement('span');
        label.textContent = labelText;
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.checked = Boolean(checked);
        wrapper.appendChild(label);
        wrapper.appendChild(input);
        return { wrapper, input };
    }

    slugify(value) {
        return value
            .toLowerCase()
            .replace(/[^a-z0-9-_]+/g, '-')
            .replace(/^-+|-+$/g, '')
            .slice(0, 32);
    }
// Initialize app when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        new App();
    });
} else {
    new App();
}
