# Streamlit Dashboard Guide

## Overview

The DEV.to Analytics Streamlit Dashboard provides an interactive web interface to visualize your content performance metrics, theme distribution, engagement trends, and comment sentiment.

## Features

### 🏠 Main Dashboard (Welcome Page)
- Quick overview statistics
- Database connection status
- Cache management
- Navigation to specialized pages

### 📊 Analytics Page
- **Quality Score Rankings**: Top articles by quality score with interactive charts
- **Read Time Analysis**: Correlation between reading time and completion rates
- **Engagement Breakdown**: Reactions and comments distribution
- **Data Export**: Download CSV files for further analysis

### 🧬 Author DNA Page
- **Theme Distribution**: Visualize content themes with pie charts
- **Performance by Theme**: Compare metrics across different themes
- **Article Classifications**: Browse articles by theme with confidence scores
- **Strategic Insights**: Recommendations based on theme performance

### 📈 Evolution Page
- **Global Trends**: Track overall engagement over time (7-365 days)
- **Individual Article Tracking**: Monitor single article performance
- **Growth Velocity**: Daily changes in views and reactions
- **Time Series Analysis**: Interactive line charts with dual axes

### 💬 Sentiment Page
- **Sentiment Distribution**: Positive, neutral, and negative comment breakdown
- **Recent Comments Feed**: Browse comments with sentiment scores
- **Polarity vs Subjectivity**: Scatter plot analysis
- **Spam Detection**: Identify potential spam with adjustable threshold

## Installation

### 1. Install Dependencies

```bash
# Install core requirements (if not already installed)
pip install -r app/requirements.txt

# Install Streamlit-specific dependencies
pip install -r app/requirements-streamlit.txt
```

### 2. Verify Database Connection

Ensure PostgreSQL is running and accessible:

```bash
# Check Docker containers
docker-compose ps

# Expected: devto_postgres should be "Up (healthy)"
```

### 3. Verify Data Availability

Run the sync worker to populate data:

```bash
# Full sync (recommended for first run)
python3 scripts/sync_worker.py

# Or manual sync
python3 -m app.services.devto_service --full
```

## Usage

### Starting the Dashboard

```bash
# From project root
streamlit run app/streamlit_app.py
```

The dashboard will open automatically in your default browser at: **http://localhost:8501**

### Alternative: Specify Port

```bash
streamlit run app/streamlit_app.py --server.port 8502
```

### Alternative: Run in Background

```bash
nohup streamlit run app/streamlit_app.py > logs/streamlit.log 2>&1 &
```

## Navigation

Use the sidebar to navigate between pages:

1. **📊 Analytics** - Performance metrics and quality scores
2. **🧬 Author DNA** - Theme classification and insights
3. **📈 Evolution** - Engagement trends over time
4. **💬 Sentiment** - Comment sentiment analysis

## Features Explained

### Caching Strategy

The dashboard uses two types of caching:

- **`@st.cache_resource`**: Caches database engine (persistent across reruns)
- **`@st.cache_data(ttl=300)`**: Caches data for 5 minutes

To refresh data:
- Click the "🔄 Refresh Data" button in the sidebar
- Or wait 5 minutes for automatic cache expiration

### Async Handling

The dashboard uses `nest_asyncio` to enable nested event loops, allowing Streamlit (which runs synchronously) to call async database services.

**Technical Pattern:**
```python
import nest_asyncio
nest_asyncio.apply()

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
```

### Data Validation

All data loading functions include validation:
- Check for empty DataFrames
- Validate required fields exist
- Handle missing values gracefully
- Display user-friendly error messages

### Error Handling

Errors are displayed in the UI with:
- User-friendly main message
- Expandable technical details
- Suggestions for resolution

## Configuration

### Environment Variables

The dashboard uses the same `.env` configuration as other services:

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=devto_analytics
POSTGRES_USER=devto
POSTGRES_PASSWORD=your_password
```

### Streamlit Configuration (Optional)

Create `.streamlit/config.toml` for custom settings:

```toml
[theme]
primaryColor = "#667eea"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"

