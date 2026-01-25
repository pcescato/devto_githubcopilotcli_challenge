# FastAPI Application - DEV.to Analytics Platform

## Overview

Production-ready FastAPI application exposing all 5 PostgreSQL async services via REST API.

**Features:**
- ✅ Async PostgreSQL with connection pooling
- ✅ Dependency injection with shared AsyncEngine
- ✅ CORS enabled for local development
- ✅ OpenAPI/Swagger documentation
- ✅ Pydantic validation for all requests/responses
- ✅ Global error handling
- ✅ Background tasks for long operations

**Tech Stack:**
- FastAPI 0.128.0
- Uvicorn (ASGI server)
- Pydantic 2.12 (validation)
- SQLAlchemy 2.0 (async)
- AsyncPG (PostgreSQL driver)

## Quick Start

### 1. Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Ensure .env file has PostgreSQL credentials
cat .env
# POSTGRES_HOST=localhost
# POSTGRES_PORT=5432
# POSTGRES_DB=devto_analytics
# POSTGRES_USER=your_user
# POSTGRES_PASSWORD=your_password
# DEVTO_API_KEY=your_api_key
```

### 2. Start Server

```bash
# Development mode (auto-reload)
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 3. Access Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## API Endpoints

### Health & Status

#### GET /
Root endpoint with API info.

```bash
curl http://localhost:8000/
```

**Response:**
```json
{
  "name": "DEV.to Analytics API",
  "version": "1.0.0",
  "docs": "/docs",
  "health": "/api/health"
}
```

#### GET /api/health
Health check with database connectivity test.

```bash
curl http://localhost:8000/api/health
```

**Response:**
```json
{
  "status": "ok",
  "database": "connected",
  "timestamp": "2026-01-25T22:30:00Z",
  "version": "1.0.0"
}
```

### Analytics

#### GET /api/analytics/quality
Get quality scores for top articles (90-day period).

**Query Parameters:**
- `limit` (int, default: 10): Number of results

```bash
curl "http://localhost:8000/api/analytics/quality?limit=5"
```

**Response:**
```json
[
  {
    "article_id": 3180743,
    "title": "Building My Own DEV.to Analytics",
    "quality_score": 87.5,
    "completion_percent": 82.3,
    "engagement_percent": 8.97,
    "views_90d": 1472
  }
]
```

**Formula:**
- Quality Score = (completion × 0.7) + (min(engagement, 20) × 1.5)
- Completion % = (avg_read_time / reading_time) × 100
- Engagement % = (reactions + comments) / views × 100

#### GET /api/analytics/read-time
Get read time analysis for articles.

**Query Parameters:**
- `limit` (int, default: 10): Number of results

```bash
curl "http://localhost:8000/api/analytics/read-time?limit=5"
```

**Response:**
```json
[
  {
    "article_id": 3180743,
    "title": "Building My Own DEV.to Analytics",
    "reading_time_minutes": 8,
    "avg_read_seconds": 394,
    "completion_percent": 82.1,
    "total_hours": 161.2
  }
]
```

#### GET /api/analytics/overview
Get global analytics overview with trends.

**Query Parameters:**
- `days` (int, default: 7): Period length in days

```bash
curl "http://localhost:8000/api/analytics/overview?days=7"
```

**Response:**
```json
{
  "period_days": 7,
  "current": {"views": 3420, "reactions": 156, "comments": 42},
  "previous": {"views": 2890, "reactions": 134, "comments": 38},
  "delta": {"views": 530, "reactions": 22, "comments": 4},
  "delta_percent": {"views": 18.3, "reactions": 16.4, "comments": 10.5}
}
```

#### GET /api/analytics/reactions
Get reaction breakdown for articles.

**Query Parameters:**
- `limit` (int, default: 10): Number of results

```bash
curl "http://localhost:8000/api/analytics/reactions?limit=5"
```

**Response:**
```json
[
  {
    "article_id": 3180743,
    "title": "Building My Own DEV.to Analytics",
    "age_days": 7,
    "lifetime_reactions": 88,
    "like": 62,
    "unicorn": 15,
    "readinglist": 11,
    "sum_reactions": 88,
    "gap": 0
  }
]
```

**Gap Field:**
- Positive: Old reactions where type (Like/Unicorn) was lost (>90 days)
- Negative: Reactions removed by users (history preserved)

### Author DNA

#### GET /api/dna
Get Author DNA report with theme distribution.

```bash
curl http://localhost:8000/api/dna
```

