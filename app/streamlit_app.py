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

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import asyncio
from datetime import datetime
from typing import Optional

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


@st.cache_resource
def get_cached_loop():
    """Get or create a cached event loop (persistent across reruns)"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Loop is closed")
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def run_async(coro):
    """Helper to run async functions using cached event loop"""
    loop = get_cached_loop()
    return loop.run_until_complete(coro)


@st.cache_resource
def get_cached_engine():
    """Get or create cached database engine (reused across reruns)"""
    import os
    from sqlalchemy.ext.asyncio import create_async_engine
    
    # Ensure we have a loop before creating the engine
    loop = get_cached_loop()
    
    # Get database URL from environment
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    database = os.getenv('POSTGRES_DB', 'devto_analytics')
    user = os.getenv('POSTGRES_USER', 'devto')
    password = os.getenv('POSTGRES_PASSWORD', 'devto_secure_password')
    
    db_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    
    engine = create_async_engine(
        db_url,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        echo=False,
        future=True
    )
    
    return engine


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
                'total_themes': len(dna_data.get('themes', [])) if dna_data else 0,
                'total_views': sum(q.get('total_views', 0) for q in quality_data) if quality_data else 0
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
            from sqlalchemy import text
            engine = get_cached_engine()
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
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
    
    # Recent Activity Section
    st.markdown("---")
    
    try:
        import pandas as pd
        from app.services.analytics_service import AnalyticsService
        
        # Load data using existing cache system
        async def _load_activity():
            engine = get_cached_engine()
            service = AnalyticsService(engine)
            data = await service.get_recent_activity()
            return data
        
        activity_data = run_async(_load_activity())
        
        if activity_data:
            df = pd.DataFrame(activity_data)
            
            # Format snapshot time range for header
            snapshot_time = df['snapshot_time'].iloc[0]
            previous_time = df['previous_snapshot_time'].iloc[0]
            
            # Format: "Sun. 1st, 2026 16:00 - 20:00"
            day = snapshot_time.day
            if 4 <= day <= 20 or 24 <= day <= 30:
                suffix = "th"
            else:
                suffix = ["st", "nd", "rd"][day % 10 - 1]
            
            day_abbr = snapshot_time.strftime('%a')
            prev_hour = previous_time.hour
            latest_hour = snapshot_time.hour
            header_time = f"{day_abbr}. {day}{suffix}, {snapshot_time.year} {prev_hour:02d}:00 - {latest_hour:02d}:00"
            
            st.subheader(f"Most recent views - {header_time}")
            
            # Format columns
            df['Article'] = df['title']
            
            df['Views'] = df['delta_views'].apply(
                lambda x: f"+{x} view" if x == 1 else f"+{x} views"
            )
            
            df['Reactions'] = df['delta_reactions'].apply(
                lambda x: "no reaction" if x == 0 else (f"+{x} reaction" if x == 1 else f"+{x} reactions")
            )
            
            df['Comments'] = df['delta_comments'].apply(
                lambda x: "no comment" if x == 0 else (f"+{x} comment" if x == 1 else f"+{x} comments")
            )
            
            # Display simple table
            st.dataframe(
                df[['Article', 'Views', 'Reactions', 'Comments']],
                hide_index=True,
                width='stretch',
            )
        else:
            st.info("No recent activity")
            
    except Exception as e:
        st.error(f"Could not load recent activity: {str(e)}")
    
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
