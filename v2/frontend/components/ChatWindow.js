/**
 * Chat Window Component
 * Multi-agent chat room with self-organization capabilities
 */

export class ChatWindow {
    constructor(state, ws) {
        this.state = state;
        this.ws = ws;
        this.messagesContainer = document.getElementById('chat-messages');
        
        this.setupStateSubscription();
        this.setupRoomControls();
        
        // Initialize room header visibility
        const roomHeader = document.getElementById('chat-room-header');
        if (roomHeader) {
            roomHeader.style.display = 'flex';
        }
    }
    
    setupStateSubscription() {
        this.state.subscribe((newState, prevState) => {
            // Update messages if chat room changed
            const roomChanged = newState.chatRoom?.messages !== prevState.chatRoom?.messages;
            const participantsChanged = newState.chatRoom?.participants !== prevState.chatRoom?.participants;
            
            if (roomChanged || participantsChanged) {
                this.renderChatRoom(newState.chatRoom);
            }
            
            // Update room header
            if (participantsChanged || newState.chatRoom?.name !== prevState.chatRoom?.name) {
                this.updateRoomHeader(newState.chatRoom);
            }
        });
    }
    
    setupRoomControls() {
        // Setup event listeners for room controls (header is in HTML)
        const inviteBtn = document.getElementById('invite-agent-btn');
        if (inviteBtn) {
            inviteBtn.addEventListener('click', () => {
                this.showInviteAgentModal();
            });
        }
    }
    
    updateRoomHeader(room) {
        if (!room) return;
        
        const nameEl = document.getElementById('room-name');
        const participantsEl = document.getElementById('room-participants');
        
        if (nameEl) {
            nameEl.textContent = room.name || 'Chat Room';
        }
        
        if (participantsEl) {
            const state = this.state.getState();
            const agents = state.agents || [];
            const participants = (room.participants || []).map(agentId => {
                const agent = agents.find(a => a.agent_id === agentId);
                return agent || { agent_id: agentId, name: agentId };
            });
            
            participantsEl.innerHTML = participants.map(agent => `
                <span class="participant-badge" title="${agent.name || agent.agent_id}">
                    ${agent.name || agent.agent_id}
                </span>
            `).join('');
        }
    }
    
    renderChatRoom(room) {
        if (!room || !room.messages || room.messages.length === 0) {
            this.messagesContainer.innerHTML = `
                <div class="empty-state">
                    <p>This is a multi-agent chat room. Invite agents to start collaborating.</p>
                </div>
            `;
            return;
        }
        
        this.messagesContainer.innerHTML = room.messages.map(msg => this.renderMessage(msg)).join('');
        
        // Scroll to bottom
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }
    
    addMessage(message) {
        const state = this.state.getState();
        const room = state.chatRoom || { messages: [], participants: [] };
        const currentMessages = room.messages || [];
        
        // Ensure sender is in participants
        if (message.sender && !room.participants.includes(message.sender)) {
            room.participants = [...room.participants, message.sender];
        }
        
        const newMessage = {
            ...message,
            id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            timestamp: message.timestamp || Date.now(),
        };
        
        this.state.setState({
            chatRoom: {
                ...room,
                messages: [...currentMessages, newMessage],
                participants: room.participants,
            }
        });
    }
    
    async inviteAgentToRoom(agentId) {
        const state = this.state.getState();
        const room = state.chatRoom || { messages: [], participants: [] };
        
        if (room.participants.includes(agentId)) {
            return; // Already in room
        }
        
        // Add agent to participants
        const newParticipants = [...room.participants, agentId];
        
        this.state.setState({
            chatRoom: {
                ...room,
                participants: newParticipants,
            }
        });
        
        // Send invitation message
        this.addMessage({
            type: 'system',
            content: `Agent "${agentId}" has joined the room`,
            timestamp: Date.now(),
        });
        
        // Notify the agent (if it's a remote agent, send via P2P)
        // For now, just log
        console.log(`Invited agent ${agentId} to room`);
    }
    
