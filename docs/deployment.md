# Production Deployment Guide

This guide provides step-by-step instructions for deploying Project Dawn in production environments.

---

## Prerequisites

- Python 3.10+ or Docker
- Network access (ports 8000, 8080, 9090)
- Storage space for data directory (recommended: 1GB+)
- Optional: Prometheus for metrics scraping

---

## Deployment Methods

### Method 1: Docker (Recommended)

**Easiest and most reliable deployment method.**

#### Quick Start

```bash
# Clone repository
git clone <repository-url>
cd project-dawn

# Start with docker-compose
docker-compose up -d

# Check logs
docker-compose logs -f

# Check health
curl http://localhost:9090/health
```

#### Custom Configuration

1. **Edit docker-compose.yml**:
   ```yaml
   services:
     dawn:
       environment:
         - PROJECT_DAWN_DATA_ROOT=/data
         - LOG_LEVEL=INFO
         - LOG_FORMAT=json
         - PROJECT_DAWN_METRICS_PORT=9090
   ```

2. **Start services**:
   ```bash
   docker-compose up -d
   ```

3. **View logs**:
   ```bash
   docker-compose logs -f dawn
   ```

#### Building Custom Image

```bash
# Build image
docker build -t project-dawn:latest .

# Run container
docker run -d \
  --name project-dawn \
  -p 8000:8000 \
  -p 8080:8080 \
  -p 9090:9090 \
  -v ./data:/data \
  -e PROJECT_DAWN_DATA_ROOT=/data \
  -e LOG_LEVEL=INFO \
  project-dawn:latest
```

---

### Method 2: Native Python

#### Installation

```bash
# Clone repository
git clone <repository-url>
cd project-dawn

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install PyYAML for config support (optional)
pip install pyyaml
```

#### Configuration

1. **Create config file** (optional):
   ```bash
   cp config/default.yaml ~/.project-dawn/config.yaml
   # Edit config.yaml as needed
   ```

2. **Set environment variables**:
   ```bash
   export PROJECT_DAWN_DATA_ROOT=~/.project-dawn
   export LOG_LEVEL=INFO
   export LOG_FORMAT=json
   export PROJECT_DAWN_METRICS_PORT=9090
   ```

#### Run

```bash
# Start server
python -m server_p2p

# Or run in background
nohup python -m server_p2p > server.log 2>&1 &
```

---

## Configuration

### Configuration File

Create `~/.project-dawn/config.yaml` (or set `PROJECT_DAWN_DATA_ROOT` to custom location):

```yaml
node:
  identity_path: ~/.project-dawn/vault/node_identity.key
  address: ws://0.0.0.0:8000
  data_root: ~/.project-dawn

security:
  trust_level_default: UNKNOWN
  reject_unknown: false
  audit_log_path: ~/.project-dawn/vault/audit.log

logging:
  level: INFO
  format: json
  file: ~/.project-dawn/logs/dawn.log

observability:
  metrics_port: 9090
  enable_tracing: false
```

### Environment Variables

All configuration can be overridden via environment variables:

```bash
# Node configuration
PROJECT_DAWN_DATA_ROOT=/data
PROJECT_DAWN_HOST=0.0.0.0
PROJECT_DAWN_WS_PORT=8000
PROJECT_DAWN_HTTP_PORT=8080

# Security
PROJECT_DAWN_TRUST_LEVEL=UNKNOWN
PROJECT_DAWN_REJECT_UNKNOWN=false

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Observability
PROJECT_DAWN_METRICS_PORT=9090
```

---

## Service Management

### Systemd Service (Linux)

Create `/etc/systemd/system/project-dawn.service`:

```ini
[Unit]
Description=Project Dawn P2P Node
After=network.target

[Service]
Type=simple
User=dawn
WorkingDirectory=/opt/project-dawn
Environment="PROJECT_DAWN_DATA_ROOT=/var/lib/project-dawn"
Environment="LOG_LEVEL=INFO"
Environment="LOG_FORMAT=json"
ExecStart=/usr/bin/python3 -m server_p2p
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start service**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable project-dawn
sudo systemctl start project-dawn
sudo systemctl status project-dawn
```

### Supervisor (Process Manager)

Create `/etc/supervisor/conf.d/project-dawn.conf`:

