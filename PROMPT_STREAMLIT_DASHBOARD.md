# PROMPT FOR GITHUB COPILOT CLI - Streamlit Dashboard from CLI Services

## Context
I have a complete DEV.to analytics platform with CLI tools that work perfectly:

**Existing CLI Services:**
1. `app/services/analytics_service.py` - Quality scores, read time, reactions
2. `app/services/theme_service.py` - Author DNA analysis, theme classification
3. `sismograph.py` - Evolution tracking, engagement trends
4. `app/services/devto_service.py` - API data collection
5. `app/services/nlp_service.py` - Sentiment analysis

**Current Usage (CLI):**
```bash
# Analytics dashboard
python -m app.services.analytics_service --dashboard

# Author DNA report
python -m app.services.theme_service --report

# Evolution tracking
python sismograph.py --engagement-evolution 3180743
```

**What Works:**
- All services use async PostgreSQL (AsyncEngine)
- Rich console output with tables and charts
- Complete business logic implemented
- Database connection in `app/db/connection.py`

## Task
Create a **Streamlit web dashboard** that uses these existing services to visualize the data.

## Requirements

### 1. File Structure
```
app/
├── streamlit_app.py          # Main Streamlit application (NEW)
├── pages/                    # Streamlit pages (NEW)
│   ├── 1_📊_Analytics.py    # Quality scores, read time
│   ├── 2_🧬_Author_DNA.py   # Theme analysis
│   ├── 3_📈_Evolution.py    # Trends over time
│   └── 4_💬_Sentiment.py    # Comment sentiment
├── services/                 # Existing services (REUSE)
│   ├── analytics_service.py  # ✅ Already exists
│   ├── theme_service.py      # ✅ Already exists
│   ├── nlp_service.py        # ✅ Already exists
│   └── ...
└── db/                       # Existing DB layer (REUSE)
    ├── connection.py         # ✅ Already exists
    └── tables.py             # ✅ Already exists
```

### 2. Main App (`app/streamlit_app.py`)

**Features:**
- Welcome page with project overview
- Sidebar navigation to different pages
- Database connection status indicator
- Quick stats cards (total articles, avg quality, themes count)
- Links to API docs and Superset dashboards

**Layout:**
```python
import streamlit as st
from app.db.connection import get_async_engine
from app.services.analytics_service import AnalyticsService

st.set_page_config(
    page_title="DEV.to Analytics",
    page_icon="📊",
    layout="wide"
)

st.title("📊 DEV.to Analytics Dashboard")
st.markdown("Real-time insights into content performance")

# Sidebar
st.sidebar.title("Navigation")
st.sidebar.info("Use the pages above to explore different metrics")

# Quick stats
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Articles", "26")
with col2:
    st.metric("Avg Quality Score", "58.3")
# ... etc
```

### 3. Page 1: Analytics (`pages/1_📊_Analytics.py`)

**Reuse:** `AnalyticsService` methods
- `get_quality_scores(limit=20)`
- `get_read_time_analysis()`
- `get_reaction_breakdown()`

**Visualizations:**
1. **Quality Scores Table** (Streamlit dataframe)
   - Columns: Title, Quality Score, Views, Engagement %
   - Sortable, filterable
   - Color-coded by quality tier

2. **Read Time Distribution** (Plotly bar chart)
   - X: Read time buckets
   - Y: Article count
   - Interactive hover

3. **Reaction Types** (Plotly pie chart)
   - Hearts, Unicorns, Bookmarks, etc.
   - Percentage breakdown

**Code Structure:**
```python
import streamlit as st
import asyncio
from app.services.analytics_service import AnalyticsService
from app.db.connection import get_async_engine
import plotly.express as px
import pandas as pd

st.title("📊 Analytics Dashboard")

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_quality_scores():
    async def _load():
        engine = get_async_engine()
        service = AnalyticsService(engine)
        return await service.get_quality_scores(limit=50)
    return asyncio.run(_load())

# Display data
df = pd.DataFrame(load_quality_scores())
st.dataframe(df, use_container_width=True)

# Plotly chart
fig = px.bar(df, x='title', y='quality_score')
st.plotly_chart(fig, use_container_width=True)
```

