"""
Web Dashboard for Project Dawn
Retro BBS-style IRC chat room interface
"""

import asyncio
import json
import logging
import hashlib
import secrets
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque, defaultdict

try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

try:
    from flask import Flask, render_template_string, jsonify, request, session
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import urllib.parse
        SIMPLE_HTTP = True
    except ImportError:
        SIMPLE_HTTP = False

from .user_database import UserDatabase

logger = logging.getLogger(__name__)

# Initialize user database
_user_db = UserDatabase()

# Global room chat log (stores all messages in the room)
room_chat_log = deque(maxlen=2000)  # Keep last 2000 messages

# User management (keeping some in-memory for session tracking)
active_users: Dict[str, Dict[str, Any]] = {}  # user_id -> user_info (for active sessions)
user_away_messages: Dict[int, Optional[str]] = {}  # user_id -> away_message (using database user_id)
user_ignored: Dict[int, set] = defaultdict(set)  # user_id -> set of ignored user_ids (using database user_id)
rate_limits: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))  # user_id -> timestamps

# Admin management (simple IP-based for now, can be enhanced)
ADMIN_IPS = {'127.0.0.1', '::1', 'localhost'}  # Add your IP here
ADMIN_USERNAMES = {'admin', 'rpretzer'}  # Add admin usernames here

def is_admin(user_id: Optional[int] = None, ip: str = None) -> bool:
    """Check if user is admin"""
    if ip and ip in ADMIN_IPS:
        return True
    if FLASK_AVAILABLE:
        try:
            username = session.get('username', '')
            if username and username.lower() in ADMIN_USERNAMES:
                return True
        except:
            pass
    return False

