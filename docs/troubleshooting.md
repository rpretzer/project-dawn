# Troubleshooting Guide

Common issues and solutions for Project Dawn.

---

## Connectivity Issues

### Cannot Connect to WebSocket Server

**Symptoms:**
- Connection refused errors
- Timeout errors
- "Address already in use" errors

**Solutions:**

1. **Check if port is available**:
   ```bash
   # Check if port 8000 is in use
   netstat -tuln | grep 8000
   # Or
   lsof -i :8000
   ```

2. **Check firewall rules**:
   ```bash
   # Allow port 8000
   sudo ufw allow 8000/tcp
   ```

3. **Check if server is running**:
   ```bash
   # Check process
   ps aux | grep server_p2p
   
   # Check logs
   tail -f ~/.project-dawn/logs/dawn.log
   ```

4. **Try different port**:
   ```bash
   export PROJECT_DAWN_WS_PORT=8001
   python -m server_p2p
   ```

### Health Endpoints Not Responding

**Symptoms:**
- HTTP 404 on `/health`
- Connection refused on port 9090

**Solutions:**

1. **Check if API server is running**:
   ```bash
   # Check logs
   grep "API server" ~/.project-dawn/logs/dawn.log
   ```

2. **Check port availability**:
   ```bash
   netstat -tuln | grep 9090
   ```

3. **Verify metrics port configuration**:
   ```bash
   export PROJECT_DAWN_METRICS_PORT=9090
   ```

---

## Configuration Issues

### Configuration Not Loading

**Symptoms:**
- Default values used instead of config file
- Environment variables not taking effect

**Solutions:**

1. **Check config file location**:
   ```bash
   # Default location
   ls -la ~/.project-dawn/config.yaml
   
   # Or check data root
   echo $PROJECT_DAWN_DATA_ROOT
   ```

2. **Verify YAML syntax**:
   ```bash
   # Check YAML syntax
   python -c "import yaml; yaml.safe_load(open('config.yaml'))"
   ```

3. **Check environment variables**:
   ```bash
   # Print all PROJECT_DAWN_* variables
   env | grep PROJECT_DAWN
   ```

4. **Verify PyYAML installed**:
   ```bash
   pip list | grep -i yaml
   # If not installed:
   pip install pyyaml
   ```

### Logging Not Working

**Symptoms:**
- No log output
- Wrong log format
- Wrong log level

**Solutions:**

1. **Check log level**:
   ```bash
   export LOG_LEVEL=DEBUG
   python -m server_p2p
   ```

2. **Check log format**:
   ```bash
   export LOG_FORMAT=json
   python -m server_p2p
   ```

3. **Check log file location**:
   ```bash
   # Check config
   grep "file:" ~/.project-dawn/config.yaml
   
   # Check if directory exists
   mkdir -p ~/.project-dawn/logs
   ```

4. **Check permissions**:
   ```bash
   ls -la ~/.project-dawn/logs/
   # Should be writable by current user
   ```

---

## Security Issues

### Peer Connection Rejected

**Symptoms:**
- "Peer not trusted" errors
- "Cannot connect to untrusted peer" warnings

**Solutions:**

1. **Add peer to trust whitelist**:
   ```python
   from security import TrustManager, TrustLevel
   
   trust_manager = TrustManager()
   trust_manager.add_trusted_peer(
       node_id="peer_node_id",
       public_key="ed25519_public_key_hex",
       trust_level=TrustLevel.TRUSTED
   )
   ```

2. **Check trust configuration**:
   ```yaml
   security:
     trust_level_default: UNKNOWN
     reject_unknown: false  # Allow unknown peers
   ```

3. **Review audit logs**:
   ```bash
   tail -f ~/.project-dawn/vault/audit.log
   ```

### Signature Verification Failing

**Symptoms:**
- "Invalid signature" errors
- "Cannot verify signature" warnings

**Solutions:**

1. **Check peer's public key**:
   ```python
   from security import TrustManager
   
   trust_manager = TrustManager()
   record = trust_manager.get_trust_record("peer_node_id")
   if record:
       print(f"Public key: {record.public_key}")
   ```

2. **Verify peer's public key matches**:
   - Ensure public key in trust record matches peer's actual key
   - Check if key is in correct format (hex string)

3. **Check audit logs**:
   ```bash
   grep "signature" ~/.project-dawn/vault/audit.log
   ```

---

## Performance Issues

### High Memory Usage

**Symptoms:**
- Memory usage growing over time
- Out of memory errors

**Solutions:**

1. **Check peer connections**:
   ```bash
   # Check metrics
   curl http://localhost:9090/metrics | grep p2p_peers_total
   ```

2. **Review connection cleanup**:
   - Ensure disconnected peers are removed
   - Check for connection leaks

