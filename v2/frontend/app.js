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
        this.init();
    }

    init() {
        // Setup WebSocket connection
        this.ws.connect();
        
        // Setup event listeners
        this.setupTabs();
        this.setupChatInput();
        this.setupThemeToggle();
        
        // Listen for WebSocket events
        this.ws.on('connected', () => {
            console.log('Connected to server');
        });
        
        this.ws.on('message', (data) => {
            console.log('Received message:', data);
            // Handle incoming messages here
        });
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
                const tabName = button.dataset.tab;
                
                // Update active states
                tabButtons.forEach(btn => btn.classList.remove('active'));
                Object.values(tabContents).forEach(content => {
                    if (content) {
                        content.classList.remove('active');
                        content.style.display = 'none';
                    }
                });
                
                button.classList.add('active');
                if (tabContents[tabName]) {
                    tabContents[tabName].classList.add('active');
                    tabContents[tabName].style.display = 'block';
                }
            });
        });
    }

    setupChatInput() {
        const chatInput = document.getElementById('chat-input');
        const sendButton = document.getElementById('send-button');

        const sendMessage = () => {
            const text = chatInput.value.trim();
            if (!text) return;

            // Add message to UI
            this.addMessage({
                type: 'user',
                content: text,
                timestamp: Date.now()
            });

            // Send via WebSocket
            if (this.ws.isConnected()) {
                this.ws.send({
                    type: 'chat',
                    content: text
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

    addMessage(message) {
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return;

        // Remove empty state if present
        const emptyState = messagesContainer.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }

        const messageEl = document.createElement('div');
        messageEl.className = `message ${message.type || 'received'}`;
        
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.textContent = message.content;
        
        messageEl.appendChild(bubble);
        messagesContainer.appendChild(messageEl);
        
        // Scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
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
}

// Initialize app when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        new App();
    });
} else {
    new App();
}