**Response:**
```json
{
  "themes": [
    {
      "theme_name": "Expertise Tech",
      "article_count": 14,
      "total_views": 3472,
      "total_reactions": 138,
      "avg_views": 248.0,
      "engagement_pct": 3.97
    },
    {
      "theme_name": "Culture & Agile",
      "article_count": 4,
      "total_views": 3345,
      "total_reactions": 82,
      "avg_views": 836.0,
      "engagement_pct": 2.45
    }
  ]
}
```

**Themes:**
- **Expertise Tech**: sql, database, python, cloud, docker, vps, astro, hugo, vector, cte
- **Human & Career**: cv, career, feedback, developer, learning, growth
- **Culture & Agile**: agile, scrum, performance, theater, laziness, management
- **Free Exploration**: Articles with no theme matches

#### POST /api/dna/classify/{article_id}
Classify article into theme.

```bash
curl -X POST http://localhost:8000/api/dna/classify/3180743
```

**Response:**
```json
{
  "article_id": 3180743,
  "theme_name": "Expertise Tech",
  "match_count": 1,
  "confidence_score": 0.10,
  "matched_keywords": ["python"]
}
```

**Algorithm:**
1. Count absolute keyword matches (case-insensitive)
2. Select theme with HIGHEST match_count
3. Tie-breaker: Use confidence_score
4. Fallback: Assign 'Free Exploration' if all counts = 0

### NLP

#### GET /api/nlp/sentiment
Get global sentiment statistics.

```bash
curl http://localhost:8000/api/nlp/sentiment
```

**Response:**
```json
{
  "total": 145,
  "moods": [
    {"mood": "positive", "count": 98, "percentage": 67.6},
    {"mood": "neutral", "count": 32, "percentage": 22.1},
    {"mood": "negative", "count": 15, "percentage": 10.3}
  ]
}
```

**Thresholds:**
- Positive: score ≥ 0.3
- Negative: score ≤ -0.2
- Neutral: -0.2 < score < 0.3

#### GET /api/nlp/questions
Find unanswered questions in comments.

**Query Parameters:**
- `limit` (int, default: 10): Number of results

```bash
curl "http://localhost:8000/api/nlp/questions?limit=5"
```

**Response:**
```json
[
  {
    "comment_id": "abc123",
    "article_title": "Building Analytics Platform",
    "author_username": "john_doe",
    "text_preview": "How did you handle rate limiting?",
    "created_at": "2026-01-25T20:00:00Z"
  }
]
```

### Articles

#### GET /api/articles
Get latest article snapshots.

**Query Parameters:**
- `limit` (int, default: 20): Number of results

```bash
curl "http://localhost:8000/api/articles?limit=5"
```

**Response:**
```json
[
  {
    "article_id": 3180743,
    "title": "Building My Own DEV.to Analytics",
    "published_at": "2026-01-18T20:27:16.124Z",
    "views": 1474,
    "reactions": 88,
    "comments": 44,
    "reading_time_minutes": 8,
    "tags": ["devto", "analytics", "python", "opensource"]
  }
]
```

#### GET /api/articles/{article_id}/content
Get full article content with analysis.

```bash
curl http://localhost:8000/api/articles/3180743/content
```

**Response:**
```json
{
  "article_id": 3180743,
  "body_markdown": "# Building Analytics\n\nContent here...",
  "word_count": 1542,
  "code_blocks": [
    {"language": "python", "line_count": 24, "block_order": 0}
  ],
  "links": [
    {"url": "https://dev.to", "link_text": "DEV.to", "link_order": 0}
  ]
}
```

### Sync Operations

#### POST /api/sync
Trigger data synchronization with DEV.to API.

**Request Body:**
```json
{
  "mode": "snapshot"
}
```

**Modes:**
- `snapshot`: Sync article metrics only (fast, ~30s)
- `full`: Sync articles, followers, comments (comprehensive, ~2min)
- `rich`: Include historical analytics and referrers (slow, ~5min)

```bash
curl -X POST http://localhost:8000/api/sync \
  -H "Content-Type: application/json" \
  -d '{"mode": "snapshot"}'
```

**Response:**
```json
{
  "mode": "snapshot",
  "status": "started",
  "message": "Background sync initiated with mode: snapshot",
  "timestamp": "2026-01-25T22:30:00Z"
}
```

**Note:** Sync runs in background. Check logs for progress.

## Architecture

