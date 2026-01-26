# PROMPT FOR GITHUB COPILOT CLI

## Task: Add API Key Authentication to FastAPI

### Context
I have a FastAPI application at `app/api/main.py` with 14 endpoints that are currently public. I need to add simple API key authentication to protect all endpoints except `/` and `/api/health`.

### Requirements

**1. Create `app/api/dependencies.py`:**
```python
# API Key verification dependency
- Read API_KEY from environment variable (API_KEY in .env)
- Fallback to hardcoded key for demo: "devto-challenge-2026"
- Accept key via header: X-API-Key
- Raise HTTPException(403) if invalid
- Return api_key if valid
```

**2. Update `app/api/main.py`:**
```python
# Import the dependency
from app.api.dependencies import verify_api_key
from fastapi import Depends

# Protect these endpoints (add dependencies=[Depends(verify_api_key)]):
- All /api/analytics/* endpoints (quality, read-time, overview, reactions)
- All /api/dna/* endpoints (/, classify/{id})
- All /api/nlp/* endpoints (sentiment, questions)
- All /api/articles/* endpoints (/, /{id}/content)
- POST /api/sync

# Keep these PUBLIC (no auth):
- GET / (welcome message)
- GET /api/health (health check)
- GET /api/test (optional - can protect if you want)
```

**3. Update `.env.example`:**
```bash
# Add this line
API_KEY=your_secret_api_key_here
```

**4. Update `API_DOCUMENTATION.md`:**
```markdown
# Add Authentication section
## Authentication

All API endpoints (except `/` and `/api/health`) require authentication via API key.

### How to authenticate:
Include the API key in the request header:
```bash
X-API-Key: your_api_key_here
```

### Example:
```bash
curl -H "X-API-Key: devto-challenge-2026" \
     http://localhost:8000/api/analytics/quality?limit=5
```

### For Swagger UI:
Click "Authorize" button and enter your API key.
```

**5. Add OpenAPI security scheme in `main.py`:**
```python
# Update FastAPI app initialization
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

app = FastAPI(
    title="DEV.to Analytics API",
    # ... existing config ...
    # Add security scheme for Swagger UI
)

# Add security definition to openapi schema
app.openapi()["components"]["securitySchemes"] = {
    "ApiKeyAuth": {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key"
    }
}
```

### Expected Behavior

**Without API key:**
```bash
$ curl http://localhost:8000/api/analytics/quality
{"detail":"Missing API Key"}
```

**With invalid API key:**
```bash
$ curl -H "X-API-Key: wrong" http://localhost:8000/api/analytics/quality
{"detail":"Invalid API Key"}
```

**With valid API key:**
```bash
$ curl -H "X-API-Key: devto-challenge-2026" \
       http://localhost:8000/api/analytics/quality?limit=5
[{"article_id": 2969205, "quality_score": 75.9, ...}]
```

**Public endpoints (no auth needed):**
```bash
$ curl http://localhost:8000/api/health
{"status":"ok","database":"connected"}
```

### Testing Checklist

After implementation, verify:
- [ ] All protected endpoints reject requests without API key
- [ ] All protected endpoints reject requests with invalid API key
- [ ] All protected endpoints accept requests with valid API key
- [ ] Public endpoints (/, /health) work without API key
- [ ] Swagger UI shows "Authorize" button
- [ ] .env.example includes API_KEY variable

### Notes
- Keep it SIMPLE - just header verification, no database
- Environment variable should be used in production
- Hardcoded fallback for demo/development
- API key should be in README for jury/testers

---

## Files to Create/Modify

**Create:**
1. `app/api/dependencies.py` (~20 lines)

**Modify:**
2. `app/api/main.py` (add Depends to 11 endpoints)
3. `API_DOCUMENTATION.md` (add Auth section)
4. `.env.example` (add API_KEY)
5. `README.md` (mention API key in quickstart)

**Estimated time:** 10-15 minutes with Copilot
**Complexity:** Low
**Impact:** High (production-ready security)