3. **Monitor resource usage**:
   ```bash
   # Check memory
   ps aux | grep server_p2p
   
   # Or with Docker
   docker stats project-dawn
   ```

### High CPU Usage

**Symptoms:**
- CPU usage consistently high
- Slow response times

**Solutions:**

1. **Check message rates**:
   ```bash
   curl http://localhost:9090/metrics | grep p2p_messages_total
   ```

2. **Review log levels**:
   ```yaml
   logging:
     level: INFO  # Use INFO or WARNING, not DEBUG
   ```

3. **Check for busy loops**:
   - Review logs for errors
   - Check for connection retries

---

## Data Issues

### Trust Records Not Persisting

**Symptoms:**
- Trust records lost on restart
- Peers need to be re-added

**Solutions:**

1. **Check data directory**:
   ```bash
   ls -la ~/.project-dawn/mesh/trust.json
   # Or
   ls -la ~/.project-dawn/vault/trust.json
   ```

2. **Check permissions**:
   ```bash
   chmod 600 ~/.project-dawn/mesh/trust.json
   ```

3. **Verify data directory exists**:
   ```bash
   mkdir -p ~/.project-dawn/mesh
   ```

### Node Identity Lost

**Symptoms:**
- New node ID on each start
- Cannot connect to existing peers

**Solutions:**

1. **Check identity file**:
   ```bash
   ls -la ~/.project-dawn/vault/node_identity.key
   ```

2. **Backup existing identity**:
   ```bash
   cp ~/.project-dawn/vault/node_identity.key ~/.project-dawn/vault/node_identity.key.backup
   ```

3. **Verify identity file format**:
   ```python
   # Should be 32 bytes
   key_bytes = open("~/.project-dawn/vault/node_identity.key", "rb").read()
   assert len(key_bytes) == 32
   ```

---

## Docker Issues

### Container Won't Start

**Symptoms:**
- Container exits immediately
- "Cannot connect to Docker daemon" errors

**Solutions:**

1. **Check logs**:
   ```bash
   docker-compose logs dawn
   # Or
   docker logs project-dawn
   ```

2. **Check image build**:
   ```bash
   docker build -t project-dawn:test .
   ```

3. **Check volume mounts**:
   ```bash
   docker-compose config
   ```

4. **Check resource limits**:
   ```yaml
   services:
     dawn:
       deploy:
         resources:
           limits:
             memory: 512M
   ```

### Port Conflicts

**Symptoms:**
- "Address already in use" errors
- Cannot access services

**Solutions:**

1. **Check port usage**:
   ```bash
   docker ps
   # Check which ports are in use
   ```

2. **Use different ports**:
   ```yaml
   services:
     dawn:
       ports:
         - "8001:8000"  # Use different host port
         - "8081:8080"
         - "9091:9090"
   ```

3. **Stop conflicting containers**:
   ```bash
   docker ps
   docker stop <container-id>
   ```

---

## Metrics Issues

### Metrics Not Exported

**Symptoms:**
- `/metrics` endpoint returns empty
- Prometheus cannot scrape metrics

**Solutions:**

1. **Check prometheus-client installed**:
   ```bash
   pip list | grep prometheus
   # If not installed:
   pip install prometheus-client
   ```

2. **Check metrics endpoint**:
   ```bash
   curl http://localhost:9090/metrics
   ```

3. **Check API server logs**:
   ```bash
   grep "API server" ~/.project-dawn/logs/dawn.log
   ```

4. **Verify metrics port**:
   ```bash
   export PROJECT_DAWN_METRICS_PORT=9090
   ```

---

## Getting Help

### Logs to Collect

When reporting issues, collect:

1. **Application logs**:
   ```bash
   tail -n 1000 ~/.project-dawn/logs/dawn.log
   ```

2. **Audit logs**:
   ```bash
   tail -n 100 ~/.project-dawn/vault/audit.log
   ```

3. **Health status**:
   ```bash
   curl http://localhost:9090/health | jq
   ```

4. **Metrics**:
   ```bash
   curl http://localhost:9090/metrics > metrics.txt
   ```

5. **Configuration**:
   ```bash
   cat ~/.project-dawn/config.yaml
   env | grep PROJECT_DAWN
   ```

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
export LOG_FORMAT=text  # Use text format for easier reading
python -m server_p2p
```

### Common Error Messages

| Error | Solution |
|-------|----------|
| "Address already in use" | Change port or stop conflicting service |
| "Peer not trusted" | Add peer to trust whitelist |
| "Invalid signature" | Verify peer's public key |
| "Cannot load config" | Check YAML syntax and file location |
| "Metrics collection disabled" | Install prometheus-client |
| "Permission denied" | Check file permissions and ownership |

---

## Additional Resources

- [Deployment Guide](deployment.md)
- [Production Checklist](production-checklist.md)
- [Configuration Documentation](configuration.md)
- [README](../README.md)
