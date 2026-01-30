"""
DEV.to Analytics Dashboard - Main Streamlit Application

A web-based analytics dashboard that visualizes DEV.to article performance,
theme distribution, engagement trends, and sentiment analysis.

Uses existing async services for data fetching.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
import asyncio
from datetime import datetime
from typing import Optional

try:
    import nest_asyncio
    nest_asyncio.apply()
except (ValueError, RuntimeError):
    pass

# Page configuration
st.set_page_config(
    page_title="DEV.to Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .high-quality { color: #28a745; font-weight: bold; }
    .medium-quality { color: #ffc107; font-weight: bold; }
    .low-quality { color: #dc3545; font-weight: bold; }
</style>
""", unsafe_allow_html=True)


def run_async(coro):
    """Helper to run async functions in Streamlit's sync context"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@st.cache_resource
def get_cached_engine():
    """Get or create cached database engine (reused across reruns)"""
    from app.db.connection import get_async_engine
    return get_async_engine()


@st.cache_data(ttl=300)
def load_quick_stats():
    """Load quick statistics for dashboard cards"""
    async def _load():
        from app.services.analytics_service import AnalyticsService
        from app.services.theme_service import ThemeService
        
        engine = get_cached_engine()
        
        try:
            analytics = AnalyticsService(engine=engine)
            theme = ThemeService(engine=engine)
            
            # Get quality scores
            quality_data = await analytics.get_quality_scores(limit=100)
            
            # Get DNA report
            dna_data = await theme.generate_dna_report()
            
            stats = {
                'total_articles': len(quality_data) if quality_data else 0,
                'avg_quality': sum(q.get('quality_score', 0) for q in quality_data) / len(quality_data) if quality_data else 0,
                'total_themes': len(dna_data.get('moods', [])) if dna_data else 0,
                'total_views': sum(q.get('views_90d', 0) for q in quality_data) if quality_data else 0
            }
            
            return stats
        except Exception as e:
            st.error(f"Error loading stats: {str(e)}")
            return {
                'total_articles': 0,
                'avg_quality': 0,
                'total_themes': 0,
                'total_views': 0
            }
    
    return run_async(_load())


@st.cache_data(ttl=60)
def check_database_connection() -> tuple[bool, str]:
    """Check if database connection is working"""
    async def _check():
        try:
            engine = get_cached_engine()
            async with engine.connect() as conn:
                result = await conn.execute("SELECT 1")
                return True, "Connected"
        except Exception as e:
            return False, str(e)
    
    return run_async(_check())


def main():
    """Main application entry point"""
    
    # Header
    st.markdown('<h1 class="main-header">📊 DEV.to Analytics Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Real-time insights into content performance, engagement, and reader sentiment</p>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.title("🎯 Navigation")
        st.info("Use the pages above to explore different metrics")
        
        st.divider()
        
        # Database connection status
        st.subheader("🔌 Connection Status")
        is_connected, message = check_database_connection()
        
        if is_connected:
            st.success("✅ Database Connected")
        else:
            st.error("❌ Database Disconnected")
            with st.expander("Error Details"):
                st.code(message)
        
        st.divider()
        
        # Cache management
        st.subheader("🔄 Cache Management")
        if st.button("Clear Cache", help="Refresh all data from database"):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.success("Cache cleared! Page will reload.")
            st.rerun()
        
        st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        st.divider()
        
        # Quick links
        st.subheader("🔗 Quick Links")
        st.markdown("""
        - [API Docs](http://localhost:8000/docs)
        - [Superset](http://localhost:8088)
        - [DbGate](http://localhost:3000)
        - [GitHub Repo](https://github.com/pcescato/devto_githubcopilotcli_challenge)
        """)
    
    # Main content
    st.header("📈 Overview")
    
    # Load stats with spinner
    with st.spinner("Loading statistics..."):
        stats = load_quick_stats()
    
    # Metric cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📝 Total Articles",
            value=stats['total_articles'],
            delta=None,
            help="Total number of published articles"
        )
    
    with col2:
        avg_quality = stats['avg_quality']
        quality_color = "high" if avg_quality >= 70 else "medium" if avg_quality >= 50 else "low"
        st.metric(
            label="⭐ Avg Quality Score",
            value=f"{avg_quality:.1f}",
            delta=None,
            help="Average quality score (0-100 scale)"
        )
    
    with col3:
        st.metric(
            label="🧬 Content Themes",
            value=stats['total_themes'],
            delta=None,
            help="Number of distinct content themes"
        )
    
    with col4:
        total_views = stats['total_views']
        views_formatted = f"{total_views:,}" if total_views < 1000000 else f"{total_views/1000:.1f}K"
        st.metric(
            label="👁️ Total Views (90d)",
            value=views_formatted,
            delta=None,
            help="Total views across all articles (last 90 days)"
        )
    
    st.divider()
    
    # Welcome content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("🚀 Welcome to DEV.to Analytics")
        st.markdown("""
        This dashboard provides comprehensive analytics for your DEV.to content:
        
        - **📊 Analytics**: Quality scores, read time analysis, and engagement metrics
        - **🧬 Author DNA**: Theme distribution and performance by content category
        - **📈 Evolution**: Track engagement trends and growth over time
        - **💬 Sentiment**: Analyze comment sentiment and detect spam
        
        Navigate using the sidebar to explore each section. Data is cached for 5 minutes
        and automatically refreshes to ensure you always have up-to-date insights.
        """)
        
        st.info("💡 **Tip:** Use the pages in the sidebar to dive deep into specific metrics!")
    
    with col2:
        st.subheader("📚 Quick Stats")
        
        if stats['total_articles'] > 0:
            st.success(f"✅ {stats['total_articles']} articles analyzed")
            st.info(f"📊 {stats['total_themes']} themes identified")
            st.warning(f"👁️ {stats['total_views']:,} total views")
        else:
            st.warning("⚠️ No data available yet. Run data sync first:")
            st.code("python3 scripts/sync_worker.py", language="bash")
    
    st.divider()
    
    # Features overview
    st.subheader("✨ Dashboard Features")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        **📊 Analytics**
        - Quality score rankings
        - Read time distribution
        - Reaction breakdown
        - Interactive charts
        """)
    
    with col2:
        st.markdown("""
        **🧬 Author DNA**
        - Theme distribution
        - Performance by theme
        - Content insights
        - Strategic recommendations
        """)
    
    with col3:
        st.markdown("""
        **📈 Evolution & Sentiment**
        - Engagement trends
        - Follower correlation
        - Comment sentiment
        - Spam detection
        """)
    
    st.divider()
    
    # System information
    with st.expander("ℹ️ System Information"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Database:**")
            st.code(f"""
Host: localhost
Port: 5432
Database: devto_analytics
Connection: {"Active" if is_connected else "Inactive"}
            """)
        
        with col2:
            st.markdown("**Application:**")
            st.code(f"""
Framework: Streamlit
Cache TTL: 5 minutes
Async Engine: PostgreSQL + asyncpg
Last Refresh: {datetime.now().strftime('%H:%M:%S')}
            """)


if __name__ == "__main__":
    main()
