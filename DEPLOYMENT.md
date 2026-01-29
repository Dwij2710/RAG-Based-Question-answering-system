# Production Deployment Guide

This guide covers deploying the RAG QA System in production environments.

## Deployment Options

### 1. Docker Deployment (Recommended)

#### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py .
COPY . .

# Create necessary directories
RUN mkdir -p uploads vector_store metrics

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### docker-compose.yml

```yaml
version: '3.8'

services:
  rag-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./vector_store:/app/vector_store
      - ./metrics:/app/metrics
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

#### Build and Run

```bash
# Build image
docker build -t rag-qa-system .

# Run container
docker run -d \
  -p 8000:8000 \
  -e ANTHROPIC_API_KEY=your-key \
  -v $(pwd)/vector_store:/app/vector_store \
  -v $(pwd)/metrics:/app/metrics \
  --name rag-api \
  rag-qa-system

# Or use docker-compose
docker-compose up -d
```

### 2. Cloud Deployment

#### AWS EC2

1. **Launch EC2 Instance**
   - AMI: Ubuntu 22.04 LTS
   - Instance Type: t3.medium (2 vCPU, 4GB RAM) minimum
   - Storage: 20GB EBS volume

2. **Setup**
```bash
# SSH into instance
ssh -i key.pem ubuntu@<instance-ip>

# Install dependencies
sudo apt update
sudo apt install -y python3.11 python3-pip git

# Clone repository
git clone <repository-url>
cd rag-qa-system

# Install Python dependencies
pip install -r requirements.txt

# Set environment variables
export ANTHROPIC_API_KEY="your-key"

# Run with systemd (see below)
```

3. **Systemd Service** (`/etc/systemd/system/rag-api.service`)

```ini
[Unit]
Description=RAG QA System
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/rag-qa-system
Environment="ANTHROPIC_API_KEY=your-key"
ExecStart=/usr/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable rag-api
sudo systemctl start rag-api
sudo systemctl status rag-api
```

4. **Nginx Reverse Proxy** (`/etc/nginx/sites-available/rag-api`)

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # File upload size limit
    client_max_body_size 50M;
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/rag-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

5. **SSL with Let's Encrypt**

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

#### Google Cloud Platform (GCP)

1. **Cloud Run Deployment**

```bash
# Build and push to Container Registry
gcloud builds submit --tag gcr.io/PROJECT_ID/rag-qa-system

# Deploy to Cloud Run
gcloud run deploy rag-qa-system \
  --image gcr.io/PROJECT_ID/rag-qa-system \
  --platform managed \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2 \
  --set-env-vars ANTHROPIC_API_KEY=your-key \
  --allow-unauthenticated
```

2. **Compute Engine (similar to EC2)**

Follow AWS EC2 steps with GCP-specific networking.

#### Azure

1. **Azure Container Instances**

```bash
az container create \
  --resource-group rag-rg \
  --name rag-qa-system \
  --image your-registry.azurecr.io/rag-qa-system \
  --cpu 2 --memory 4 \
  --ports 8000 \
  --environment-variables ANTHROPIC_API_KEY=your-key \
  --dns-name-label rag-qa-unique
```

### 3. Kubernetes Deployment

#### deployment.yaml

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-qa-system
spec:
  replicas: 3
  selector:
    matchLabels:
      app: rag-qa-system
  template:
    metadata:
      labels:
        app: rag-qa-system
    spec:
      containers:
      - name: rag-api
        image: your-registry/rag-qa-system:latest
        ports:
        - containerPort: 8000
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: anthropic-key
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        volumeMounts:
        - name: vector-store
          mountPath: /app/vector_store
      volumes:
      - name: vector-store
        persistentVolumeClaim:
          claimName: vector-store-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: rag-qa-service
spec:
  selector:
    app: rag-qa-system
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

## Production Configurations

### Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional
LOG_LEVEL=INFO
MAX_UPLOAD_SIZE=52428800  # 50MB
RATE_LIMIT_PER_MINUTE=100
VECTOR_STORE_DIR=/data/vector_store
METRICS_DIR=/data/metrics
```

### Gunicorn for Production

Replace uvicorn with gunicorn for better production stability:

```bash
# Install
pip install gunicorn

# Run
gunicorn app:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

### Performance Tuning

#### 1. FAISS GPU Support

For faster similarity search:

```bash
# Install GPU version
pip uninstall faiss-cpu
pip install faiss-gpu
```

Modify `vector_store.py`:
```python
# Use GPU
res = faiss.StandardGpuResources()
self.index = faiss.index_cpu_to_gpu(res, 0, self.index)
```

#### 2. Redis Caching

Add caching for frequent queries:

```python
import redis
from functools import lru_cache

redis_client = redis.Redis(host='localhost', port=6379)

def cache_query(question: str, top_k: int):
    cache_key = f"query:{hash(question)}:{top_k}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    return None

