# Deployment

Production deployment guide for bybit-ws.

## Uvicorn (Recommended)

```bash
uvicorn bybit_ws.app:app --host 0.0.0.0 --port 8000 --workers 1
```

> **Important:** Use `--workers 1` because the WebSocket manager maintains in-memory state. For multi-worker deployments, use Redis Pub/Sub as a shared message bus.

### With Gunicorn

```bash
gunicorn bybit_ws.app:app -w 1 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

## Docker

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["python", "-m", "bybit_ws.app"]
```

### Build and Run

```bash
docker build -t bybit-ws .
docker run -d -p 8000:8000 --name bybit-ws bybit-ws
```

### Docker Compose

```yaml
version: "3.8"
services:
  bybit-ws:
    build: .
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Reverse Proxy

### Nginx

```nginx
upstream bybit_ws {
    server 127.0.0.1:8000;
}

server {
    listen 443 ssl http2;
    server_name market-data.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://bybit_ws;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws/ {
        proxy_pass http://bybit_ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### Caddy

```
market-data.example.com {
    reverse_proxy localhost:8000
}
```

## Production Checklist

- [ ] Use `--workers 1` or external pub/sub for state sharing
- [ ] Place behind reverse proxy with TLS termination
- [ ] Add authentication (API keys, JWT)
- [ ] Add rate limiting middleware
- [ ] Set up monitoring (Prometheus metrics endpoint)
- [ ] Configure log aggregation (structured JSON logging)
- [ ] Set up health check monitoring (UptimeRobot, Pingdom)
- [ ] Replace in-memory store with Redis/PostgreSQL for durability
- [ ] Configure CORS origins for production domain

## Scaling Considerations

### Single Worker Limitation

The WebSocket manager holds all market data in process memory. This means:
- Only **1 worker process** can hold the WebSocket connection
- Multi-worker deployments need external state sharing

### Multi-Worker Architecture

```
                    ┌─── Worker 1 (API only)
Load Balancer ──────┼─── Worker 2 (API only)
                    └─── Worker 3 (API only)
                              │
                         Redis Pub/Sub
                              │
                    ┌─────────┴─────────┐
               WS Manager (separate process)
                    Connected to Bybit
```

### Memory Usage

Approximate memory per symbol:
- Trades buffer (1,000 records): ~200 KB
- Orderbook snapshot: ~50 KB
- Ticker history (500 records): ~100 KB
- Kline history (500 records): ~80 KB

**Total per symbol: ~430 KB**
**10 symbols: ~4.3 MB**
**50 symbols: ~21.5 MB**

## Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

### System Stats

```bash
curl http://localhost:8000/stats
```

### Connection Status

```bash
curl http://localhost:8000/status
```