[server]
port = 8501
enableCORS = false
enableXsrfProtection = true
maxUploadSize = 200
```

## Performance Tips

### 1. Optimize Query Limits

Use sidebar sliders to limit data:
- Analytics: 10-100 articles
- Comments: 10-200 comments
- Evolution: 7-365 days

### 2. Clear Cache Regularly

If data seems stale:
1. Click "🔄 Refresh Data" in sidebar
2. Or use "Clear Cache" button on main page

### 3. Use Pagination

Large datasets use pagination:
- 10 items per page default
- Use page number input to navigate

### 4. Export Data for Heavy Analysis

For complex analysis, export CSV and use external tools:
- Python/pandas
- Excel
- Tableau/PowerBI

## Troubleshooting

### Dashboard Won't Start

**Error:** `ModuleNotFoundError: No module named 'streamlit'`

**Solution:**
```bash
pip install -r app/requirements-streamlit.txt
```

### No Data Displayed

**Error:** "No data available. Please run sync worker first"

**Solution:**
```bash
python3 scripts/sync_worker.py
```

### Database Connection Failed

**Error:** "Database Disconnected"

**Solution:**
1. Check Docker containers: `docker-compose ps`
2. Restart if needed: `docker-compose restart postgres`
3. Verify `.env` configuration

### Async Loop Errors

**Error:** `RuntimeError: This event loop is already running`

**Solution:** Already handled by `nest_asyncio.apply()` in code. If you still see this:
```bash
pip install --upgrade nest-asyncio
```

### Chart Not Rendering

**Error:** Blank chart or error message

**Cause:** Empty or invalid data

**Solution:**
1. Check data with expander "📋 View Raw Data"
2. Verify database has records for selected time range
3. Adjust filters (theme, date range, sentiment)

### Slow Performance

**Symptoms:** Pages take >10 seconds to load

**Solutions:**
1. Reduce data limits (sliders in sidebar)
2. Use shorter time ranges for evolution
3. Clear cache and reload
4. Check database performance: `docker stats devto_postgres`

## Data Freshness

The dashboard displays cached data (5 minutes TTL). For real-time updates:

1. **Manual Sync:**
   ```bash
   python3 scripts/sync_worker.py
   ```

2. **Automated Sync (Cron):**
   ```bash
   # Edit crontab
   crontab -e
   
   # Add hourly sync
   0 * * * * cd /root/projects/devto_githubcopilotcli_challenge && ./venv/bin/python3 scripts/sync_worker.py >> logs/sync_worker.log 2>&1
   ```

3. **Clear Dashboard Cache:**
   - Click "🔄 Refresh Data" in any page sidebar
   - Or "Clear Cache" button on main page

## API Integration

The dashboard reuses the same async services as the REST API:

| Service | Used In Pages | Methods Called |
|---------|---------------|----------------|
| AnalyticsService | Analytics | get_quality_scores(), get_read_time_analysis(), get_reaction_breakdown() |
| ThemeService | Author DNA | generate_dna_report(), classify_article() |
| NLPService | Sentiment | get_sentiment_stats() |
| Direct SQL | Evolution | article_metrics, daily_analytics queries |

## Security Considerations

### 1. Local Deployment Only

The dashboard is designed for **local development**. For production:

- Add authentication (Streamlit has no built-in auth)
- Use HTTPS with SSL/TLS
- Restrict network access
- Consider Streamlit Cloud with GitHub SSO

### 2. Database Credentials

Never commit `.env` to version control:
```bash
# .gitignore already includes
.env
```

### 3. API Keys

If extending to call external APIs from dashboard:
- Store keys in `.env`
- Never hardcode in Python files
- Use `st.secrets` for Streamlit Cloud

## Advanced Usage

### Custom Metrics

Add custom metrics by extending services:

1. Add method to service (e.g., `app/services/analytics_service.py`)
2. Create data loading function in page:
   ```python
   @st.cache_data(ttl=300)
   def load_custom_metric():
       async def _load():
           service = AnalyticsService(engine=get_cached_engine())
           return await service.your_custom_method()
       return run_async(_load())
   ```
3. Display with Plotly chart

### Custom Charts

Use Plotly Express or Graph Objects:

```python
import plotly.express as px

