/**
 * Project Dawn - Observability Dashboard
 * Renders metrics, alerts, and network topology
 */

export class Dashboard {
    constructor(wsClient) {
        this.ws = wsClient;
        this.container = null;
        this.refreshInterval = null;
        this.topologyData = { nodes: [], edges: [] };
    }

    mount(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) return;

        this.renderLayout();
        this.startRefreshing();
    }

    unmount() {
        this.stopRefreshing();
        if (this.container) {
            this.container.innerHTML = '';
        }
    }

    renderLayout() {
        this.container.innerHTML = `
            <div class="dashboard-grid">
                <!-- Top Row: Metrics Cards -->
                <div class="dashboard-section metrics-section">
                    <h3>System Metrics</h3>
                    <div class="metrics-grid" id="metrics-grid">
                        <div class="metric-card loading">Loading...</div>
                        <div class="metric-card loading">Loading...</div>
                        <div class="metric-card loading">Loading...</div>
                        <div class="metric-card loading">Loading...</div>
                    </div>
                </div>

                <!-- Middle Row: Alerts & Health -->
                <div class="dashboard-row">
                    <div class="dashboard-section alerts-section">
                        <h3>Active Alerts</h3>
                        <div class="alerts-list" id="alerts-list">
                            <div class="empty-state">No active alerts</div>
                        </div>
                    </div>
                    <div class="dashboard-section health-section">
                        <h3>Component Health</h3>
                        <div class="health-list" id="health-list">
                            <div class="empty-state">Loading health data...</div>
                        </div>
                    </div>
                </div>

                <!-- Bottom Row: Topology -->
                <div class="dashboard-section topology-section">
                    <div class="section-header">
                        <h3>Network Topology</h3>
                        <div class="topology-controls">
                            <span class="topology-stats" id="topology-stats">0 nodes, 0 connections</span>
                        </div>
                    </div>
                    <div class="topology-graph" id="topology-graph">
                        <!-- SVG Graph will be rendered here -->
                    </div>
                </div>
            </div>
        `;
    }

    startRefreshing() {
        this.refresh();
        this.refreshInterval = setInterval(() => this.refresh(), 5000); // 5s interval
    }

    stopRefreshing() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    async refresh() {
        if (!this.ws.isConnected()) return;

        try {
            await Promise.all([
                this.updateMetrics(),
                this.updateHealth(),
                this.updateTopology()
            ]);
        } catch (e) {
            console.warn('Dashboard refresh failed:', e);
        }
    }

    async updateMetrics() {
        // Fetch raw metrics from text format if endpoint available, 
        // but for now we'll use the network_info tool which aggregates some stats
        // In a real app, we'd parse the Prometheus text format
        try {
            // Note: We need a way to get raw metrics. 
            // For now, let's use the coordination agent's network_stats resource if available
            // Or fallback to node_info
            
            // Try getting network stats from coordination agent
            const response = await this.ws.request('coordinator/resources/read', { uri: 'network://stats' });
            
            if (response && response.contents && response.contents.length > 0) {
                const stats = JSON.parse(response.contents[0].text);
                this.renderMetricsFromStats(stats);
            }
        } catch (e) {
            // Fallback: use basic node info
            try {
                const info = await this.ws.request('node/get_info');
                this.renderBasicMetrics(info.result);
            } catch (err) {
                console.warn('Failed to fetch metrics', err);
            }
        }
    }

    renderMetricsFromStats(stats) {
        const container = document.getElementById('metrics-grid');
        if (!container) return;

        // Extract key metrics
        const metrics = [
            { label: 'Total Agents', value: stats.network.total_agents, color: 'blue' },
            { label: 'Connected Nodes', value: stats.network.connected_nodes, color: 'green' },
            { label: 'Success Rate', value: `${(stats.connections.success_rate * 100).toFixed(1)}%`, color: 'teal' },
            { label: 'Avg Health', value: stats.health.average_health_score.toFixed(2), color: 'purple' }
        ];

        container.innerHTML = metrics.map(m => `
            <div class="metric-card">
                <div class="metric-value" style="color: var(--${m.color})">${m.value}</div>
                <div class="metric-label">${m.label}</div>
            </div>
        `).join('');
        
        // Also update alert list if there are unhealthy nodes
        if (stats.health.unhealthy_nodes > 0) {
            this.renderAlerts([{
                name: 'Unhealthy Nodes Detected',
                severity: 'warning',
                value: `${stats.health.unhealthy_nodes} nodes reporting low health`
            }]);
        } else {
            this.renderAlerts([]);
        }
    }

    renderBasicMetrics(info) {
        const container = document.getElementById('metrics-grid');
        if (!container) return;

        const metrics = [
            { label: 'Local Agents', value: info.agents.length, color: 'blue' },
            { label: 'Connected Peers', value: info.peer_count, color: 'green' },
            // Placeholder for others
            { label: 'Uptime', value: 'Active', color: 'teal' },
            { label: 'Status', value: 'Online', color: 'purple' }
        ];

        container.innerHTML = metrics.map(m => `
            <div class="metric-card">
                <div class="metric-value" style="color: var(--${m.color})">${m.value}</div>
                <div class="metric-label">${m.label}</div>
            </div>
        `).join('');
    }

    async updateHealth() {
        try {
            // We need a health endpoint exposed via JSON-RPC
            // Currently server_api exposes it via HTTP, but maybe not WS?
            // Let's assume we can add a simple node/health method or use existing tools
            // For now, we'll mock it based on peer connection status or implement a new method
            
            // Just use a placeholder implementation that checks connection
            const healthList = document.getElementById('health-list');
            if (!healthList) return;
            
            const isConnected = this.ws.isConnected();
            const healthItems = [
                { name: 'WebSocket Connection', status: isConnected ? 'healthy' : 'unhealthy', message: isConnected ? 'Connected' : 'Disconnected' },
                { name: 'Agent Runtime', status: 'healthy', message: 'Active' }, // Assumed if we can fetch
            ];
            
            healthList.innerHTML = healthItems.map(item => `
                <div class="health-item ${item.status}">
                    <div class="health-indicator"></div>
                    <div class="health-info">
                        <div class="health-name">${item.name}</div>
                        <div class="health-msg">${item.message}</div>
                    </div>
                </div>
            `).join('');
            
        } catch (e) {
            console.warn('Failed to update health', e);
        }
    }

    renderAlerts(alerts) {
        const container = document.getElementById('alerts-list');
        if (!container) return;

        if (!alerts || alerts.length === 0) {
            container.innerHTML = '<div class="empty-state">No active alerts</div>';
            return;
        }

        container.innerHTML = alerts.map(alert => `
            <div class="alert-card ${alert.severity}">
                <div class="alert-icon">⚠️</div>
                <div class="alert-content">
                    <div class="alert-title">${alert.name}</div>
                    <div class="alert-value">${alert.value}</div>
                </div>
            </div>
        `).join('');
    }

    async updateTopology() {
        try {
            const response = await this.ws.request('coordinator/resources/read', { uri: 'network://topology' });
            if (response && response.contents && response.contents.length > 0) {
                const topology = JSON.parse(response.contents[0].text);
                this.renderTopologyGraph(topology);
                
                // Update stats
                const statsEl = document.getElementById('topology-stats');
                if (statsEl) {
                    statsEl.textContent = `${topology.total_nodes} nodes, ${topology.connected_edges} connections`;
                }
            }
        } catch (e) {
            // Fallback or silence
        }
    }

    renderTopologyGraph(data) {
        const container = document.getElementById('topology-graph');
        if (!container) return;

        // Simple SVG rendering
        // Calculate layout (star layout for simplicity: local node in center)
        const width = container.clientWidth || 600;
        const height = container.clientHeight || 300;
        const centerX = width / 2;
        const centerY = height / 2;
        const radius = Math.min(width, height) / 3;

        const nodes = data.nodes || [];
        const edges = data.edges || [];

        // Position nodes
        const positionedNodes = nodes.map((node, i) => {
            if (node.type === 'local') {
                return { ...node, x: centerX, y: centerY };
            }
            // Distribute others in a circle
            const angle = ((i - 1) / (nodes.length - 1)) * 2 * Math.PI;
            return {
                ...node,
                x: centerX + radius * Math.cos(angle),
                y: centerY + radius * Math.sin(angle)
            };
        });

        // Create SVG
        const svg = `
            <svg width="100%" height="100%" viewBox="0 0 ${width} ${height}">
                <!-- Edges -->
                ${edges.map(edge => {
                    const source = positionedNodes.find(n => n.id === edge.source);
                    const target = positionedNodes.find(n => n.id === edge.target);
                    if (!source || !target) return '';
                    return `<line x1="${source.x}" y1="${source.y}" x2="${target.x}" y2="${target.y}" 
                            stroke="#dadce0" stroke-width="2" />`;
                }).join('')}
                
                <!-- Nodes -->
                ${positionedNodes.map(node => `
                    <g class="node-group" transform="translate(${node.x},${node.y})">
                        <circle r="${node.type === 'local' ? 20 : 15}" 
                                fill="${node.type === 'local' ? 'var(--accent)' : 'var(--bg-input)'}" 
                                stroke="${node.type === 'local' ? 'none' : 'var(--border-focus)'}"
                                stroke-width="2" />
                        <text dy="${node.type === 'local' ? 35 : 30}" text-anchor="middle" 
                              fill="var(--text-secondary)" font-size="10">
                            ${node.label}
                        </text>
                    </g>
                `).join('')}
            </svg>
        `;

        container.innerHTML = svg;
    }
}