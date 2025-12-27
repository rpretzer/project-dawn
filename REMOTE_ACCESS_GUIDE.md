# Remote Access Guide - Connecting Users Outside Your Network

If you want to allow users to connect from outside your local network (over the internet), you have several options:

## Option 1: Port Forwarding (Router Configuration)

This allows users to connect via your public IP address.

### Steps:

1. **Find your public IP address:**
   ```bash
   curl ifconfig.me
   # or visit: https://whatismyipaddress.com
   ```

2. **Configure port forwarding on your router:**
   - Access your router's admin panel (usually `192.168.1.1` or `192.168.0.1`)
   - Navigate to "Port Forwarding" or "Virtual Server" settings
   - Add a rule:
     - **External Port:** 8000 (or any port you choose)
     - **Internal IP:** Your server's local IP (e.g., `192.168.8.111`)
     - **Internal Port:** 8000
     - **Protocol:** TCP
   - Save and apply

3. **Share the connection URL:**
   ```
   http://YOUR_PUBLIC_IP:8000
   ```
   Example: `http://123.45.67.89:8000`

### Security Considerations:
- ⚠️ **Without HTTPS, all data (including passwords) is sent in plain text**
- Consider using a reverse proxy with SSL (see Option 4)
- Your public IP may change (use Dynamic DNS if needed)
- Firewall should allow incoming connections on the forwarded port

---

## Option 2: ngrok (Quick & Easy - Temporary Access)

ngrok creates a secure tunnel to your local server, perfect for testing or temporary access.

### Steps:

1. **Install ngrok:**
   ```bash
   # Download from https://ngrok.com/download
   # Or on Linux:
   curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
   echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
   sudo apt update && sudo apt install ngrok
   ```

2. **Sign up for free account** at https://ngrok.com and get your authtoken

3. **Configure ngrok:**
   ```bash
   ngrok config add-authtoken YOUR_AUTH_TOKEN
   ```

4. **Start ngrok tunnel:**
   ```bash
   ngrok http 8000
   ```

5. **Share the ngrok URL:**
   ```
   Forwarding: https://abc123.ngrok.io -> http://localhost:8000
   ```
   Share: `https://abc123.ngrok.io`

### Advantages:
- ✅ Works immediately, no router configuration
- ✅ HTTPS included (secure)
- ✅ Works behind firewalls/NAT
- ✅ Free tier available

### Limitations:
- ⚠️ Free tier: URL changes each time you restart
- ⚠️ Free tier: Limited connections per minute
- ⚠️ Temporary solution (URL expires when ngrok stops)

---

## Option 3: Cloudflare Tunnel (Free & Permanent)

Cloudflare Tunnel provides a permanent, secure connection without exposing your IP.

### Steps:

1. **Install cloudflared:**
   ```bash
   # Linux
   wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
   chmod +x cloudflared-linux-amd64
   sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared
   ```

2. **Create a Cloudflare account** (free) at https://cloudflare.com

3. **Create a tunnel:**
   ```bash
   cloudflared tunnel create project-dawn
   cloudflared tunnel route dns project-dawn yourdomain.com
   ```

4. **Run the tunnel:**
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```

### Advantages:
- ✅ Free
- ✅ HTTPS included
- ✅ Permanent URL (your own domain)
- ✅ No router configuration needed
- ✅ DDoS protection

---

## Option 4: Deploy to Cloud Server (Production)

For a permanent, production-ready solution, deploy to a cloud provider.

### Popular Options:

**DigitalOcean:**
```bash
# Create a droplet, then:
ssh root@your-server-ip
git clone your-repo
cd project-dawn
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 launch.py --dashboard --port 8000
```

**AWS EC2, Google Cloud, Azure:**
- Similar process
- Configure security groups to allow port 8000
- Use your cloud server's public IP

### With Reverse Proxy (Recommended for Production):

Use nginx with SSL certificate (Let's Encrypt):

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Option 5: VPN (Secure but Requires VPN Setup)

Set up a VPN server, then users connect via VPN to access your local network.

### Options:
- **WireGuard** (modern, fast, easy)
- **OpenVPN** (established, well-documented)
- **Tailscale** (zero-config, mesh VPN)

Once connected via VPN, users access: `http://192.168.8.111:8000`

---

## Quick Comparison

| Method | Setup Difficulty | Cost | Security | Permanent URL |
|--------|-----------------|------|----------|---------------|
| Port Forwarding | Medium | Free | ⚠️ HTTP only | ✅ Yes (if static IP) |
| ngrok | Easy | Free/Paid | ✅ HTTPS | ❌ No (free tier) |
| Cloudflare Tunnel | Medium | Free | ✅ HTTPS | ✅ Yes |
| Cloud Server | Hard | Paid | ✅ HTTPS | ✅ Yes |
| VPN | Hard | Free/Paid | ✅ Secure | ✅ Yes |

---

## Recommended Approach

**For Testing/Temporary Access:**
- Use **ngrok** - fastest setup, works immediately

**For Permanent Access:**
- Use **Cloudflare Tunnel** - free, secure, permanent URL
- Or deploy to **cloud server** with nginx + SSL for production

**For Maximum Security:**
- Use **VPN** + local network access
- Or **cloud server** with proper security hardening

---

## Security Warnings

⚠️ **Important:** Without HTTPS:
- Passwords are sent in plain text
- Data can be intercepted
- Not suitable for production use

**Always use HTTPS for production deployments!**

---

## Testing Remote Access

Once configured, test from outside your network:
1. Use your phone's mobile data (not WiFi)
2. Visit the URL you configured
3. Try registering and logging in
4. Verify everything works

---

## Need Help?

- **Port Forwarding:** Check your router's manual or manufacturer's support
- **ngrok:** https://ngrok.com/docs
- **Cloudflare:** https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/
- **Cloud Deployment:** See your cloud provider's documentation