### 4. Page 2: Author DNA (`pages/2_🧬_Author_DNA.py`)

**Reuse:** `ThemeService` methods
- `generate_dna_report()`
- `get_theme_distribution()`

**Visualizations:**
1. **Theme Distribution Pie Chart** (Plotly)
   - 4 themes with distinct colors
   - Show article count + percentage

2. **Performance by Theme** (Plotly grouped bars)
   - X: Theme name
   - Y1: Avg views (bar)
   - Y2: Engagement % (bar)
   - Grouped side-by-side

3. **DNA Summary Cards**
   - Top theme by articles
   - Top theme by views
   - Top theme by engagement

### 5. Page 3: Evolution (`pages/3_📈_Evolution.py`)

**Reuse:** `sismograph.py` logic
- Engagement evolution over time
- Follower correlation
- Views vs reactions trends

**Visualizations:**
1. **Engagement Evolution** (Plotly line chart)
   - X: Date (collected_at)
   - Y: Engagement %
   - Smooth line, markers

2. **Views & Reactions Dual Axis** (Plotly)
   - Y1: Total views (area chart)
   - Y2: Total reactions (line chart)
   - Time series over 90 days

3. **Article Selector**
   - Dropdown to select article
   - Show evolution for that article

### 6. Page 4: Sentiment (`pages/4_💬_Sentiment.py`)

**Reuse:** `NLPService` methods
- `get_sentiment_stats()`
- `get_spam_detection_results()`

**Visualizations:**
1. **Sentiment Distribution** (Plotly pie)
   - Positive, Neutral, Negative
   - Color-coded (green, gray, red)

2. **Sentiment by Article** (Plotly bar)
   - X: Article title
   - Y: Avg sentiment score
   - Sort by sentiment

3. **Recent Comments Table**
   - Author, Comment, Sentiment, Spam?
   - Filterable by sentiment

## Technical Requirements

### Dependencies
```txt
streamlit>=1.30.0
plotly>=5.18.0
pandas>=2.1.0
nest-asyncio>=1.6.0  # CRITICAL for async in Streamlit
# Existing requirements already installed
```

### Data Validation & Type Safety

**IMPORTANT**: Validate data before visualization to avoid runtime errors:

```python
from typing import List, Dict, Optional
import pandas as pd

def validate_quality_scores(data: List[Dict]) -> pd.DataFrame:
    """Convert service output to validated DataFrame"""
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # Ensure required columns exist
    required_cols = ['article_id', 'title', 'quality_score', 'views_90d']
    missing_cols = set(required_cols) - set(df.columns)
    if missing_cols:
        st.error(f"Missing columns: {missing_cols}")
        return pd.DataFrame()
    
    # Type conversion with error handling
    df['quality_score'] = pd.to_numeric(df['quality_score'], errors='coerce')
    df['views_90d'] = pd.to_numeric(df['views_90d'], errors='coerce')
    
    # Filter out invalid rows
    df = df.dropna(subset=['quality_score'])
    
    # Sort by quality score descending
    df = df.sort_values('quality_score', ascending=False)
    
    return df

# Usage
raw_data = load_quality_scores(engine)
df = validate_quality_scores(raw_data)

if df.empty:
    st.warning("No valid quality score data available")
else:
    st.dataframe(df)
```

**Why validation matters:**
- Services return dicts, Plotly expects DataFrames
- NULL values crash charts
- Type mismatches cause silent failures
- Missing columns break UI

### Async Handling
Since Streamlit is sync but our services are async:

```python
import asyncio
import nest_asyncio

# Enable nested event loops (critical for Streamlit + async)
nest_asyncio.apply()

def run_async(coro):
    """Helper to run async functions in Streamlit"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

# Usage
@st.cache_data(ttl=300)
def load_data():
    async def _load():
        engine = get_async_engine()
        service = MyService(engine)
        data = await service.get_data()
        # IMPORTANT: Close engine connection
        await engine.dispose()
        return data
    return run_async(_load())
```

**Critical async considerations:**
1. **Connection cleanup**: Always `await engine.dispose()` after data loading
2. **Event loop management**: Use `nest_asyncio` to avoid "loop already running" errors
3. **Cache invalidation**: Set reasonable TTL to avoid stale connections
4. **Error handling**: Wrap all async calls in try/except with proper cleanup

### Database Connection Management

**IMPORTANT**: Streamlit's execution model (top-to-bottom on every interaction) requires careful connection handling:

```python
import streamlit as st
from app.db.connection import get_async_engine

@st.cache_resource
def get_cached_engine():
    """Get or create cached engine (reused across reruns)"""
    return get_async_engine()

@st.cache_data(ttl=300)
def load_quality_scores(_engine):  # Note: _engine prefix tells Streamlit not to hash it
    """Load data with proper connection cleanup"""
    async def _load():
        async with _engine.connect() as conn:
            service = AnalyticsService(_engine)
            return await service.get_quality_scores(limit=50)
    return run_async(_load())

# Usage in app
engine = get_cached_engine()
data = load_quality_scores(engine)
```

**Why this matters:**
- Streamlit reruns entire script on every interaction
- Without caching, you'd create new DB connections on every button click
- `@st.cache_resource` ensures engine is created once
- `@st.cache_data` ensures queries run only when cache expires

### Caching Strategy
- Use `@st.cache_data` for data loading (TTL 5 minutes)
- Use `@st.cache_resource` for database engine
- Clear cache button in sidebar

### Error Handling
- Try/except around all async calls
- Display user-friendly error messages
- Connection status indicator
- Graceful degradation when services fail

**Production-ready error handling pattern:**

```python
import streamlit as st
import traceback

def safe_load_data(loader_func, fallback_message="No data available"):
    """Wrapper for safe data loading with user-friendly errors"""
    try:
        return loader_func()
    except Exception as e:
        st.error(f"⚠️ Error loading data: {fallback_message}")
        with st.expander("🔍 Technical details (for debugging)"):
            st.code(traceback.format_exc())
        return None

# Usage
data = safe_load_data(
    lambda: load_quality_scores(engine),
    fallback_message="Could not load quality scores. Check database connection."
)

if data is not None:
    st.dataframe(data)
else:
    st.info("👆 Click technical details above to see error information")
```

### Edge Cases to Handle

1. **Empty database** - No articles yet
   - Show placeholder message: "No data yet. Run data sync first."
   - Provide button to trigger sync

2. **Incomplete data** - Articles without metrics
   - Filter out NULL values before charting
   - Show warning: "X articles missing metrics"

3. **Stale data** - Last sync > 24 hours ago
   - Display last sync timestamp
   - Show warning banner if data is old
   - Provide "Refresh Data" button

4. **Connection failures** - Database unreachable
   - Display clear error: "Cannot connect to database"
   - Suggest: Check if PostgreSQL is running
   - Retry button with exponential backoff

5. **Slow queries** - Queries taking >5 seconds
   - Add `st.spinner()` with progress message
   - Consider query timeout (use asyncio.wait_for)
   - Cache aggressively for slow operations

**Example edge case handling:**

```python
@st.cache_data(ttl=300)
def load_with_fallback(_engine):
    async def _load():
        try:
            async with asyncio.timeout(10):  # 10 second timeout
                service = AnalyticsService(_engine)
                data = await service.get_quality_scores(limit=50)
                
                if not data or len(data) == 0:
                    st.warning("📭 No articles found. Have you run the data sync?")
                    return []
                
                return data
        except asyncio.TimeoutError:
            st.error("⏱️ Query took too long. Try reducing the data range.")
            return []
        except Exception as e:
            st.error(f"❌ Database error: {str(e)}")
            return []
    
    return run_async(_load())
```

