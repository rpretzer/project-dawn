# Quick Connection Guide

## For Server Administrators

**Start the server:**
```bash
python3 launch.py --dashboard --port 8000
```

**Find your IP address:**
- Linux/Mac: `hostname -I` or `ip addr show`
- Windows: `ipconfig`

**Share this URL with users:**
```
http://YOUR_IP_ADDRESS:8000
```

**Example:**
```
http://192.168.1.100:8000
```

**Firewall (if needed):**
```bash
# Linux (ufw)
sudo ufw allow 8000/tcp

# Linux (firewalld)
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --reload
```

---

## For Users Connecting

1. **Open the URL** provided by the administrator in your web browser

2. **Click "LOGIN"** button (top-right)

3. **To register (first time):**
   - Click "Create new account"
   - Enter username, password, and optional nickname
   - Click "REGISTER"

4. **To login (returning users):**
   - Enter username and password
   - Click "LOGIN"

5. **Start chatting!**
   - Type messages in the input box
   - Use `/help` for commands

---

## Example Connection URLs

**Local network examples:**
- `http://192.168.1.100:8000`
- `http://10.0.0.5:8000`
- `http://192.168.8.111:8000`

**Custom port:**
- `http://192.168.1.100:8080` (if server uses port 8080)

**Domain name (if configured):**
- `http://dawn.example.com:8000`

---

## Troubleshooting

**"Connection Refused":**
- Check the URL is correct
- Verify server is running
- Check firewall settings

**"Username already exists":**
- Choose a different username

**Can't login:**
- Check username/password are correct
- Username is case-insensitive
- Password is case-sensitive

For more details, see **CONNECTION_INSTRUCTIONS.md**