def set_cache(question: str, top_k: int, result: dict):
    cache_key = f"query:{hash(question)}:{top_k}"
    redis_client.setex(cache_key, 3600, json.dumps(result))  # 1 hour TTL
```

#### 3. Celery for Background Jobs

For scalable background processing:

```python
# Install
pip install celery redis

# celery_app.py
from celery import Celery

celery_app = Celery(
    'rag_tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

@celery_app.task
def process_document_task(document_id, file_path, filename):
    # Your processing logic
    pass
```

## Monitoring & Observability

### 1. Prometheus Metrics

Add prometheus client:

```python
from prometheus_client import Counter, Histogram, generate_latest

# Metrics
query_count = Counter('rag_queries_total', 'Total queries')
query_latency = Histogram('rag_query_latency_seconds', 'Query latency')

@app.get("/prometheus")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### 2. Structured Logging

```python
import logging
import json
from pythonjsonlogger import jsonlogger

logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
```

### 3. Health Checks

Enhanced health check:

```python
@app.get("/health")
async def health_check():
    checks = {
        "api": "healthy",
        "vector_store": vector_store.has_documents(),
        "documents_count": len(vector_store.list_documents()),
        "disk_space": shutil.disk_usage("/").free > 1e9  # 1GB free
    }
    
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        content=checks,
        status_code=status_code
    )
```

## Security Hardening

### 1. API Authentication

Add JWT authentication:

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=["HS256"]
        )
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

@app.post("/ask", dependencies=[Depends(verify_token)])
async def ask_question(question_req: QuestionRequest):
    # Your logic
    pass
```

### 2. Rate Limiting with Redis

```python
from redis import Redis
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

@app.on_event("startup")
async def startup():
    redis = Redis(host="localhost", port=6379)
    await FastAPILimiter.init(redis)

@app.post("/ask", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
async def ask_question(question_req: QuestionRequest):
    # Your logic
    pass
```

### 3. Input Sanitization

```python
from bleach import clean

def sanitize_input(text: str) -> str:
    # Remove potentially harmful content
    return clean(text, tags=[], strip=True)
```

## Backup & Recovery

### Database Backups

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/rag-qa"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup vector store
tar -czf "$BACKUP_DIR/vector_store_$DATE.tar.gz" vector_store/

# Backup metrics
tar -czf "$BACKUP_DIR/metrics_$DATE.tar.gz" metrics/

# Keep only last 7 days
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

# Upload to S3 (optional)
aws s3 cp "$BACKUP_DIR/vector_store_$DATE.tar.gz" s3://your-bucket/backups/
```

### Automated Backups with Cron

```bash
# Add to crontab
0 2 * * * /path/to/backup.sh
```

## Scaling Strategies

### Horizontal Scaling

1. **Load Balancer**: Nginx/HAProxy
2. **Shared Storage**: NFS/S3 for vector store
3. **Message Queue**: RabbitMQ/Redis for background jobs
4. **Database**: PostgreSQL for metadata instead of JSON files

### Vertical Scaling

- Increase CPU/RAM for embedding generation
- Add GPU for faster FAISS operations
- SSD storage for faster I/O

## Cost Optimization

1. **Claude API Caching**: Cache common responses
2. **Spot Instances**: Use spot instances for non-critical workloads
3. **Auto-scaling**: Scale down during low traffic
4. **Storage Tiering**: Archive old documents to cheaper storage

## Troubleshooting Production Issues

### High Latency

```bash
# Check metrics
curl http://localhost:8000/metrics

# Monitor system resources
htop
iostat -x 5

# Profile Python code
python -m cProfile -o profile.stats app.py
```

### Memory Leaks

```python
# Add memory profiling
from memory_profiler import profile

@profile
def process_document():
    # Your code
    pass
```

### Disk Space Issues

```bash
# Clean old uploads
find uploads/ -mtime +1 -delete

# Rotate logs
logrotate /etc/logrotate.d/rag-api
```

## Compliance & Data Privacy

- **GDPR**: Implement user data deletion
- **Data Encryption**: Encrypt vectors at rest
- **Audit Logs**: Log all data access
- **Access Control**: Implement RBAC

## Migration Strategy

### Zero-Downtime Deployment

1. Deploy new version alongside old
2. Route 10% traffic to new version
3. Monitor metrics and errors
4. Gradually increase traffic
5. Retire old version

## Summary Checklist

- [ ] Containerize with Docker
- [ ] Set up reverse proxy (Nginx)
- [ ] Configure SSL/TLS
- [ ] Implement authentication
- [ ] Add monitoring and logging
- [ ] Set up automated backups
- [ ] Configure auto-scaling
- [ ] Implement health checks
- [ ] Test disaster recovery
- [ ] Document runbooks

For questions or support, open an issue in the repository.
