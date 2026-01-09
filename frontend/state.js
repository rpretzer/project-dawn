/**
 * State Management
 * 
 * Reactive state management for the frontend.
 */

class StateManager {
    constructor() {
        this.state = {
            agents: [],
            tools: [],
            events: 0,
            connected: false,
        };
        this.subscribers = [];
    }
    
    setState(updates) {
        const oldState = { ...this.state };
        this.state = { ...this.state, ...updates };
        this.notifySubscribers(oldState, this.state);
    }
    
    getState() {
        return { ...this.state };
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
    
    notifySubscribers(oldState, newState) {
        this.subscribers.forEach(callback => {
            try {
                callback(newState, oldState);
            } catch (error) {
                console.error('Error in state subscriber:', error);
            }
        });
    }
    
    // State updaters
    setAgents(agents) {
        this.setState({ agents });
    }
    
    setTools(tools) {
        this.setState({ tools });
    }
    
    incrementEvents() {
        this.setState({ events: this.state.events + 1 });
    }
    
    setConnected(connected) {
        this.setState({ connected });
    }
}