```ini
[program:project-dawn]
command=/opt/project-dawn/venv/bin/python -m server_p2p
directory=/opt/project-dawn
user=dawn
autostart=true
autorestart=true
stderr_logfile=/var/log/project-dawn/error.log
stdout_logfile=/var/log/project-dawn/access.log
environment=PROJECT_DAWN_DATA_ROOT="/var/lib/project-dawn",LOG_LEVEL="INFO",LOG_FORMAT="json"
```

**Start service**:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start project-dawn
```

---

## Monitoring Setup

### Prometheus Configuration

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'project-dawn'
    static_configs:
      - targets: ['localhost:9090']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

### Health Checks

Use health endpoints for load balancers and orchestrators:

```bash
# Kubernetes liveness probe
curl http://localhost:9090/health/live

# Kubernetes readiness probe
curl http://localhost:9090/health/ready

# Overall health
curl http://localhost:9090/health
```

---

## Network Configuration

### Ports

- **8000**: WebSocket server (P2P connections)
- **8080**: Frontend HTTP server
- **9090**: Metrics and health endpoints

### Firewall Rules

```bash
# Allow WebSocket connections
sudo ufw allow 8000/tcp

# Allow frontend access
sudo ufw allow 8080/tcp

# Allow metrics (internal only)
sudo ufw allow from 10.0.0.0/8 to any port 9090
```

---

## Data Management

### Data Directory Structure

```
~/.project-dawn/
├── vault/
│   ├── node_identity.key      # Node identity (private key)
│   ├── trust.json             # Trust records
│   ├── audit.log              # Audit log
│   └── master_key             # Encryption master key (if using encryption at rest)
├── mesh/
│   └── trust.json             # Trust records (if not using vault)
└── logs/
    └── dawn.log               # Application logs
```

### Backup

```bash
# Backup data directory
tar -czf project-dawn-backup-$(date +%Y%m%d).tar.gz ~/.project-dawn/

# Or with Docker
docker exec project-dawn tar -czf /backup/data.tar.gz /data
```

### Permissions

```bash
# Set proper permissions
chmod 700 ~/.project-dawn/vault
chmod 600 ~/.project-dawn/vault/*.key
chmod 600 ~/.project-dawn/vault/trust.json
```

---

## Scaling

### Horizontal Scaling

Project Dawn is designed for P2P operation. Multiple nodes can run independently:

```bash
# Node 1
PROJECT_DAWN_WS_PORT=8000 docker-compose up -d

# Node 2
PROJECT_DAWN_WS_PORT=8001 docker-compose up -d

# Node 3
PROJECT_DAWN_WS_PORT=8002 docker-compose up -d
```

### Load Balancing

Use a reverse proxy (nginx, traefik) for frontend access:

```nginx
upstream project_dawn {
    server localhost:8080;
    server localhost:8081;
    server localhost:8082;
}

server {
    listen 80;
    server_name project-dawn.example.com;
    
    location / {
        proxy_pass http://project_dawn;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Security Hardening

### Production Checklist

- [ ] Enable encryption at rest for sensitive data
- [ ] Use passphrase protection for private keys
- [ ] Configure trust levels (reject UNKNOWN peers)
- [ ] Set up firewall rules
- [ ] Enable audit logging
- [ ] Configure log rotation
- [ ] Use HTTPS for frontend (via reverse proxy)
- [ ] Restrict metrics endpoint to internal network
- [ ] Regular backups of data directory
- [ ] Monitor security audit logs

### Trust Configuration

For production, configure stricter trust policies:

```yaml
security:
  trust_level_default: UNKNOWN
  reject_unknown: true  # Reject unknown peers
```

---

## Troubleshooting

See [Troubleshooting Guide](troubleshooting.md) for common issues and solutions.

---

## Next Steps

1. **Monitor metrics**: Set up Prometheus and Grafana
2. **Configure alerts**: Set up alerting on health checks
3. **Enable backup**: Set up automated backups
4. **Scale out**: Deploy additional nodes as needed
5. **Security review**: Review security configuration

---

## Support

For issues or questions:
- Check [Troubleshooting Guide](troubleshooting.md)
- Review logs in `~/.project-dawn/logs/dawn.log`
- Check health endpoints: `http://localhost:9090/health`
- Review metrics: `http://localhost:9090/metrics`
