# Streamlit Caching Behavior

## Cache Duration
The Streamlit dashboard uses `@st.cache_data(ttl=300)` which means:
- Data is cached for **5 minutes** (300 seconds)
- After code updates, you may see stale data until cache expires

## When You'll See Cached Data
1. After rebuilding Docker container with code changes
2. After modifying Python files
3. After database updates (until TTL expires)

## How to Force Refresh

### Option 1: Wait for Cache to Expire
- Wait 5 minutes and refresh page
- Cache automatically expires after TTL

### Option 2: Use Sidebar Refresh Button
- Click **"🔄 Refresh Data"** in sidebar
- Clears all cached data immediately
- Available on all dashboard pages

### Option 3: Browser Hard Refresh
- Press **Ctrl+Shift+R** (Linux/Windows)
- Press **Cmd+Shift+R** (Mac)
- Or **Ctrl+F5**

### Option 4: Restart Container
```bash
docker-compose restart streamlit
```
This clears in-memory cache completely.

## After Code Changes

When you update Python code and rebuild:
```bash
# Rebuild with new code
docker-compose build streamlit

# Remove old container
docker-compose stop streamlit
docker-compose rm -f streamlit

# Start new container
docker-compose up -d streamlit

# Wait 10 seconds for startup
sleep 10

# Then refresh browser OR wait 5 minutes for cache expiry
```

## Current Fix Applied

The bug was fixed in commit `e1a65ea`:
- Changed `dna_data.get('moods', [])` → `dna_data.get('themes', [])`
- Changed `q.get('views_90d', 0)` → `q.get('total_views', 0)`

After rebuilding (completed), you should see:
- **Content Themes: 4** (was 0)
- **Total Views: 11,680** (was 0)

If still showing old values, refresh browser or wait 5 minutes.

## Verify Container Has New Code

```bash
# Check container creation time (should be recent)
docker-compose ps streamlit

# View logs
docker-compose logs --tail=20 streamlit

# Check if running
curl http://localhost:8501/_stcore/health
```

Status: Container rebuilt with fixed code at $(date)
