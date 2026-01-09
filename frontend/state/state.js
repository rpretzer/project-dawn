/**
 * State Manager
 * Reactive state management for the application
 */

export class StateManager {
    constructor() {
        this.state = {
            // Connection
            connected: false,
            peers: 0,
            nodeId: null,
            
            // Agents
            agents: [],
            selectedAgent: null,
            
            // Chat Room (multi-agent conversation)
            chatRoom: {
                id: 'main', // Room ID
                name: 'Main Chat Room',
                participants: [], // Array of agent IDs in the room
                messages: [],
                tasks: [], // Active tasks being worked on
                threadId: null, // Current conversation thread
            },
            
            // Messages (deprecated, use chatRoom.messages)
            messages: [],
            
            // Tools, Resources, Prompts
            tools: [],
            resources: [],
            prompts: [],
            
            // UI State
            theme: 'dark',
        };
        
        this.subscribers = [];
    }
    
    getState() {
        return { ...this.state };
    }
    
    setState(updates) {
        const prevState = { ...this.state };
        this.state = { ...this.state, ...updates };
        this._notifySubscribers(prevState, this.state);
    }
    
    subscribe(callback) {
        this.subscribers.push(callback);
        return () => {
            const index = this.subscribers.indexOf(callback);
            if (index > -1) {
                this.subscribers.splice(index, 1);
            }
        };
    }
    
    _notifySubscribers(prevState, newState) {
        this.subscribers.forEach(callback => {
            try {
                callback(newState, prevState);
            } catch (error) {
                console.error('Error in state subscriber:', error);
            }
        });
    }
}