fig = px.bar(df, x='category', y='value', color='group')
st.plotly_chart(fig, use_container_width=True)
```

### Multi-Page Apps

Add more pages by creating files in `app/pages/`:

```
app/pages/
├── 1_📊_Analytics.py
├── 2_🧬_Author_DNA.py
├── 3_📈_Evolution.py
├── 4_💬_Sentiment.py
└── 5_🎯_Your_New_Page.py  # Add here
```

Streamlit automatically detects and adds to sidebar.

## Comparison with Other Tools

### vs Apache Superset

**Streamlit Advantages:**
- Faster to develop custom visualizations
- Full Python access to services
- No SQL required for users
- Interactive widgets (sliders, filters)

**Superset Advantages:**
- Better for SQL power users
- Role-based access control
- Better performance on large datasets
- Dashboard sharing and embedding

**Recommendation:** Use both!
- Superset for executive dashboards
- Streamlit for exploratory analysis

### vs FastAPI REST API

**Streamlit Advantages:**
- Immediate visual feedback
- No need for frontend framework
- Interactive filtering and pagination

**API Advantages:**
- Machine-readable JSON responses
- Integration with external systems
- Better for automation

**Recommendation:** Use both!
- API for integrations
- Streamlit for human users

## Deployment Options

### 1. Local Development (Current)

```bash
streamlit run app/streamlit_app.py
```

Access: http://localhost:8501

### 2. Docker Container

Create `Dockerfile.streamlit`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY app/requirements.txt app/requirements-streamlit.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-streamlit.txt

COPY app/ ./app/
COPY .env .env

EXPOSE 8501

CMD ["streamlit", "run", "app/streamlit_app.py", "--server.address", "0.0.0.0"]
```

Add to `docker-compose.yml`:

```yaml
streamlit:
  build:
    context: .
    dockerfile: Dockerfile.streamlit
  container_name: devto_streamlit
  restart: unless-stopped
  ports:
    - "8501:8501"
  environment:
    POSTGRES_HOST: postgres
    POSTGRES_PORT: 5432
    POSTGRES_DB: ${POSTGRES_DB}
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  depends_on:
    postgres:
      condition: service_healthy
  networks:
    - devto_network
```

### 3. Streamlit Cloud (Free Hosting)

1. Push code to GitHub
2. Go to https://share.streamlit.io
3. Connect GitHub repository
4. Deploy `app/streamlit_app.py`
5. Add secrets via Streamlit Cloud UI (PostgreSQL credentials)

**Note:** Requires public GitHub repo or Streamlit Teams

### 4. Behind Caddy Reverse Proxy

Add to `Caddyfile`:

```
dashboard-app.local {
    reverse_proxy localhost:8501
}
```

Add to `/etc/hosts`:
```
127.0.0.1 dashboard-app.local
```

Restart Caddy:
```bash
sudo systemctl reload caddy
```

Access: http://dashboard-app.local

## Maintenance

### Update Dependencies

```bash
# Check for updates
pip list --outdated

# Update specific package
pip install --upgrade streamlit

# Update all (use with caution)
pip install --upgrade -r app/requirements-streamlit.txt
```

### Monitor Logs

When running in background:

```bash
# View live logs
tail -f logs/streamlit.log

# Search for errors
grep ERROR logs/streamlit.log
```

### Backup Configuration

```bash
# Backup Streamlit config
cp -r .streamlit .streamlit.backup

# Backup custom pages
tar -czf pages_backup.tar.gz app/pages/
```

## Support

### Getting Help

1. **Check Logs:** Look for error messages
2. **Review Documentation:** Re-read relevant sections
3. **Test Database:** Verify PostgreSQL connectivity
4. **Simplify:** Start with main page, then add pages one by one

### Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| ModuleNotFoundError | `pip install -r app/requirements-streamlit.txt` |
| Empty charts | Run `python3 scripts/sync_worker.py` |
| Slow performance | Reduce data limits in sidebar sliders |
| Cache issues | Click "🔄 Refresh Data" button |
| Connection refused | Check `docker-compose ps` and restart services |

## Resources

- **Streamlit Docs:** https://docs.streamlit.io
- **Plotly Docs:** https://plotly.com/python/
- **Pandas Docs:** https://pandas.pydata.org/docs/
- **Project README:** README.md
- **API Docs:** API_DOCUMENTATION.md
- **Technical Docs:** TECHNICAL_DOCUMENTATION.md

## Next Steps

1. **Explore All Pages:** Navigate through all 4 specialized pages
2. **Customize Filters:** Adjust sliders and selectors to your needs
3. **Export Data:** Download CSV files for external analysis
4. **Add Custom Pages:** Create new pages for specific use cases
5. **Schedule Syncs:** Set up cron jobs for automated data refresh
6. **Share Insights:** Take screenshots or export PDFs (Ctrl+P in browser)

---

**Generated with GitHub Copilot CLI** - AI-assisted development for the DEV.to Analytics Platform