    showInviteAgentModal() {
        const state = this.state.getState();
        const agents = state.agents || [];
        const room = state.chatRoom || { participants: [] };
        
        // Filter out agents already in room
        const availableAgents = agents.filter(a => !room.participants.includes(a.agent_id));
        
        if (availableAgents.length === 0) {
            alert('All available agents are already in the room');
            return;
        }
        
        // Create simple selection modal
        const agentList = availableAgents.map(a => 
            `- ${a.name || a.agent_id}`
        ).join('\n');
        
        const agentId = prompt(`Select an agent to invite:\n\n${agentList}\n\nEnter agent ID:`, '');
        
        if (agentId) {
            this.inviteAgentToRoom(agentId);
        }
    }
    
    renderMessages(messages) {
        if (messages.length === 0) {
            this.messagesContainer.innerHTML = `
                <div class="empty-state">
                    <p>Select an agent from the sidebar to start a conversation</p>
                </div>
            `;
            return;
        }
        
        this.messagesContainer.innerHTML = messages.map(msg => this.renderMessage(msg)).join('');
        
        // Scroll to bottom
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }
    
    renderMessage(message) {
        const time = new Date(message.timestamp).toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        
        if (message.type === 'system') {
            return `
                <div class="message system">
                    <div class="message-bubble">
                        <div class="message-content">${this.escapeHtml(message.content)}</div>
                        <div class="message-footer">
                            <span class="message-time">${time}</span>
                        </div>
                    </div>
                </div>
            `;
        }
        
        if (message.type === 'task') {
            return `
                <div class="message task">
                    <div class="message-bubble task-bubble">
                        <div class="task-header">
                            <span class="task-icon">📋</span>
                            <span class="task-title">${this.escapeHtml(message.task?.title || 'Task')}</span>
                        </div>
                        <div class="message-content">${this.escapeHtml(message.content)}</div>
                        ${message.task?.assignees ? `
                            <div class="task-assignees">
                                Assigned to: ${message.task.assignees.map(a => this.escapeHtml(a)).join(', ')}
                            </div>
                        ` : ''}
                        <div class="message-footer">
                            <span class="message-time">${time}</span>
                            ${message.task?.status ? `
                                <span class="task-status status-${message.task.status}">${message.task.status}</span>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        }
        
        if (message.type === 'agent-action') {
            return `
                <div class="message agent-action">
                    <div class="message-bubble action-bubble">
                        <div class="action-header">
                            <span class="action-icon">${message.action === 'invite' ? '👋' : '🤝'}</span>
                            <span class="action-text">${this.escapeHtml(message.content)}</span>
                        </div>
                        <div class="message-footer">
                            <span class="message-time">${time}</span>
                        </div>
                    </div>
                </div>
            `;
        }
        
        const isSent = message.type === 'sent';
        const sender = message.sender || 'You';
        const senderId = message.senderId || sender;
        
        // Get agent info for styling
        const state = this.state.getState();
        const agents = state.agents || [];
        const agent = agents.find(a => a.agent_id === senderId);
        const agentName = agent?.name || sender;
        
        return `
            <div class="message ${isSent ? 'sent' : 'received'}" data-sender-id="${senderId}">
                ${!isSent ? `
                    <div class="message-header">
                        <span class="sender-name">${this.escapeHtml(agentName)}</span>
                        ${agent ? `<span class="sender-badge">Agent</span>` : ''}
                    </div>
                ` : ''}
                <div class="message-bubble">
                    <div class="message-content">${this.escapeHtml(message.content)}</div>
                    ${message.metadata?.toolsUsed ? `
                        <div class="message-tools">
                            Tools used: ${message.metadata.toolsUsed.map(t => this.escapeHtml(t)).join(', ')}
                        </div>
                    ` : ''}
                    <div class="message-footer">
                        <span class="message-time">${time}</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

