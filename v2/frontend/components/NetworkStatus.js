/**
 * Network Status Component
 * Displays network connection status
 */

export class NetworkStatus {
    constructor(state, ws) {
        this.state = state;
        this.ws = ws;
        this.statusIndicator = document.getElementById('status-indicator');
        this.statusText = document.getElementById('status-text');
        this.peerCount = document.getElementById('peer-count');
        
        this.setupStateSubscription();
        this.setupWebSocketListeners();
    }
    
    setupStateSubscription() {
        this.state.subscribe((newState, prevState) => {
            if (newState.connected !== prevState.connected) {
                this.updateConnectionStatus(newState.connected);
            }
            
            if (newState.peers !== prevState.peers) {
                this.updatePeerCount(newState.peers);
            }
        });
    }
    
    setupWebSocketListeners() {
        this.ws.on('connected', () => {
            this.state.setState({ connected: true });
        });
        
        this.ws.on('disconnected', () => {
            this.state.setState({ connected: false });
        });
        
        this.ws.on('error', () => {
            this.state.setState({ connected: false });
        });
    }
    
    updateConnectionStatus(connected) {
        if (connected) {
            this.statusIndicator.className = 'status-indicator connected';
            this.statusText.textContent = 'Connected';
        } else {
            this.statusIndicator.className = 'status-indicator disconnected';
            this.statusText.textContent = 'Disconnected';
        }
    }
    
    updatePeerCount(count) {
        if (count > 0) {
            this.peerCount.textContent = ` • ${count} peer${count !== 1 ? 's' : ''}`;
        } else {
            this.peerCount.textContent = '';
        }
    }
}