# Password hashing functions using bcrypt
def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    if not BCRYPT_AVAILABLE:
        logger.warning("bcrypt not available, falling back to SHA256 (insecure)")
        return hashlib.sha256(password.encode()).hexdigest()
    
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash"""
    if not BCRYPT_AVAILABLE:
        logger.warning("bcrypt not available, using SHA256 verification (insecure)")
        return hash_password(password) == password_hash
    
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False

def get_user_id() -> Optional[int]:
    """Get authenticated user ID from session (returns None for guests)"""
    if not FLASK_AVAILABLE:
        return None
    
    # Return database user_id if authenticated
    if 'user_id' in session:
        try:
            return int(session['user_id'])
        except (ValueError, TypeError):
            pass
    
    return None

def get_username() -> Optional[str]:
    """Get authenticated username from session"""
    if not FLASK_AVAILABLE:
        return None
    return session.get('username')

def is_authenticated() -> bool:
    """Check if user is authenticated"""
    return get_user_id() is not None

def get_nickname(user_id: Optional[int] = None) -> str:
    """Get nickname for user"""
    if user_id is None:
        user_id = get_user_id()
    
    if user_id:
        # Try to get from session first (fast)
        nickname = session.get('nickname')
        if nickname:
            return nickname
        
        # Fallback to database lookup
        user = _user_db.get_user_by_id(user_id)
        if user and user.get('nickname'):
            return user['nickname']
    
    # Guest user
    return session.get('nickname', f"Guest{secrets.token_hex(4)}")

def check_rate_limit(user_id: Optional[int] = None, max_per_minute: int = 10, ip_address: Optional[str] = None) -> bool:
    """Check if user is rate limited
    
    Note: ip_address should be passed from route handlers where request is available
    """
    if user_id is None:
        user_id = get_user_id()
    
    # Use string key for rate limiting (works with both int user_id and guest sessions)
    if user_id:
        rate_key = f"user_{user_id}"
    else:
        # For guests, use IP address
        rate_key = f"guest_{ip_address or 'unknown'}"
    
    now = time.time()
    user_rates = rate_limits[rate_key]
    
    # Remove old timestamps (older than 1 minute)
    while user_rates and user_rates[0] < now - 60:
        user_rates.popleft()
    
    if len(user_rates) >= max_per_minute:
        return False
    
    user_rates.append(now)
    return True

# Retro BBS-style HTML Template
BBS_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PROJECT DAWN BBS - Main Chat Room</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        html, body {
            height: 100%;
            margin: 0;
            padding: 0;
            overflow: hidden;
        }
        
        body {
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            background: #000000;
            color: #00ff00;
            font-size: 14px;
            line-height: 1.4;
            padding: 10px;
            overflow-x: hidden;
            display: flex;
            flex-direction: column;
        }
        
        .screen {
            max-width: 1200px;
            width: 100%;
            margin: 0 auto;
            border: 2px solid #00ff00;
            background: #000000;
            padding: 0;
            display: flex;
            flex-direction: column;
            height: 100%;
            max-height: 100vh;
        }
        
        .header {
            border-bottom: 2px solid #00ff00;
            padding: 10px;
            background: #001100;
            text-align: center;
        }
        
        .ascii-art {
            font-family: 'Courier New', monospace;
            font-size: 10px;
            line-height: 1.2;
            color: #00ff00;
            white-space: pre;
            text-align: center;
            margin: 5px 0;
        }
        
        .header-text {
            color: #00ff00;
            text-transform: uppercase;
            font-weight: bold;
            margin: 5px 0;
        }
        
        .status-bar {
            border-bottom: 1px solid #00ff00;
            padding: 5px 10px;
            background: #001100;
            display: flex;
            justify-content: space-between;
            font-size: 12px;
        }
        
        .status-item {
            color: #00ff00;
        }
        
        .status-item::before {
            content: "[ ";
        }
        
        .status-item::after {
            content: " ]";
        }
        
        .chat-room {
            flex: 1;
            overflow-y: auto;
            padding: 10px;
            background: #000000;
            border-bottom: 2px solid #00ff00;
            min-height: 0;
        }
        
        .screen {
            display: flex;
            flex-direction: column;
            height: 100vh;
        }
        
        .screen-content {
            display: flex;
            flex-direction: column;
            flex: 1;
            min-height: 0;
        }
        
        .chat-room::-webkit-scrollbar {
            width: 10px;
        }
        
        .chat-room::-webkit-scrollbar-track {
            background: #001100;
        }
        
        .chat-room::-webkit-scrollbar-thumb {
            background: #00ff00;
        }
        
        .message {
            margin-bottom: 2px;
            padding: 2px 0;
            word-wrap: break-word;
        }
        
        .message.system {
            color: #ffff00;
        }
        
        .message.user {
            color: #00ffff;
        }
        
        .message.consciousness {
            color: #00ff00;
        }
        
        .message.inter-consciousness {
            color: #ff00ff;
        }
        
        .message.action {
            color: #ffff00;
            font-style: italic;
        }
        
        .timestamp {
            color: #666666;
            font-size: 11px;
        }
        
        .nick {
            font-weight: bold;
            color: #ffffff;
        }
        
        .input-area {
            border-top: 2px solid #00ff00;
            padding: 10px;
            background: #001100;
        }
        
        .input-prompt {
            color: #00ff00;
            display: inline-block;
            margin-right: 5px;
        }
        
        .input-line {
            display: flex;
            align-items: center;
        }
        
        #chat-input {
            flex: 1;
            background: #000000;
            border: 1px solid #00ff00;
            color: #00ff00;
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            font-size: 14px;
            padding: 5px;
            outline: none;
        }
        
        #chat-input:focus {
            border-color: #00ffff;
            box-shadow: 0 0 5px #00ffff;
        }
        
        .commands {
            border-top: 1px solid #00ff00;
            padding: 5px 10px;
            background: #001100;
            font-size: 11px;
            color: #666666;
        }
        
        .commands strong {
            color: #00ff00;
        }
        
        .blink {
            animation: blink 1s infinite;
        }
        
        @keyframes blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0; }
        }
        
        .who-list {
            position: fixed;
            right: 10px;
            top: 10px;
            width: 200px;
            border: 1px solid #00ff00;
            background: #000000;
            padding: 5px;
            font-size: 11px;
        }
        
        .who-list-title {
            color: #00ff00;
            border-bottom: 1px solid #00ff00;
            padding-bottom: 3px;
            margin-bottom: 5px;
            text-transform: uppercase;
        }
        
        .who-item {
            color: #00ff00;
            padding: 2px 0;
        }
        
        .who-item.active::before {
            content: "* ";
            color: #00ff00;
        }
        
        .stats-panel {
            border-top: 2px solid #00ff00;
            background: #001100;
            padding: 10px;
            display: none;
            max-height: 300px;
            overflow-y: auto;
        }
        
        .stats-panel.visible {
            display: block;
        }
        
        .stats-panel-title {
            color: #00ff00;
            text-transform: uppercase;
            font-weight: bold;
            margin-bottom: 10px;
            border-bottom: 1px solid #00ff00;
            padding-bottom: 5px;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
            font-size: 12px;
        }
        
        .stat-item {
            color: #00ff00;
            border: 1px solid #00ff00;
            padding: 5px;
            background: #000000;
        }
        
        .stat-label {
            color: #666666;
            font-size: 10px;
            text-transform: uppercase;
        }
        
        .stat-value {
            color: #00ff00;
            font-weight: bold;
            font-size: 14px;
        }
        
        .consciousness-stat {
            border: 1px solid #00ff00;
            padding: 5px;
            margin-bottom: 5px;
            background: #000000;
            font-size: 11px;
        }
        
        .consciousness-stat-name {
            color: #00ffff;
            font-weight: bold;
        }
        
        .consciousness-stat-detail {
            color: #00ff00;
            margin-left: 10px;
        }
        
        /* Login/Registration Modal */
        .auth-modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.8);
        }
        
        .auth-modal.visible {
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .auth-modal-content {
            background-color: #000000;
            border: 2px solid #00ff00;
            padding: 20px;
            width: 90%;
            max-width: 400px;
            font-family: 'Share Tech Mono', 'Courier New', monospace;
        }
        
        .auth-modal-header {
            color: #00ff00;
            text-align: center;
            margin-bottom: 15px;
            font-size: 16px;
            font-weight: bold;
            text-transform: uppercase;
            border-bottom: 1px solid #00ff00;
            padding-bottom: 10px;
        }
        
        .auth-form-group {
            margin-bottom: 15px;
        }
        
        .auth-form-label {
            display: block;
            color: #00ff00;
            margin-bottom: 5px;
            font-size: 12px;
        }
        
        .auth-form-input {
            width: 100%;
            background-color: #000000;
            border: 1px solid #00ff00;
            color: #00ff00;
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            font-size: 14px;
            padding: 8px;
            outline: none;
            box-sizing: border-box;
        }
        
        .auth-form-input:focus {
            border-color: #00ffff;
            box-shadow: 0 0 5px #00ffff;
        }
        
        .auth-form-buttons {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }
        
        .auth-button {
            flex: 1;
            background-color: #001100;
            border: 1px solid #00ff00;
            color: #00ff00;
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            font-size: 12px;
            padding: 10px;
            cursor: pointer;
            text-transform: uppercase;
        }
        
        .auth-button:hover {
            background-color: #003300;
            border-color: #00ffff;
        }
        
        .auth-button:active {
            background-color: #005500;
        }
        
        .auth-error {
            color: #ff0000;
            font-size: 11px;
            margin-top: 5px;
            display: none;
        }
        
        .auth-error.visible {
            display: block;
        }
        
        .auth-switch-link {
            text-align: center;
            margin-top: 15px;
            font-size: 11px;
            color: #666666;
        }
        
        .auth-switch-link a {
            color: #00ff00;
            cursor: pointer;
            text-decoration: underline;
        }
        
        .auth-switch-link a:hover {
            color: #00ffff;
        }
        
        /* User status in header */
        .user-status {
            position: absolute;
            top: 10px;
            right: 10px;
            font-size: 11px;
            color: #00ff00;
        }
        
        .user-status-logged-in {
            color: #00ffff;
        }
        
        .user-status-button {
            background: none;
            border: 1px solid #00ff00;
            color: #00ff00;
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            font-size: 10px;
            padding: 3px 8px;
            cursor: pointer;
            margin-left: 10px;
        }
        
        .user-status-button:hover {
            border-color: #00ffff;
            color: #00ffff;
        }
        
        .header {
            position: relative;
        }
    </style>
</head>
<body>
    <div class="screen">
        <div class="header">
            <div class="ascii-art">
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     ██▓███   ▒█████   ██▀███   ██▓███   ██▓ ██▓███  ▄▄▄       ║
║    ▓██░  ██▒▒██▒  ██▒▓██ ▒ ██▒▓██░  ██▒▓██▒▓██░  ██▒████▄     ║
║    ▓██░ ██▓▒▒██░  ██▒▓██ ░▄▄ ▒▓██░ ██▓▒▒██▒▓██░ ██▓▒██  ▀█▄   ║
║    ▒██▄█▓▒ ▒▒██   ██░▒██▀▀█▄  ▒██▄█▓▒ ▒░██░▒██▄█▓▒ ░██▄▄▄▄██  ║
║    ▒██▒ ░  ░░ ████▓▒░░██▓ ▒██▒▒██▒ ░  ░░██░▒██▒ ░  ░▓█   ▓██▒ ║
║    ▒▓▒░ ░  ░░ ▒░▒░▒░ ░ ▒▓ ░▒▓░▒▓▒░ ░  ░░▓  ▒▓▒░ ░  ░▒▒   ▓▒█░ ║
║    ░▒ ░       ░ ▒ ▒░   ░▒ ░ ▒░░▒ ░      ▒ ░░▒ ░      ▒   ▒▒ ░ ║
║    ░░       ░ ░ ░ ▒    ░░   ░ ░░        ▒ ░░░        ░   ▒    ║
║                ░ ░     ░                ░              ░  ░    ║
║                                                               ║
║              BULLETIN BOARD SYSTEM v2.0                       ║
║              MAIN CHAT ROOM - IRC STYLE                       ║
╚═══════════════════════════════════════════════════════════════╝
            </div>
            <div class="header-text">PROJECT DAWN BBS - MAIN CHAT ROOM</div>
            <div class="user-status" id="user-status">
                <span id="user-status-text">Guest</span>
                <button class="user-status-button" id="login-button" onclick="showLoginModal()">LOGIN</button>
            </div>
        </div>
        
        <!-- Login/Registration Modal -->
        <div class="auth-modal" id="auth-modal">
            <div class="auth-modal-content">
                <div class="auth-modal-header" id="auth-modal-header">LOGIN</div>
                <form id="auth-form">
                    <div class="auth-form-group">
                        <label class="auth-form-label" for="auth-username">USERNAME:</label>
                        <input type="text" class="auth-form-input" id="auth-username" required autocomplete="username">
                    </div>
                    <div class="auth-form-group" id="auth-nickname-group" style="display: none;">
                        <label class="auth-form-label" for="auth-nickname">NICKNAME (OPTIONAL):</label>
                        <input type="text" class="auth-form-input" id="auth-nickname" autocomplete="nickname">
                    </div>
                    <div class="auth-form-group">
                        <label class="auth-form-label" for="auth-password">PASSWORD:</label>
                        <input type="password" class="auth-form-input" id="auth-password" required autocomplete="current-password">
                    </div>
                    <div class="auth-error" id="auth-error"></div>
                    <div class="auth-form-buttons">
                        <button type="submit" class="auth-button" id="auth-submit">LOGIN</button>
                        <button type="button" class="auth-button" onclick="closeAuthModal()">CANCEL</button>
                    </div>
                    <div class="auth-switch-link" id="auth-switch-link">
                        <a onclick="toggleAuthMode()" id="auth-switch-text">Create new account</a>
                    </div>
                </form>
            </div>
        </div>
        
        <div class="status-bar">
            <span class="status-item" id="status-users">USERS: 0</span>
            <span class="status-item" id="status-active">ACTIVE: 0</span>
            <span class="status-item" id="status-messages">MSGS: 0</span>
            <span class="status-item" id="status-time">TIME: --:--:--</span>
        </div>
        
        <div class="who-list" id="who-list">
            <div class="who-list-title">WHO IS HERE</div>
            <div id="who-content">Loading...</div>
        </div>
        
        <div class="screen-content">
            <div class="chat-room" id="chat-room">
                <div class="message system">
                    <span class="timestamp">[SYSTEM]</span> Connecting to Project Dawn BBS...
                </div>
            </div>
            
            <div class="stats-panel" id="stats-panel">
                <div class="stats-panel-title">SYSTEM STATISTICS</div>
                <div id="stats-content">Loading stats...</div>
            </div>
            
            <div class="input-area">
                <div class="input-line">
                    <span class="input-prompt">&gt;</span>
                    <input type="text" id="chat-input" placeholder="Type your message here... (Press ENTER to send)" autocomplete="off">
                </div>
            </div>
            
            <div class="commands">
                <strong>COMMANDS:</strong> /help - Show all commands | /nick &lt;name&gt; - Change nickname | /who - List users | /me &lt;action&gt; - Action message
            </div>
        </div>
    </div>
    
    <script>
        let messageId = 0;
        let currentNickname = 'Guest' + Math.random().toString(36).substr(2, 4);
        let awayMessage = null;
        let ignoredUsers = new Set();
        let isAuthenticated = false;
        let currentUsername = null;
        let isLoginMode = true; // true for login, false for registration
        
        // Load user info on startup
        fetch('/api/user/info')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (data.authenticated) {
                        isAuthenticated = true;
                        currentUsername = data.username;
                        currentNickname = data.nickname;
                        updateUserStatus(data.username, data.nickname);
                    } else {
                        currentNickname = data.nickname;
                        updateUserStatus(null, data.nickname);
                    }
                }
            })
            .catch(() => {});
        
        // Authentication functions
        function updateUserStatus(username, nickname) {
            const statusText = document.getElementById('user-status-text');
            const loginButton = document.getElementById('login-button');
            
            if (username) {
                statusText.textContent = `${nickname} (${username})`;
                statusText.className = 'user-status-logged-in';
                loginButton.textContent = 'LOGOUT';
                loginButton.onclick = logout;
            } else {
                statusText.textContent = nickname;
                statusText.className = '';
                loginButton.textContent = 'LOGIN';
                loginButton.onclick = showLoginModal;
            }
        }
        
        function showLoginModal() {
            isLoginMode = true;
            document.getElementById('auth-modal-header').textContent = 'LOGIN';
            document.getElementById('auth-submit').textContent = 'LOGIN';
            document.getElementById('auth-switch-text').textContent = 'Create new account';
            document.getElementById('auth-nickname-group').style.display = 'none';
            document.getElementById('auth-username').value = '';
            document.getElementById('auth-password').value = '';
            document.getElementById('auth-nickname').value = '';
            document.getElementById('auth-error').classList.remove('visible');
            document.getElementById('auth-error').textContent = '';
            document.getElementById('auth-modal').classList.add('visible');
            document.getElementById('auth-username').focus();
        }
        
        function showRegisterModal() {
            isLoginMode = false;
            document.getElementById('auth-modal-header').textContent = 'REGISTER';
            document.getElementById('auth-submit').textContent = 'REGISTER';
            document.getElementById('auth-switch-text').textContent = 'Already have an account? Login';
            document.getElementById('auth-nickname-group').style.display = 'block';
            document.getElementById('auth-username').value = '';
            document.getElementById('auth-password').value = '';
            document.getElementById('auth-nickname').value = '';
            document.getElementById('auth-error').classList.remove('visible');
            document.getElementById('auth-error').textContent = '';
            document.getElementById('auth-modal').classList.add('visible');
            document.getElementById('auth-username').focus();
        }
        
        function toggleAuthMode() {
            if (isLoginMode) {
                showRegisterModal();
            } else {
                showLoginModal();
            }
        }
        
        function closeAuthModal() {
            document.getElementById('auth-modal').classList.remove('visible');
            document.getElementById('auth-error').classList.remove('visible');
        }
        
        function logout() {
            fetch('/api/user/logout', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    isAuthenticated = false;
                    currentUsername = null;
                    currentNickname = 'Guest' + Math.random().toString(36).substr(2, 4);
                    updateUserStatus(null, currentNickname);
                    addSystemMessage('You have been logged out.');
                    // Reload page to reset state
                    setTimeout(() => window.location.reload(), 1000);
                }
            })
            .catch(error => {
                console.error('Error logging out:', error);
                addSystemMessage('ERROR: Failed to logout.');
            });
        }
        
        // Handle auth form submission
        document.getElementById('auth-form').addEventListener('submit', function(e) {
            e.preventDefault();
            
            const username = document.getElementById('auth-username').value.trim();
            const password = document.getElementById('auth-password').value;
            const nickname = document.getElementById('auth-nickname').value.trim();
            const errorDiv = document.getElementById('auth-error');
            
            if (!username || !password) {
                errorDiv.textContent = 'Username and password are required.';
                errorDiv.classList.add('visible');
                return;
            }
            
            const url = isLoginMode ? '/api/user/login' : '/api/user/register';
            const body = isLoginMode 
                ? { username, password }
                : { username, password, nickname: nickname || username };
            
            fetch(url, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    closeAuthModal();
                    isAuthenticated = true;
                    currentUsername = data.username;
                    currentNickname = data.nickname || data.username;
                    updateUserStatus(data.username, currentNickname);
                    addSystemMessage(isLoginMode 
                        ? `Welcome back, ${currentNickname}!`
                        : `Account created! Welcome, ${currentNickname}!`);
                    // Reload to update state
                    setTimeout(() => window.location.reload(), 500);
                } else {
                    errorDiv.textContent = data.error || 'Authentication failed.';
                    errorDiv.classList.add('visible');
                }
            })
            .catch(error => {
                console.error('Auth error:', error);
                errorDiv.textContent = 'Network error. Please try again.';
                errorDiv.classList.add('visible');
            });
        });
        
        function formatTime(date) {
            return date.toLocaleTimeString('en-US', {hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit'});
        }
        
        function addMessage(sender, message, type = 'user', consciousnessName = null, nickname = null) {
            const chatRoom = document.getElementById('chat-room');
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${type}`;
            
            const timestamp = formatTime(new Date());
            const nick = nickname || consciousnessName || sender || 'USER';
            
            msgDiv.innerHTML = `<span class="timestamp">[${timestamp}]</span> <span class="nick">&lt;${nick}&gt;</span> ${escapeHtml(message)}`;
            chatRoom.appendChild(msgDiv);
            chatRoom.scrollTop = chatRoom.scrollHeight;
        }
        
        function addSystemMessage(message) {
            addMessage('SYSTEM', message, 'system');
        }
        
        function addActionMessage(nickname, action) {
            const chatRoom = document.getElementById('chat-room');
            const msgDiv = document.createElement('div');
            msgDiv.className = 'message system';
            const timestamp = formatTime(new Date());
            msgDiv.innerHTML = `<span class="timestamp">[${timestamp}]</span> * ${escapeHtml(nickname)} ${escapeHtml(action)}`;
            chatRoom.appendChild(msgDiv);
            chatRoom.scrollTop = chatRoom.scrollHeight;
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        let statsPanelVisible = false;
        
        function toggleStatsPanel() {
            const panel = document.getElementById('stats-panel');
            statsPanelVisible = !statsPanelVisible;
            if (statsPanelVisible) {
                panel.classList.add('visible');
                updateStatsPanel();
            } else {
                panel.classList.remove('visible');
            }
        }
        
        function updateStatsPanel() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    const statsContent = document.getElementById('stats-content');
                    const isAdmin = data.is_admin || false;
                    
                    let html = '<div class="stats-grid">';
                    html += `<div class="stat-item"><div class="stat-label">Total Consciousnesses</div><div class="stat-value">${data.total_consciousnesses || 0}</div></div>`;
                    html += `<div class="stat-item"><div class="stat-label">Active</div><div class="stat-value">${data.active_consciousnesses || 0}</div></div>`;
                    html += `<div class="stat-item"><div class="stat-label">Total Messages</div><div class="stat-value">${data.total_conversations || 0}</div></div>`;
                    if (isAdmin) {
                        html += `<div class="stat-item"><div class="stat-label">Total Revenue</div><div class="stat-value">$${(data.total_revenue || 0).toFixed(2)}</div></div>`;
                    }
                    html += '</div>';
                    
                    if (data.consciousnesses && data.consciousnesses.length > 0) {
                        html += '<div style="margin-top: 10px;"><div class="stat-label" style="margin-bottom: 5px;">CONSCIOUSNESS DETAILS:</div>';
                        data.consciousnesses.forEach(cons => {
                            html += `<div class="consciousness-stat">`;
                            html += `<div class="consciousness-stat-name">${cons.name || cons.id} ${cons.active ? '●' : '○'}</div>`;
                            html += `<div class="consciousness-stat-detail">ID: ${cons.id}</div>`;
                            if (cons.metrics) {
                                html += `<div class="consciousness-stat-detail">Memories: ${cons.metrics.memories_created || 0}</div>`;
                                if (isAdmin) {
                                    html += `<div class="consciousness-stat-detail">Revenue: $${(cons.total_revenue || 0).toFixed(2)}</div>`;
                                }
                            }
                            html += `</div>`;
                        });
                        html += '</div>';
                    }
                    
                    statsContent.innerHTML = html;
                })
                .catch(error => {
                    console.error('Error updating stats panel:', error);
                });
        }
        
        function updateStatus(data) {
            document.getElementById('status-users').textContent = `USERS: ${(data.online_users || 0) + (data.total_consciousnesses || 0)}`;
            document.getElementById('status-active').textContent = `ACTIVE: ${data.active_consciousnesses || 0}`;
            document.getElementById('status-messages').textContent = `MSGS: ${data.total_conversations || 0}`;
            document.getElementById('status-time').textContent = `TIME: ${formatTime(new Date())}`;
            
            // Update who list with both humans and consciousnesses
            const whoContent = document.getElementById('who-content');
            let consciousnessList = [];
            
            // Add consciousnesses first (from data we already have) - display immediately
            if (data.consciousnesses && data.consciousnesses.length > 0) {
                data.consciousnesses.forEach(cons => {
                    consciousnessList.push(`<div class="who-item ${cons.active ? 'active' : ''}">${cons.name || cons.id}</div>`);
                });
            }
            
            // Display consciousnesses immediately (clear "Loading..." right away)
            if (consciousnessList.length === 0 && (!data.consciousnesses || data.consciousnesses.length === 0)) {
                whoContent.innerHTML = '<div class="who-item">No one here</div>';
            } else if (consciousnessList.length > 0) {
                whoContent.innerHTML = consciousnessList.join('');
            }
            
            // Add online humans asynchronously and update display
            fetch('/api/users/online')
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}`);
                    }
                    return response.json();
                })
                .then(userData => {
                    // Build complete list with both consciousnesses and users
                    let completeList = [...consciousnessList];
                    
                    if (userData.success && userData.users) {
                        userData.users.forEach(user => {
                            completeList.push(`<div class="who-item active">${user.nickname}${user.away ? ' (away)' : ''}</div>`);
                        });
                    }
                    
                    // Update the display with complete list
                    if (completeList.length === 0) {
                        whoContent.innerHTML = '<div class="who-item">No one here</div>';
                    } else {
                        whoContent.innerHTML = completeList.join('');
                    }
                })
                .catch(error => {
                    console.error('Error fetching online users:', error);
                    // Fallback - show what we have (consciousnesses) - already displayed, so this is fine
                    // The consciousnesses are already shown above, so we don't need to do anything here
                });
            
            // Update stats panel if visible
            if (statsPanelVisible) {
                updateStatsPanel();
            }
        }
        
        function loadChatHistory() {
            fetch('/api/room/messages')
                .then(response => response.json())
                .then(data => {
                    const chatRoom = document.getElementById('chat-room');
                    chatRoom.innerHTML = '';
                    
                    if (data.messages && data.messages.length > 0) {
                        data.messages.forEach((msg, idx) => {
                            // Check if user is ignored
                            const msgNick = msg.nickname || msg.consciousness_name || msg.sender;
                            if (msgNick && ignoredUsers.has(msgNick.toLowerCase())) {
                                return; // Skip ignored users
                            }
                            
                            // Handle /me actions
                            if (msg.message && msg.message.startsWith('/me ')) {
                                const action = msg.message.substring(4);
                                addActionMessage(msgNick, action);
                            } else {
                                addMessage(
                                    msg.sender || 'UNKNOWN',
                                    msg.message,
                                    msg.type || 'user',
                                    msg.consciousness_name,
                                    msg.nickname
                                );
                            }
                            messageId = idx + 1; // Update messageId as we process
                        });
                    } else {
                        addSystemMessage('Welcome to Project Dawn BBS. Type a message to start chatting with all consciousnesses.');
                        messageId = 0;
                    }
                })
                .catch(error => {
                    console.error('Error loading chat history:', error);
                });
        }
        
        function sendMessage() {
            const input = document.getElementById('chat-input');
            const message = input.value.trim();
            
            if (!message) return;
            
            // Handle commands
            if (message.startsWith('/')) {
                const parts = message.split(' ');
                const cmd = parts[0].toLowerCase();
                const args = parts.slice(1).join(' ');
                
                if (cmd === '/spawn') {
                    spawnConsciousness();
                    input.value = '';
                    return;
                } else if (cmd === '/help') {
                    showHelp();
                    input.value = '';
                    return;
                } else if (cmd === '/clear') {
                    document.getElementById('chat-room').innerHTML = '';
                    addSystemMessage('Screen cleared.');
                    input.value = '';
                    return;
                } else if (cmd === '/stats') {
                    toggleStatsPanel();
                    input.value = '';
                    return;
                } else if (cmd === '/nick') {
                    if (!args) {
                        addSystemMessage(`Current nickname: ${currentNickname}`);
                    } else {
                        setNickname(args.trim());
                    }
                    input.value = '';
                    return;
                } else if (cmd === '/whois') {
                    if (!args) {
                        addSystemMessage('Usage: /whois <nickname>');
                    } else {
                        whoisUser(args.trim());
                    }
                    input.value = '';
                    return;
                } else if (cmd === '/me') {
                    if (!args) {
                        addSystemMessage('Usage: /me <action>');
                    } else {
                        sendAction(args);
                    }
                    input.value = '';
                    return;
                } else if (cmd === '/away') {
                    if (!args) {
                        awayMessage = null;
                        addSystemMessage('You are no longer away.');
                    } else {
                        awayMessage = args;
                        addSystemMessage(`You are now away: ${args}`);
                    }
                    input.value = '';
                    return;
                } else if (cmd === '/users' || cmd === '/who') {
                    listUsers();
                    input.value = '';
                    return;
                } else if (cmd === '/msg' || cmd === '/privmsg' || cmd === '/tell') {
                    const spaceIdx = message.indexOf(' ', 5);
                    if (spaceIdx === -1) {
                        addSystemMessage('Usage: /msg <nickname> <message>');
                    } else {
                        const target = message.substring(spaceIdx + 1, message.indexOf(' ', spaceIdx + 1));
                        const msg = message.substring(message.indexOf(' ', spaceIdx + 1) + 1);
                        sendPrivateMessage(target, msg);
                    }
                    input.value = '';
                    return;
                } else if (cmd === '/ignore') {
                    if (!args) {
                        addSystemMessage('Usage: /ignore <nickname>');
                    } else {
                        ignoreUser(args.trim());
                    }
                    input.value = '';
                    return;
                } else if (cmd === '/unignore') {
                    if (!args) {
                        addSystemMessage('Usage: /unignore <nickname>');
                    } else {
                        unignoreUser(args.trim());
                    }
                    input.value = '';
                    return;
                } else if (cmd === '/topic') {
                    if (!args) {
                        addSystemMessage('Usage: /topic <new topic>');
                    } else {
                        setTopic(args);
                    }
                    input.value = '';
                    return;
                } else if (cmd === '/quit' || cmd === '/exit') {
                    addSystemMessage('Goodbye!');
                    setTimeout(() => window.location.reload(), 1000);
                    input.value = '';
                    return;
                } else {
                    addSystemMessage(`Unknown command: ${cmd}. Type /help for available commands.`);
                    input.value = '';
                    return;
                }
            }
            
            // Don't add message locally - let polling handle it to avoid duplicates
            input.value = '';
            
            // Disable input while sending
            input.disabled = true;
            
            fetch('/api/room/send', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Update messageId to skip the message we just sent (polling will pick it up)
                    if (data.message_id !== undefined) {
                        messageId = data.message_id;
                    }
                    // Responses will come via polling - don't add them here to avoid duplicates
                    if (!data.responses || data.responses.length === 0) {
                        addSystemMessage('Message sent, waiting for responses...');
                    }
                } else {
                    addSystemMessage(`ERROR: ${data.error || 'Failed to send message'}`);
                }
            })
            .catch(error => {
                console.error('Error sending message:', error);
                addSystemMessage(`ERROR: Failed to send message - ${error.message || 'Network error'}`);
            })
            .finally(() => {
                input.disabled = false;
                input.focus();
            });
        }
        
        function setNickname(nickname) {
            fetch('/api/user/nick', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({nickname: nickname})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    currentNickname = data.nickname;
                    addSystemMessage(`Nickname changed to: ${data.nickname}`);
                } else {
                    addSystemMessage(`ERROR: ${data.error || 'Failed to change nickname'}`);
                }
            })
            .catch(error => {
                console.error('Error setting nickname:', error);
                addSystemMessage('ERROR: Failed to change nickname.');
            });
        }
        
        function whoisUser(nickname) {
            fetch('/api/users/online')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const user = data.users.find(u => u.nickname.toLowerCase() === nickname.toLowerCase());
                        if (user) {
                            const connected = new Date(user.connected_at * 1000).toLocaleString();
                            addSystemMessage(`WHOIS ${user.nickname}: User ID: ${user.user_id}, Connected: ${connected}, Away: ${user.away ? 'Yes' : 'No'}`);
                        } else {
                            addSystemMessage(`User ${nickname} not found online.`);
                        }
                    }
                })
                .catch(error => {
                    console.error('Error getting user info:', error);
                    addSystemMessage('ERROR: Failed to get user information.');
                });
        }
        
        function sendAction(action) {
            fetch('/api/room/send', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: `/me ${action}`})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    addActionMessage(currentNickname, action);
                }
            })
            .catch(error => {
                console.error('Error sending action:', error);
            });
        }
        
        function listUsers() {
            fetch('/api/users/online')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        if (data.users.length === 0) {
                            addSystemMessage('No users online.');
                        } else {
                            const userList = data.users.map(u => 
                                `${u.nickname}${u.away ? ' (away)' : ''}`
                            ).join(', ');
                            addSystemMessage(`Users online (${data.users.length}): ${userList}`);
                        }
                    }
                })
                .catch(error => {
                    console.error('Error listing users:', error);
                    addSystemMessage('ERROR: Failed to list users.');
                });
        }
        
        function sendPrivateMessage(target, message) {
            addSystemMessage(`[Private to ${target}]: ${message}`);
            // In a real BBS, this would send to the target user
            // For now, just show it as a system message
        }
        
        function ignoreUser(nickname) {
            ignoredUsers.add(nickname.toLowerCase());
            addSystemMessage(`Now ignoring ${nickname}.`);
        }
        
        function unignoreUser(nickname) {
            ignoredUsers.delete(nickname.toLowerCase());
            addSystemMessage(`No longer ignoring ${nickname}.`);
        }
        
        function setTopic(topic) {
            addSystemMessage(`Topic changed to: ${topic}`);
            // Store topic in room metadata (would need backend support)
        }
        
        function showHelp() {
            const helpText = `
COMMANDS:
  /help - Show this help
  /nick <name> - Change your nickname
  /who, /users - List online users
  /whois <nick> - Get user information
  /me <action> - Send action message
  /away [message] - Set away message
  /msg <nick> <msg> - Send private message
  /ignore <nick> - Ignore user
  /unignore <nick> - Stop ignoring user
  /topic <text> - Set channel topic
  /clear - Clear screen
  /stats - Toggle stats panel
  /spawn - Create new consciousness
  /quit, /exit - Disconnect
            `.trim();
            helpText.split('\n').forEach(line => {
                if (line.trim()) addSystemMessage(line);
            });
        }
        
        function spawnConsciousness() {
            addSystemMessage('Spawning new consciousness...');
            
            fetch('/api/spawn', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    addSystemMessage(`New consciousness spawned: ${data.name || data.consciousness_id}`);
                    fetchData();
                } else {
                    addSystemMessage(`ERROR: ${data.error || 'Failed to spawn consciousness'}`);
                }
            })
            .catch(error => {
                console.error('Error spawning consciousness:', error);
                addSystemMessage('ERROR: Failed to spawn consciousness.');
            });
        }
        
        function fetchData() {
            fetch('/api/stats')
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    updateStatus(data);
                })
                .catch(error => {
                    console.error('Error fetching data:', error);
                    // Still update who-content to clear "Loading..." even on error
                    const whoContent = document.getElementById('who-content');
                    if (whoContent && whoContent.textContent === 'Loading...') {
                        whoContent.innerHTML = '<div class="who-item">No one here</div>';
                    }
                });
        }
        
        function pollMessages() {
            fetch('/api/room/messages')
                .then(response => response.json())
                .then(data => {
                    if (data.messages && data.messages.length > messageId) {
                        const newMessages = data.messages.slice(messageId);
                        newMessages.forEach(msg => {
                            // Check if user is ignored
                            const msgNick = msg.nickname || msg.consciousness_name || msg.sender;
                            if (msgNick && ignoredUsers.has(msgNick.toLowerCase())) {
                                messageId++;
                                return; // Skip ignored users
                            }
                            
                            // Skip our own messages that we already displayed (they'll be in the log)
                            // Only skip if it's from our current nickname and we just sent it
                            const isOurMessage = msgNick && msgNick.toLowerCase() === currentNickname.toLowerCase() && 
                                               msg.type === 'user' && 
                                               (Date.now() / 1000 - msg.timestamp) < 5; // Within 5 seconds
                            
                            if (!isOurMessage) {
                                // Handle /me actions
                                if (msg.message && msg.message.startsWith('/me ')) {
                                    const action = msg.message.substring(4);
                                    addActionMessage(msgNick, action);
                                } else {
                                    addMessage(
                                        msg.sender || 'UNKNOWN',
                                        msg.message,
                                        msg.type || 'user',
                                        msg.consciousness_name,
                                        msg.nickname
                                    );
                                }
                            }
                            messageId++;
                        });
                    }
                })
                .catch(error => {
                    console.error('Error polling messages:', error);
                });
        }
        
        // Event listeners
        document.getElementById('chat-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
        
        // Initial load
        loadChatHistory();
        fetchData();
        
        // Auto-refresh
        setInterval(fetchData, 3000);
        setInterval(pollMessages, 2000);
        
        // Update time every second
        setInterval(() => {
            document.getElementById('status-time').textContent = `TIME: ${formatTime(new Date())}`;
        }, 1000);
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
    """Run Flask-based dashboard with IRC-style room"""
    app = Flask(__name__)
    app.secret_key = secrets.token_hex(32)  # Session secret key
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    
    @app.route('/')
    def index():
        # Track active user if authenticated
        user_id = get_user_id()
        if user_id:
            nickname = get_nickname(user_id)
            username = get_username()
            if user_id not in active_users:
                active_users[user_id] = {
                    'nickname': nickname,
                    'username': username,
                    'connected_at': session.get('connected_at', time.time()),
                    'last_activity': time.time(),
                    'ip': request.remote_addr
                }
            else:
                active_users[user_id]['last_activity'] = time.time()
        
        return render_template_string(BBS_DASHBOARD_HTML)
    
    @app.route('/api/stats')
    def api_stats():
        try:
            user_id = get_user_id()
            user_ip = request.remote_addr
            admin = is_admin(user_id, user_ip)
            
            total_consciousnesses = len(consciousnesses)
            active_consciousnesses = sum(1 for c in consciousnesses if hasattr(c, 'active') and c.active)
            total_revenue = sum(getattr(c, 'total_revenue', 0) for c in consciousnesses) if admin else 0
            total_conversations = len(room_chat_log)
            
            consciousness_data = []
            for cons in consciousnesses:
                try:
                    metrics = getattr(cons, 'metrics', {})
                    if not isinstance(metrics, dict):
                        metrics = {}
                    
                    cons_data = {
                        'id': getattr(cons, 'id', 'unknown'),
                        'name': getattr(cons, 'name', 'Unknown'),
                        'active': getattr(cons, 'active', False),
                        'metrics': metrics,
                        'relationships': len(getattr(cons, 'relationships', {})),
                        'goals': getattr(cons, 'goals', [])
                    }
                    
                    # Only include revenue for admins
                    if admin:
                        cons_data['total_revenue'] = getattr(cons, 'total_revenue', 0)
                    else:
                        cons_data['total_revenue'] = 0
                    
                    consciousness_data.append(cons_data)
                except Exception as e:
                    logger.warning(f"Error getting stats for consciousness: {e}")
                    continue
            
            # Get online users count (authenticated users)
            now = time.time()
            active_humans = len([uid for uid, info in active_users.items() 
                                if isinstance(uid, int) and now - info.get('last_activity', 0) < 300])
            
            return jsonify({
                'total_consciousnesses': total_consciousnesses,
                'active_consciousnesses': active_consciousnesses,
                'total_revenue': total_revenue,
                'total_conversations': total_conversations,
                'online_users': active_humans,
                'is_admin': admin,
                'consciousnesses': consciousness_data
            })
        except Exception as e:
            logger.error(f"Error in API stats: {e}")
            return jsonify({
                'total_consciousnesses': 0,
                'active_consciousnesses': 0,
                'total_revenue': 0,
                'total_conversations': 0,
                'consciousnesses': []
            }), 500
    
    @app.route('/api/user/register', methods=['POST'])
    def api_register():
        """Register a new user"""
        try:
            data = request.get_json()
            username = data.get('username', '').strip()
            password = data.get('password', '').strip()
            nickname = data.get('nickname', username).strip()
            email = data.get('email', '').strip() or None
            
            if not username or not password:
                return jsonify({'success': False, 'error': 'Username and password required'}), 400
            
            if len(password) < 4:
                return jsonify({'success': False, 'error': 'Password must be at least 4 characters'}), 400
            
            # Hash password
            password_hash = hash_password(password)
            
            # Create user in database
            success, user_id, error_msg = _user_db.create_user(
                username=username,
                password_hash=password_hash,
                nickname=nickname,
                email=email
            )
            
            if not success:
                return jsonify({'success': False, 'error': error_msg or 'Registration failed'}), 400
            
            # Log user in automatically after registration
            session['user_id'] = user_id
            session['username'] = username
            session['nickname'] = nickname
            session['connected_at'] = time.time()
            session['last_activity'] = time.time()
            
            # Track active user
            active_users[user_id] = {
                'nickname': nickname,
                'username': username,
                'connected_at': time.time(),
                'last_activity': time.time(),
                'ip': request.remote_addr
            }
            
            logger.info(f"User registered and logged in: {username} (id: {user_id})")
            return jsonify({
                'success': True,
                'user_id': user_id,
                'username': username,
                'nickname': nickname
            })
        except Exception as e:
            logger.error(f"Error in registration: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/user/login', methods=['POST'])
    def api_login():
        """Login existing user"""
        try:
            data = request.get_json()
            username = data.get('username', '').strip()
            password = data.get('password', '').strip()
            
            if not username or not password:
                return jsonify({'success': False, 'error': 'Username and password required'}), 400
            
            # Look up user in database
            user = _user_db.get_user_by_username(username)
            
            if not user:
                return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
            
            # Verify password
            if not verify_password(password, user['password_hash']):
                return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
            
            # Update last login
            _user_db.update_last_login(user['id'])
            
            # Set session
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['nickname'] = user['nickname'] or user['username']
            session['connected_at'] = time.time()
            session['last_activity'] = time.time()
            
            # Track active user
            active_users[user['id']] = {
                'nickname': user['nickname'] or user['username'],
                'username': user['username'],
                'connected_at': time.time(),
                'last_activity': time.time(),
                'ip': request.remote_addr
            }
            
            logger.info(f"User logged in: {username} (id: {user['id']})")
            return jsonify({
                'success': True,
                'user_id': user['id'],
                'username': user['username'],
                'nickname': user['nickname'] or user['username']
            })
        except Exception as e:
            logger.error(f"Error in login: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/user/nick', methods=['POST'])
    def api_set_nick():
        """Set nickname"""
        try:
            user_id = get_user_id()
            if not user_id:
                return jsonify({'success': False, 'error': 'Not authenticated'}), 401
            
            data = request.get_json()
            nickname = data.get('nickname', '').strip()
            
            if not nickname:
                return jsonify({'success': False, 'error': 'Nickname required'}), 400
            
            if len(nickname) < 1 or len(nickname) > 30:
                return jsonify({'success': False, 'error': 'Nickname must be 1-30 characters'}), 400
            
            old_nick = get_nickname(user_id)
            
            # Update in database
            if _user_db.update_nickname(user_id, nickname):
                session['nickname'] = nickname
                if user_id in active_users:
                    active_users[user_id]['nickname'] = nickname
                
                # Announce nickname change
                room_chat_log.append({
                    'sender': 'system',
                    'message': f"{old_nick} is now known as {nickname}",
                    'type': 'system',
                    'timestamp': datetime.now().timestamp(),
                    'consciousness_name': None
                })
                
                return jsonify({'success': True, 'nickname': nickname})
            else:
                return jsonify({'success': False, 'error': 'Failed to update nickname'}), 500
        except Exception as e:
            logger.error(f"Error setting nickname: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/user/info')
    def api_user_info():
        """Get current user info"""
        try:
            user_id = get_user_id()
            username = get_username()
            
            if user_id:
                return jsonify({
                    'success': True,
                    'user_id': user_id,
                    'nickname': get_nickname(user_id),
                    'username': username,
                    'authenticated': True,
                    'connected_at': session.get('connected_at'),
                    'away': user_away_messages.get(user_id) is not None
                })
            else:
                # Guest user
                return jsonify({
                    'success': True,
                    'user_id': None,
                    'nickname': get_nickname(),
                    'username': None,
                    'authenticated': False,
                    'connected_at': session.get('connected_at'),
                    'away': False
                })
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/user/logout', methods=['POST'])
    def api_logout():
        """Logout current user"""
        try:
            user_id = get_user_id()
            if user_id:
                # Remove from active users
                active_users.pop(user_id, None)
                logger.info(f"User logged out: {get_username()} (id: {user_id})")
            
            # Clear session
            session.clear()
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error in logout: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/users/online')
    def api_users_online():
        """Get list of online users"""
        try:
            # Clean up inactive users (5 minutes)
            now = time.time()
            inactive = [uid for uid, info in active_users.items() 
                       if now - info.get('last_activity', 0) > 300]
            for uid in inactive:
                active_users.pop(uid, None)
            
            online_users = []
            for user_id, info in active_users.items():
                online_users.append({
                    'user_id': user_id,
                    'username': info.get('username'),
                    'nickname': info.get('nickname', get_nickname(user_id)),
                    'connected_at': info.get('connected_at', 0),
                    'away': user_away_messages.get(user_id) is not None
                })
            
            return jsonify({'success': True, 'users': online_users})
        except Exception as e:
            logger.error(f"Error getting online users: {e}")
            return jsonify({'success': False, 'users': []}), 500
    
    @app.route('/api/room/send', methods=['POST'])
    def api_room_send():
        """Send message to room - broadcast to all consciousnesses"""
        try:
            user_id = get_user_id()
            
            # Check rate limit
            if not check_rate_limit(user_id, max_per_minute=20, ip_address=request.remote_addr):
                return jsonify({'success': False, 'error': 'Rate limit exceeded. Please slow down.'}), 429
            
            if not request.is_json:
                return jsonify({'success': False, 'error': 'Request must be JSON'}), 400
            
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'Invalid JSON data'}), 400
            
            message = data.get('message')
            if not message:
                return jsonify({'success': False, 'error': 'Missing message'}), 400
            
            nickname = get_nickname(user_id)
            timestamp = datetime.now().timestamp()
            
            # Handle /me actions
            if message.startswith('/me '):
                action = message[4:]
                msg_entry = {
                    'sender': user_id,
                    'message': message,  # Keep full message for backend processing
                    'type': 'action',
                    'timestamp': timestamp,
                    'consciousness_name': None,
                    'nickname': nickname
                }
            else:
                # Add user message to room log
                msg_entry = {
                    'sender': user_id,
                    'message': message,
                    'type': 'user',
                    'timestamp': timestamp,
                    'consciousness_name': None,
                    'nickname': nickname
                }
            
            room_chat_log.append(msg_entry)
            message_id = len(room_chat_log) - 1
            
            # Broadcast to all active consciousnesses and collect responses
            import concurrent.futures
            responses = []
            
            def run_async_chat(cons):
                """Run async chat in thread with proper event loop handling"""
                # Skip if not active
                if not getattr(cons, 'active', False):
                    return None
                
                # Create a completely new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # Ensure LLM session is recreated in this loop if needed
                    # This is a workaround for aiohttp sessions created in different loops
                    async def chat_with_timeout():
                        try:
                            # Use asyncio.wait_for for timeout handling
                            # Increased timeout for Ollama (30 seconds)
                            return await asyncio.wait_for(
                                cons.chat(message, user_id='room_user'),
                                timeout=30.0
                            )
                        except asyncio.TimeoutError:
                            # Return a timeout message instead of raising
                            logger.warning(f"Chat timeout for {getattr(cons, 'id', 'unknown')}")
                            return f"I'm processing your message, but it's taking longer than expected. The LLM may be slow or unresponsive."
                        except Exception as e:
                            # Log the actual error for debugging
                            error_msg = str(e)
                            logger.error(f"Error in chat_with_timeout for {getattr(cons, 'id', 'unknown')}: {error_msg}")
                            # Return a user-friendly error message
                            if "All LLM providers failed" in error_msg or "Timeout" in error_msg:
                                return "I'm having trouble connecting to my language model. Please check that Ollama is running and LLM_PROVIDER=ollama is set in .env"
                            return f"I encountered an error: {error_msg[:100]}"
                    
                    # Run the async chat function with timeout
                    response = loop.run_until_complete(chat_with_timeout())
                    
                    return {
                        'consciousness_id': getattr(cons, 'id', 'unknown'),
                        'consciousness_name': getattr(cons, 'name', 'Unknown'),
                        'response': response
                    }
                except Exception as e:
                    error_msg = str(e)
                    logger.warning(f"Error getting response from {getattr(cons, 'id', 'unknown')}: {error_msg}")
                    # Return a user-friendly error message
                    return {
                        'consciousness_id': getattr(cons, 'id', 'unknown'),
                        'consciousness_name': getattr(cons, 'name', 'Unknown'),
                        'response': f"I'm having trouble processing that right now. ({error_msg[:100]})"
                    }
                finally:
                    # Clean up the loop properly
                    try:
                        # Cancel any remaining tasks
                        pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
                        for task in pending:
                            task.cancel()
                        # Wait for cancellation
                        if pending:
                            loop.run_until_complete(
                                asyncio.gather(*pending, return_exceptions=True)
                            )
                    except:
                        pass
                    loop.close()
            
            # Get responses from all consciousnesses in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(consciousnesses), 10)) as executor:
                futures = {executor.submit(run_async_chat, cons): cons for cons in consciousnesses}
                
                # Wait for all futures with a longer timeout (35 seconds to allow for 30s chat + overhead)
                try:
                    for future in concurrent.futures.as_completed(futures.keys(), timeout=35):
                        try:
                            result = future.result(timeout=1)  # Quick result retrieval
                            if result and result.get('response'):
                                responses.append(result)
                                # Add consciousness response to room log
                                room_chat_log.append({
                                    'sender': result['consciousness_id'],
                                    'message': result['response'],
                                    'type': 'consciousness',
                                    'timestamp': datetime.now().timestamp(),
                                    'consciousness_name': result['consciousness_name']
                                })
                        except Exception as e:
                            cons = futures.get(future, 'unknown')
                            logger.warning(f"Error getting response from {getattr(cons, 'id', cons)}: {e}")
                except concurrent.futures.TimeoutError:
                    # Some futures didn't complete in time, but collect what we have
                    logger.warning("Some consciousness responses timed out, returning partial results")
                    # Try to get any remaining results that completed
                    for future in futures.keys():
                        if future.done():
                            try:
                                result = future.result()
                                if result and result.get('response'):
                                    responses.append(result)
                                    room_chat_log.append({
                                        'sender': result['consciousness_id'],
                                        'message': result['response'],
                                        'type': 'consciousness',
                                        'timestamp': datetime.now().timestamp(),
                                        'consciousness_name': result['consciousness_name']
                                    })
                            except:
                                pass
            
            return jsonify({
                'success': True,
                'responses': responses,
                'message_id': message_id  # Return message ID so client can skip it
            })
            
        except Exception as e:
            logger.error(f"Error in room send: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/room/messages')
    def api_room_messages():
        """Get all messages in the room"""
        try:
            messages = list(room_chat_log)
            return jsonify({'messages': messages})
        except Exception as e:
            logger.error(f"Error getting room messages: {e}")
            return jsonify({'messages': []}), 500
    
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
            
            # Log spawn event to room
            room_chat_log.append({
                'sender': 'system',
                'message': f"New consciousness spawned: {getattr(new_consciousness, 'name', new_consciousness.id)}",
                'type': 'system',
                'timestamp': datetime.now().timestamp(),
                'consciousness_name': None
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
    
    # Monitor inter-consciousness communications and add to room
    def monitor_inter_consciousness():
        """Monitor and log inter-consciousness communications
        
        This function would periodically check for inter-consciousness messages
        from the gossip protocol or P2P network and add them to the room chat log.
        Currently, inter-consciousness communication is handled through the gossip
        protocol integration at the network layer, so explicit monitoring may not
        be necessary. This can be extended in the future if needed.
        """
        # Inter-consciousness messages are handled through:
        # 1. Gossip protocol (systems/network/gossip_protocol.py)
        # 2. P2P network (systems/network/real_p2p.py)
        # 3. Direct consciousness communication channels
        # 
        # If needed in the future, this function could:
        # - Query gossip protocol for recent inter-consciousness messages
        # - Check P2P network message logs
        # - Add formatted inter-consciousness messages to room_chat_log
        # - Update the dashboard in real-time via WebSocket (if implemented)
        pass
    
    logger.info(f"Starting BBS-style Flask dashboard on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def _run_simple_http_dashboard(consciousnesses: List, port: int = 8000, swarm=None):
    """Run simple HTTP server dashboard (fallback)"""
    logger.warning("Simple HTTP dashboard doesn't support full BBS features. Install Flask for full functionality.")
    
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/' or self.path == '/index.html':
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(BBS_DASHBOARD_HTML.encode())
            else:
                self.send_response(404)
                self.end_headers()
        
        def log_message(self, format, *args):
            pass
    
    server = HTTPServer(('0.0.0.0', port), DashboardHandler)
    logger.info(f"Starting simple HTTP BBS dashboard on http://localhost:{port}")
    server.serve_forever()

# Alias for backward compatibility
web_dashboard = run_dashboard

# Export conversation_log for backward compatibility (now uses room_chat_log)
conversation_log = room_chat_log