## Styling & UX

### Theme
- Use Streamlit's default theme (clean, professional)
- Add custom CSS for quality score color coding:
  ```python
  st.markdown("""
  <style>
  .high-quality { color: green; font-weight: bold; }
  .medium-quality { color: orange; }
  .low-quality { color: red; }
  </style>
  """, unsafe_allow_html=True)
  ```

### Layout
- Use `st.columns()` for side-by-side metrics
- Use `st.expander()` for detailed sections
- Use `st.tabs()` for multiple views on same page

### Interactivity
- Add filters (date range, theme, quality threshold)
- Add sorting options for tables
- Add refresh buttons for real-time updates
- Add export to CSV buttons

## Expected Output Files

1. **app/streamlit_app.py** - Main entry point
2. **app/pages/1_📊_Analytics.py** - Analytics page
3. **app/pages/2_🧬_Author_DNA.py** - DNA page
4. **app/pages/3_📈_Evolution.py** - Evolution page
5. **app/pages/4_💬_Sentiment.py** - Sentiment page
6. **app/requirements-streamlit.txt** - Additional dependencies
7. **STREAMLIT_GUIDE.md** - Usage instructions

## Running the App

```bash
# Install dependencies
pip install streamlit plotly pandas

# Run Streamlit app
streamlit run app/streamlit_app.py

# Access at http://localhost:8501
```

## Important Constraints

1. **REUSE existing services** - Don't rewrite business logic
2. **Keep async architecture** - Use asyncio.run() helper
3. **Match CLI output** - Same metrics, same calculations
4. **Production-ready** - Error handling, caching, UX
5. **Fast development** - Leverage Streamlit's simplicity

## Verification

After generation, verify:
- [ ] App starts without errors: `streamlit run app/streamlit_app.py`
- [ ] All 4 pages load without exceptions
- [ ] Data matches CLI output (compare numbers manually)
- [ ] Charts are interactive (Plotly hover, zoom, pan)
- [ ] Caching works (second load is instant, check with st.spinner)
- [ ] Database connection stable (no "connection refused" errors)
- [ ] Quality scores match AnalyticsService output
- [ ] DNA report matches ThemeService output
- [ ] No event loop errors (thanks to nest_asyncio)
- [ ] Connection cleanup works (no "too many connections" error)

### Testing Checklist

**Functional tests:**
```bash
# Test 1: Start app
streamlit run app/streamlit_app.py
# → Should open browser at http://localhost:8501

# Test 2: Compare CLI vs Streamlit output
python -m app.services.analytics_service --dashboard
# → Note quality scores

# Then in Streamlit Analytics page
# → Verify same scores appear

# Test 3: Cache behavior
# Click between pages multiple times
# → Second+ loads should be instant (< 100ms)

# Test 4: Connection limits
# Refresh page 20 times rapidly
# → Should NOT see "too many connections" error

# Test 5: Error handling
# Stop PostgreSQL: docker stop devto_postgres
# Refresh Streamlit page
# → Should show friendly error, not crash

# Test 6: Data validation
# Check page source for any Python exceptions
# → Should be clean (no red error boxes)
```

**Performance tests:**
```python
# Add to sidebar for debugging
if st.sidebar.checkbox("Show Performance Stats"):
    import time
    start = time.time()
    data = load_quality_scores(engine)
    elapsed = time.time() - start
    st.sidebar.metric("Load Time", f"{elapsed:.2f}s")
    st.sidebar.metric("Cache Hit?", "Yes" if elapsed < 0.1 else "No")
```

## Bonus Features (Optional)

- Dark mode toggle
- Export charts as PNG
- Real-time updates (auto-refresh every 5 min)
- Comparison mode (compare 2 articles)
- Filters persist across pages (session state)

Generate a complete, production-ready Streamlit dashboard that showcases the CLI services with a beautiful web interface.