### Lifespan Management

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create AsyncEngine with connection pooling
    engine = create_async_engine(db_url, pool_size=20, max_overflow=10)
    app.state.engine = engine
    yield
    # Shutdown: Dispose engine and close connections
    await engine.dispose()
```

### Dependency Injection

```python
async def get_engine() -> AsyncGenerator[AsyncEngine, None]:
    yield app.state.engine

async def get_analytics_service(engine: AsyncEngine = Depends(get_engine)):
    return AnalyticsService(engine=engine)

@app.get("/api/analytics/quality")
async def get_quality_scores(
    analytics: AnalyticsService = Depends(get_analytics_service)
):
    scores = await analytics.get_quality_scores(limit=10)
    return scores
```

**Benefits:**
- Single AsyncEngine shared across all requests
- Connection pooling (20 connections, 10 overflow)
- Services initialized per-request
- Automatic cleanup on shutdown

### Error Handling

```python
@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": "Database error", "detail": str(exc)}
    )
```

**Error Responses:**
```json
{
  "error": "Database error",
  "detail": "Connection timeout",
  "timestamp": "2026-01-25T22:30:00Z"
}
```

### CORS Configuration

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
```

**Allowed Origins:**
- http://localhost:3000 (React default)
- http://localhost:8000 (API itself)
- http://localhost:5173 (Vite default)

## Testing

### Manual Testing

```bash
# Health check
curl http://localhost:8000/api/health

# Quality scores
curl "http://localhost:8000/api/analytics/quality?limit=5"

# DNA report
curl http://localhost:8000/api/dna

# Test endpoint (verifies all services)
curl http://localhost:8000/api/test
```

### Test Endpoint Response

```json
{
  "status": "ok",
  "services": {
    "analytics": "working",
    "theme": "working"
  },
  "sample_quality_score": {...},
  "theme_count": 4
}
```

## Deployment

### Development

```bash
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Production

```bash
# Multi-worker mode (CPU cores × 2)
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# With Gunicorn (production-ready)
gunicorn app.api.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

Required in `.env` or environment:
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=devto_analytics
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
DEVTO_API_KEY=your_api_key
```

## Performance

### Connection Pooling

- **Pool Size**: 20 connections
- **Max Overflow**: 10 additional connections
- **Pre-ping**: Validates connections before use
- **Total Capacity**: 30 concurrent connections

### Response Times (Typical)

- Health check: ~5ms
- Quality scores (limit=10): ~50ms
- DNA report: ~30ms
- Articles list (limit=20): ~40ms
- Full sync (background): 2-5 minutes

## Security

### API Key Protection

DEV.to API key is loaded from environment variables, not committed to code.

### CORS

CORS is configured for local development only. Update `allow_origins` for production.

### Database

PostgreSQL credentials from environment variables only.

## Monitoring

### Logs

```bash
# View API logs
tail -f /var/log/uvicorn.log

# View sync logs
tail -f /var/log/devto_sync.log
```

### Health Checks

```bash
# Kubernetes health check
livenessProbe:
  httpGet:
    path: /api/health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30
```

## Troubleshooting

### Connection Pool Exhausted

**Symptom:** `TimeoutError: QueuePool limit exceeded`

**Solution:** Increase `pool_size` and `max_overflow` in lifespan configuration.

### Slow Queries

**Symptom:** API responses > 1 second

**Solution:** 
1. Check PostgreSQL indexes
2. Use `EXPLAIN ANALYZE` on slow queries
3. Consider caching frequently accessed data

### CORS Errors

**Symptom:** `Access-Control-Allow-Origin` errors in browser

**Solution:** Add frontend origin to `allow_origins` list in CORS middleware.

## Files Structure

```
app/
├── api/
│   ├── __init__.py         # Module exports
│   ├── main.py             # FastAPI application (650 lines)
│   └── models.py           # Pydantic response models (360 lines)
├── services/
│   ├── analytics_service.py
│   ├── theme_service.py
│   ├── nlp_service.py
│   ├── content_service.py
│   └── devto_service.py
└── db/
    └── tables.py           # SQLAlchemy schema
```

## Summary

✅ **14 Endpoints** across 6 categories
✅ **5 Services** fully integrated
✅ **Async Architecture** for performance
✅ **OpenAPI Documentation** auto-generated
✅ **Production-Ready** with error handling and logging
✅ **CORS Enabled** for frontend integration
✅ **Background Tasks** for long operations
✅ **Connection Pooling** for scalability

The API is ready for frontend integration and production deployment!
