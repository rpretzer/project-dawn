/**
 * WebSocket Client for MCP
 * 
 * Handles WebSocket connection to MCP Host and message routing.
 */

class WebSocketClient {
    constructor(url) {
        this.url = url;
        this.ws = null;
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
        this.reconnectAttempts = 0;
        this.messageHandlers = [];
        this.connectionState = 'disconnected';
    }
    
    connect() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.log('Already connected');
            return;
        }
        
        console.log(`Connecting to ${this.url}...`);
        this.connectionState = 'connecting';
        this.updateConnectionStatus('connecting', 'Connecting...');
        
        try {
            this.ws = new WebSocket(this.url);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.connectionState = 'connected';
                this.reconnectAttempts = 0;
                this.updateConnectionStatus('connected', 'Connected');
                this.onConnect();
            };
            
            this.ws.onmessage = (event) => {
                this.handleMessage(event.data);
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus('error', 'Error');
                this.onError(error);
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.connectionState = 'disconnected';
                this.updateConnectionStatus('disconnected', 'Disconnected');
                this.onDisconnect();
                this.attemptReconnect();
            };
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.updateConnectionStatus('error', 'Failed to connect');
            this.attemptReconnect();
        }
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.connectionState = 'disconnected';
        this.updateConnectionStatus('disconnected', 'Disconnected');
    }
    
    attemptReconnect() {
        if (this.connectionState === 'connected') {
            return;
        }
        
        this.reconnectAttempts++;
        const delay = Math.min(
            this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
            this.maxReconnectDelay
        );
        
        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})...`);
        this.updateConnectionStatus('connecting', `Reconnecting... (${this.reconnectAttempts})`);
        
        setTimeout(() => {
            this.connect();
        }, delay);
    }
    
    send(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
            return true;
        } else {
            console.error('WebSocket not connected');
            return false;
        }
    }
    
    handleMessage(data) {
        try {
            const message = JSON.parse(data);
            
            // Handle JSON-RPC 2.0 responses for pending requests
            if (message.jsonrpc === "2.0" && message.id) {
                // Check if this is a response to a pending request
                const pending = this.pendingRequests.get(message.id);
                if (pending) {
                    clearTimeout(pending.timeout);
                    this.pendingRequests.delete(message.id);
                    
                    if (message.error) {
                        pending.reject(new Error(message.error.message || 'Request failed'));
                    } else {
                        pending.resolve(message.result);
                    }
                    return;
                }
                
                // Fall through to handle as general message
            }
            
            // Handle event notifications
            if (message.type === 'event') {
                this.messageHandlers.forEach(handler => {
                    try {
                        handler({
                            type: 'event',
                            ...message
                        });
                    } catch (error) {
                        console.error('Error in message handler:', error);
                    }
                });
            } else {
                // Generic message
                this.messageHandlers.forEach(handler => {
                    try {
                        handler(message);
                    } catch (error) {
                        console.error('Error in message handler:', error);
                    }
                });
            }
        } catch (error) {
            console.error('Error parsing message:', error);
        }
    }
    
    pendingRequests = new Map();
    
    async sendJSONRPCAsync(method, params = {}) {
        /**
         * Send JSON-RPC request and wait for response
         * 
         * @param {string} method - Method name
         * @param {object} params - Parameters
         * @returns {Promise} - Promise that resolves with response
         */
        return new Promise((resolve, reject) => {
            const id = Date.now().toString() + Math.random().toString(36).substr(2, 9);
            
            // Set up response handler
            const timeout = setTimeout(() => {
                this.pendingRequests.delete(id);
                reject(new Error(`Request ${method} timed out`));
            }, 30000); // 30 second timeout
            
            this.pendingRequests.set(id, { resolve, reject, timeout, method });
            
            // Send request
            this.sendJSONRPC(method, params, id);
        });
    }
    
    onMessage(handler) {
        this.messageHandlers.push(handler);
    }
    
    updateConnectionStatus(state, text) {
        const statusDot = document.getElementById('status-dot');
        const statusText = document.getElementById('status-text');
        
        if (statusDot) {
            statusDot.className = 'status-dot';
            if (state === 'connected') {
                statusDot.classList.add('connected');
            } else if (state === 'disconnected' || state === 'error') {
                statusDot.classList.add('disconnected');
            } else {
                statusDot.classList.add('connecting');
            }
        }
        
        if (statusText) {
            statusText.textContent = text;
        }
    }
    
    onConnect() {
        // Override in main.js
    }
    
    onDisconnect() {
        // Override in main.js
    }
    
    onError(error) {
        // Override in main.js
    }
    
    isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }
}

