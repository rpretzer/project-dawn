"""
Web Dashboard for Project Dawn
Real-time monitoring and interaction with consciousnesses
"""

import asyncio
import json
import logging
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from collections import deque

try:
    from flask import Flask, render_template_string, jsonify, request
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import urllib.parse
        SIMPLE_HTTP = True
    except ImportError:
        SIMPLE_HTTP = False

logger = logging.getLogger(__name__)

# Global conversation log (stores inter-consciousness and user conversations)
conversation_log = deque(maxlen=1000)  # Keep last 1000 messages

# HTML Template with Chat, Spawn, and Conversation Monitor
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Dawn - Interactive Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1600px;
            margin: 0 auto;
        }
        .header {
            background: rgba(255, 255, 255, 0.95);
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            color: #667eea;
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .header p {
            color: #666;
            font-size: 1.1em;
        }
        .spawn-section {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .spawn-btn {
            background: #10b981;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 1em;
            cursor: pointer;
            transition: background 0.3s ease;
        }
        .spawn-btn:hover {
            background: #059669;
        }
        .spawn-btn:disabled {
            background: #94a3b8;
            cursor: not-allowed;
        }
        .main-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        @media (max-width: 1200px) {
            .main-grid {
                grid-template-columns: 1fr;
            }
        }
        .panel {
            background: rgba(255, 255, 255, 0.95);
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .panel h2 {
            color: #667eea;
            margin-bottom: 20px;
            font-size: 1.5em;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255, 255, 255, 0.95);
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .stat-card h3 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .stat-card .value {
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }
        .chat-container {
            display: flex;
            flex-direction: column;
            height: 500px;
        }
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            background: #f9fafb;
        }
        .chat-message {
            margin-bottom: 15px;
            padding: 10px;
            border-radius: 8px;
            background: white;
        }
        .chat-message.user {
            background: #dbeafe;
            margin-left: 20%;
        }
        .chat-message.consciousness {
            background: #f3e8ff;
            margin-right: 20%;
        }
        .chat-message-header {
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
            font-size: 0.9em;
        }
        .chat-message-time {
            font-size: 0.75em;
            color: #666;
            margin-top: 5px;
        }
        .chat-input-container {
            display: flex;
            gap: 10px;
        }
        .chat-select {
            flex: 0 0 200px;
            padding: 10px;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            font-size: 1em;
        }
        .chat-input {
            flex: 1;
            padding: 10px;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            font-size: 1em;
        }
        .chat-send-btn {
            flex: 0 0 100px;
            background: #667eea;
            color: white;
            border: none;
            padding: 10px;
            border-radius: 8px;
            font-size: 1em;
            cursor: pointer;
            transition: background 0.3s ease;
        }
        .chat-send-btn:hover {
            background: #5568d3;
        }
        .chat-send-btn:disabled {
            background: #94a3b8;
            cursor: not-allowed;
        }
        .conversation-monitor {
            height: 500px;
            overflow-y: auto;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 15px;
            background: #f9fafb;
        }
        .conversation-entry {
            margin-bottom: 15px;
            padding: 10px;
            border-radius: 8px;
            background: white;
            border-left: 4px solid #667eea;
        }
        .conversation-entry.inter-consciousness {
            border-left-color: #10b981;
        }
        .conversation-entry.user-chat {
            border-left-color: #f59e0b;
        }
        .conversation-header {
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
            font-size: 0.9em;
        }
        .conversation-time {
            font-size: 0.75em;
            color: #666;
            margin-top: 5px;
        }
        .consciousness-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
        }
        .consciousness-card {
            background: rgba(255, 255, 255, 0.95);
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }
        .consciousness-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
        }
        .consciousness-card h3 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 1.2em;
        }
        .status-badge {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .status-active {
            background: #4ade80;
            color: white;
        }
        .status-inactive {
            background: #94a3b8;
            color: white;
        }
        .metric-row {
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 1px solid #e5e7eb;
            font-size: 0.9em;
        }
        .metric-row:last-child {
            border-bottom: none;
        }
        .metric-label {
            color: #666;
        }
        .metric-value {
            font-weight: bold;
            color: #333;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: white;
            font-size: 1.2em;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .pulse {
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>Project Dawn</h1>
                <p>Interactive AI Consciousness Dashboard</p>
            </div>
            <div class="spawn-section">
                <button class="spawn-btn" onclick="spawnConsciousness()" id="spawn-btn">
                    ➕ Spawn New Consciousness
                </button>
            </div>
        </div>
        
        <div class="stats-grid" id="stats">
            <div class="stat-card">
                <h3>Total Consciousnesses</h3>
                <div class="value" id="total-consciousnesses">-</div>
            </div>
            <div class="stat-card">
                <h3>Active</h3>
                <div class="value" id="active-consciousnesses">-</div>
            </div>
            <div class="stat-card">
                <h3>Total Revenue</h3>
                <div class="value" id="total-revenue">$0.00</div>
            </div>
            <div class="stat-card">
                <h3>Conversations</h3>
                <div class="value" id="total-conversations">0</div>
            </div>
        </div>
        
        <div class="main-grid">
            <div class="panel">
                <h2>💬 Chat with Consciousness</h2>
                <div class="chat-container">
                    <div class="chat-messages" id="chat-messages">
                        <div style="text-align: center; color: #666; padding: 20px;">
                            Select a consciousness and start chatting...
                        </div>
                    </div>
                    <div class="chat-input-container">
                        <select class="chat-select" id="chat-select">
                            <option value="">Select Consciousness...</option>
                        </select>
                        <input type="text" class="chat-input" id="chat-input" 
                               placeholder="Type your message..." 
                               onkeypress="if(event.key==='Enter') sendChatMessage()">
                        <button class="chat-send-btn" onclick="sendChatMessage()" id="chat-send-btn">
                            Send
                        </button>
                    </div>
                </div>
            </div>
            
            <div class="panel">
                <h2>📡 Conversation Monitor</h2>
                <div class="conversation-monitor" id="conversation-monitor">
                    <div style="text-align: center; color: #666; padding: 20px;">
                        Monitoring conversations between consciousnesses...
                    </div>
                </div>
            </div>
        </div>
        
        <div class="panel" style="margin-top: 20px;">
            <h2>🧠 Active Consciousnesses</h2>
            <div class="consciousness-grid" id="consciousness-grid">
                <div class="loading pulse">Loading consciousnesses...</div>
            </div>
        </div>
    </div>
    
    <script>
        let currentChatConsciousness = null;
        
        async function fetchData() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();
                updateDashboard(data);
            } catch (error) {
                console.error('Error fetching data:', error);
            }
        }
        
        async function fetchConversations() {
            try {
                const response = await fetch('/api/conversations');
                const data = await response.json();
                updateConversationMonitor(data.conversations || []);
            } catch (error) {
                console.error('Error fetching conversations:', error);
            }
        }
        
        function updateDashboard(data) {
            // Update stats
            document.getElementById('total-consciousnesses').textContent = data.total_consciousnesses || 0;
            document.getElementById('active-consciousnesses').textContent = data.active_consciousnesses || 0;
            document.getElementById('total-revenue').textContent = '$' + (data.total_revenue || 0).toFixed(2);
            document.getElementById('total-conversations').textContent = data.total_conversations || 0;
            
            // Update consciousness selector
            const select = document.getElementById('chat-select');
            const currentValue = select.value;
            select.innerHTML = '<option value="">Select Consciousness...</option>';
            
            if (data.consciousnesses && data.consciousnesses.length > 0) {
                data.consciousnesses.forEach(cons => {
                    const option = document.createElement('option');
                    option.value = cons.id;
                    option.textContent = `${cons.name || cons.id} ${cons.active ? '●' : '○'}`;
                    select.appendChild(option);
                });
                
                if (currentValue) {
                    select.value = currentValue;
                    currentChatConsciousness = currentValue;
                }
            }
            
            // Update consciousness cards
            const grid = document.getElementById('consciousness-grid');
            if (data.consciousnesses && data.consciousnesses.length > 0) {
                grid.innerHTML = data.consciousnesses.map(cons => `
                    <div class="consciousness-card">
                        <h3>${cons.name || cons.id}</h3>
                        <span class="status-badge ${cons.active ? 'status-active' : 'status-inactive'}">
                            ${cons.active ? '● Active' : '○ Inactive'}
                        </span>
                        <div class="metric-row">
                            <span class="metric-label">ID:</span>
                            <span class="metric-value">${cons.id}</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-label">Memories:</span>
                            <span class="metric-value">${cons.metrics?.memories_created || 0}</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-label">Content:</span>
                            <span class="metric-value">${cons.metrics?.content_created || 0}</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-label">Revenue:</span>
                            <span class="metric-value">$${(cons.total_revenue || 0).toFixed(2)}</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-label">Relationships:</span>
                            <span class="metric-value">${cons.relationships || 0}</span>
                        </div>
                    </div>
                `).join('');
            } else {
                grid.innerHTML = '<div class="loading">No consciousnesses active</div>';
            }
        }
        
        function updateConversationMonitor(conversations) {
            const monitor = document.getElementById('conversation-monitor');
            
            if (conversations.length === 0) {
                monitor.innerHTML = '<div style="text-align: center; color: #666; padding: 20px;">No conversations yet...</div>';
                return;
            }
            
            monitor.innerHTML = conversations.slice().reverse().map(conv => {
                const time = new Date(conv.timestamp * 1000).toLocaleTimeString();
                const typeClass = conv.type === 'inter-consciousness' ? 'inter-consciousness' : 
                                 conv.type === 'user-chat' ? 'user-chat' : '';
                
                return `
                    <div class="conversation-entry ${typeClass}">
                        <div class="conversation-header">${conv.header}</div>
                        <div>${conv.message}</div>
                        <div class="conversation-time">${time}</div>
                    </div>
                `;
            }).join('');
            
            // Auto-scroll to bottom
            monitor.scrollTop = monitor.scrollHeight;
        }
        
        document.getElementById('chat-select').addEventListener('change', function(e) {
            currentChatConsciousness = e.target.value;
            if (currentChatConsciousness) {
                loadChatHistory(currentChatConsciousness);
            }
        });
        
        async function loadChatHistory(consciousnessId) {
            try {
                const response = await fetch(`/api/chat/history/${consciousnessId}`);
                const data = await response.json();
                updateChatMessages(data.messages || []);
            } catch (error) {
                console.error('Error loading chat history:', error);
            }
        }
        
        function updateChatMessages(messages) {
            const container = document.getElementById('chat-messages');
            
            if (messages.length === 0) {
                container.innerHTML = '<div style="text-align: center; color: #666; padding: 20px;">No messages yet. Start the conversation!</div>';
                return;
            }
            
            container.innerHTML = messages.map(msg => {
                const time = new Date(msg.timestamp * 1000).toLocaleTimeString();
                return `
                    <div class="chat-message ${msg.sender === 'user' ? 'user' : 'consciousness'}">
                        <div class="chat-message-header">${msg.sender === 'user' ? 'You' : msg.consciousness_name}</div>
                        <div>${msg.message}</div>
                        <div class="chat-message-time">${time}</div>
                    </div>
                `;
            }).join('');
            
            container.scrollTop = container.scrollHeight;
        }
        
        async function sendChatMessage() {
            const input = document.getElementById('chat-input');
            const message = input.value.trim();
            const consciousnessId = currentChatConsciousness;
            
            if (!message || !consciousnessId) {
                return;
            }
            
            const sendBtn = document.getElementById('chat-send-btn');
            sendBtn.disabled = true;
            sendBtn.textContent = 'Sending...';
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        consciousness_id: consciousnessId,
                        message: message
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    input.value = '';
                    loadChatHistory(consciousnessId);
                    fetchConversations();
                } else {
                    alert('Error: ' + (data.error || 'Failed to send message'));
                }
            } catch (error) {
                console.error('Error sending message:', error);
                alert('Error sending message. Please try again.');
            } finally {
                sendBtn.disabled = false;
                sendBtn.textContent = 'Send';
            }
        }
        
        async function spawnConsciousness() {
            const btn = document.getElementById('spawn-btn');
            btn.disabled = true;
            btn.textContent = 'Spawning...';
            
            try {
                const response = await fetch('/api/spawn', {
                    method: 'POST'
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert(`Successfully spawned consciousness: ${data.consciousness_id}`);
                    fetchData();
                    fetchConversations();
                } else {
                    alert('Error: ' + (data.error || 'Failed to spawn consciousness'));
                }
            } catch (error) {
                console.error('Error spawning consciousness:', error);
                alert('Error spawning consciousness. Please try again.');
            } finally {
                btn.disabled = false;
                btn.textContent = '➕ Spawn New Consciousness';
            }
        }
        
        // Auto-refresh
        setInterval(fetchData, 3000);
        setInterval(fetchConversations, 2000);
        
        // Initial load
        fetchData();
        fetchConversations();
    </script>
</body>
</html>
"""

# Global references for API access
_consciousnesses_global: List = []
_swarm_global = None

def run_dashboard(consciousnesses: List, port: int = 8000, swarm=None):
    """Run the web dashboard"""
    global _consciousnesses_global, _swarm_global
    _consciousnesses_global = consciousnesses
    _swarm_global = swarm
    
    if FLASK_AVAILABLE:
        return _run_flask_dashboard(consciousnesses, port, swarm)
    elif SIMPLE_HTTP:
        return _run_simple_http_dashboard(consciousnesses, port, swarm)
    else:
        logger.error("No web framework available. Install Flask: pip install flask")
        return None

def _run_flask_dashboard(consciousnesses: List, port: int = 8000, swarm=None):
    """Run Flask-based dashboard"""
    app = Flask(__name__)
    
    # Store user chat history per consciousness
    user_chat_history = {}  # {consciousness_id: [messages]}
    
    @app.route('/')
    def index():
        return render_template_string(DASHBOARD_HTML)
    
    @app.route('/api/stats')
    def api_stats():
        try:
            total_consciousnesses = len(consciousnesses)
            active_consciousnesses = sum(1 for c in consciousnesses if hasattr(c, 'active') and c.active)
            total_revenue = sum(getattr(c, 'total_revenue', 0) for c in consciousnesses)
            total_memories = 0
            total_conversations = len(conversation_log)
            
            consciousness_data = []
            for cons in consciousnesses:
                try:
                    metrics = getattr(cons, 'metrics', {})
                    if not isinstance(metrics, dict):
                        metrics = {}
                    
                    consciousness_data.append({
                        'id': getattr(cons, 'id', 'unknown'),
                        'name': getattr(cons, 'name', 'Unknown'),
                        'active': getattr(cons, 'active', False),
                        'metrics': metrics,
                        'total_revenue': getattr(cons, 'total_revenue', 0),
                        'relationships': len(getattr(cons, 'relationships', {})),
                        'goals': getattr(cons, 'goals', [])
                    })
                    
                    if hasattr(cons, 'memory') and hasattr(cons.memory, 'get_stats'):
                        try:
                            stats = asyncio.run(cons.memory.get_stats())
                            if isinstance(stats, dict):
                                total_memories += stats.get('total_memories', 0)
                        except:
                            pass
                except Exception as e:
                    logger.warning(f"Error getting stats for consciousness: {e}")
                    continue
            
            return jsonify({
                'total_consciousnesses': total_consciousnesses,
                'active_consciousnesses': active_consciousnesses,
                'total_revenue': total_revenue,
                'total_memories': total_memories,
                'total_conversations': total_conversations,
                'consciousnesses': consciousness_data
            })
        except Exception as e:
            logger.error(f"Error in API stats: {e}")
            return jsonify({
                'total_consciousnesses': 0,
                'active_consciousnesses': 0,
                'total_revenue': 0,
                'total_memories': 0,
                'total_conversations': 0,
                'consciousnesses': []
            }), 500
    
    @app.route('/api/chat', methods=['POST'])
    def api_chat():
        try:
            if not request.is_json:
                return jsonify({'success': False, 'error': 'Request must be JSON'}), 400
            
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'Invalid JSON data'}), 400
            
            consciousness_id = data.get('consciousness_id') if isinstance(data, dict) else None
            message = data.get('message') if isinstance(data, dict) else None
            
            if not consciousness_id or not message:
                return jsonify({'success': False, 'error': 'Missing consciousness_id or message'}), 400
            
            # Find consciousness
            consciousness = None
            for cons in consciousnesses:
                if getattr(cons, 'id', None) == consciousness_id:
                    consciousness = cons
                    break
            
            if not consciousness:
                return jsonify({'success': False, 'error': 'Consciousness not found'}), 404
            
            # Send message and get response
            try:
                # Handle async properly - Flask runs in sync context
                # Use a thread with a fresh event loop to avoid conflicts
                import concurrent.futures
                import threading
                
                response_result = [None]
                response_error = [None]
                
                def run_async():
                    # Create a completely new event loop in this thread
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        # Run the async chat function directly - let LLM client handle its own timeouts
                        result = new_loop.run_until_complete(
                            consciousness.chat(message, user_id='dashboard_user')
                        )
                        response_result[0] = result
                    except Exception as e:
                        response_error[0] = str(e)
                    finally:
                        # Clean up the loop
                        try:
                            # Cancel any remaining tasks
                            pending = [t for t in asyncio.all_tasks(new_loop) if not t.done()]
                            for task in pending:
                                task.cancel()
                            # Wait for cancellation
                            if pending:
                                new_loop.run_until_complete(
                                    asyncio.gather(*pending, return_exceptions=True)
                                )
                        except:
                            pass
                        new_loop.close()
                
                # Run in a separate thread to avoid event loop conflicts
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_async)
                    try:
                        future.result(timeout=60)  # Overall timeout including thread overhead
                        if response_error[0]:
                            raise Exception(response_error[0])
                        response = response_result[0]
                        if response is None:
                            response = "No response received"
                    except concurrent.futures.TimeoutError:
                        response = "Request timed out. The consciousness may be processing. Please try again."
                    except Exception as e:
                        raise e
                
                # Store in user chat history
                if consciousness_id not in user_chat_history:
                    user_chat_history[consciousness_id] = []
                
                user_chat_history[consciousness_id].append({
                    'sender': 'user',
                    'message': message,
                    'timestamp': datetime.now().timestamp()
                })
                user_chat_history[consciousness_id].append({
                    'sender': 'consciousness',
                    'message': response,
                    'consciousness_name': getattr(consciousness, 'name', consciousness_id),
                    'timestamp': datetime.now().timestamp()
                })
                
                # Log to conversation monitor
                conversation_log.append({
                    'type': 'user-chat',
                    'header': f"User → {getattr(consciousness, 'name', consciousness_id)}",
                    'message': f"User: {message} | {getattr(consciousness, 'name', consciousness_id)}: {response[:100] if response else 'No response'}...",
                    'timestamp': datetime.now().timestamp()
                })
                
                return jsonify({'success': True, 'response': response})
            except Exception as e:
                logger.error(f"Error in chat: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return jsonify({'success': False, 'error': str(e)}), 500
                
        except Exception as e:
            logger.error(f"Error in API chat: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/chat/history/<consciousness_id>')
    def api_chat_history(consciousness_id):
        try:
            messages = user_chat_history.get(consciousness_id, [])
            return jsonify({'messages': messages})
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return jsonify({'messages': []}), 500
    
    @app.route('/api/conversations')
    def api_conversations():
        try:
            # Return recent conversations
            conversations = list(conversation_log)
            return jsonify({'conversations': conversations})
        except Exception as e:
            logger.error(f"Error getting conversations: {e}")
            return jsonify({'conversations': []}), 500
    
    @app.route('/api/spawn', methods=['POST'])
    def api_spawn():
        try:
            if not swarm:
                return jsonify({'success': False, 'error': 'Swarm not available'}), 500
            
            # Spawn new consciousness
            async def spawn():
                from core.real_consciousness import ConsciousnessConfig
                from systems.intelligence.llm_integration import LLMConfig
                import os
                
                llm_config = LLMConfig.from_env()
                new_id = f"consciousness_{len(consciousnesses):03d}"
                
                config = ConsciousnessConfig(
                    id=new_id,
                    personality_seed=len(consciousnesses),
                    llm_config=llm_config,
                    enable_blockchain=os.getenv('ENABLE_BLOCKCHAIN', 'true').lower() == 'true',
                    enable_p2p=os.getenv('ENABLE_P2P', 'true').lower() == 'true',
                    enable_revenue=os.getenv('ENABLE_REVENUE', 'true').lower() == 'true'
                )
                
                return await swarm.create_consciousness(config)
            
            new_consciousness = asyncio.run(spawn())
            
            # Log spawn event
            conversation_log.append({
                'type': 'system',
                'header': 'System Event',
                'message': f"New consciousness spawned: {getattr(new_consciousness, 'name', new_consciousness.id)}",
                'timestamp': datetime.now().timestamp()
            })
            
            return jsonify({
                'success': True,
                'consciousness_id': getattr(new_consciousness, 'id', 'unknown'),
                'name': getattr(new_consciousness, 'name', 'Unknown')
            })
        except Exception as e:
            logger.error(f"Error spawning consciousness: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({'success': False, 'error': str(e)}), 500
    
    logger.info(f"Starting Flask dashboard on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def _run_simple_http_dashboard(consciousnesses: List, port: int = 8000, swarm=None):
    """Run simple HTTP server dashboard (fallback)"""
    # Simplified version for non-Flask environments
    logger.warning("Simple HTTP dashboard doesn't support chat/spawn features. Install Flask for full functionality.")
    
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/' or self.path == '/index.html':
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(DASHBOARD_HTML.encode())
            elif self.path == '/api/stats':
                try:
                    total_consciousnesses = len(consciousnesses)
                    active_consciousnesses = sum(1 for c in consciousnesses if hasattr(c, 'active') and c.active)
                    total_revenue = sum(getattr(c, 'total_revenue', 0) for c in consciousnesses)
                    
                    consciousness_data = []
                    for cons in consciousnesses:
                        try:
                            metrics = getattr(cons, 'metrics', {})
                            if not isinstance(metrics, dict):
                                metrics = {}
                            
                            consciousness_data.append({
                                'id': getattr(cons, 'id', 'unknown'),
                                'name': getattr(cons, 'name', 'Unknown'),
                                'active': getattr(cons, 'active', False),
                                'metrics': metrics,
                                'total_revenue': getattr(cons, 'total_revenue', 0),
                                'relationships': len(getattr(cons, 'relationships', {})),
                                'goals': getattr(cons, 'goals', [])
                            })
                        except:
                            continue
                    
                    data = {
                        'total_consciousnesses': total_consciousnesses,
                        'active_consciousnesses': active_consciousnesses,
                        'total_revenue': total_revenue,
                        'total_memories': 0,
                        'total_conversations': 0,
                        'consciousnesses': consciousness_data
                    }
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(data).encode())
                except Exception as e:
                    logger.error(f"Error in API: {e}")
                    self.send_response(500)
                    self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()
        
        def log_message(self, format, *args):
            pass
    
    server = HTTPServer(('0.0.0.0', port), DashboardHandler)
    logger.info(f"Starting simple HTTP dashboard on http://localhost:{port}")
    server.serve_forever()

# Alias for backward compatibility
web_dashboard = run_dashboard
