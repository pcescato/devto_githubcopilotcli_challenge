"""
Analytics Page - Quality Scores, Read Time, and Engagement Metrics

Visualizes article performance using the AnalyticsService.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
import asyncio
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import List, Dict, Any

st.set_page_config(
    page_title="Analytics - DEV.to Dashboard",
    page_icon="📊",
    layout="wide"
)


def run_async(coro):
    """Helper to run async functions"""
    # Use the existing event loop or create one that stays alive
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Run the coroutine without closing the loop
    return loop.run_until_complete(coro)


@st.cache_resource
def get_cached_engine():
    """Get cached database engine"""
    import os
    from sqlalchemy.ext.asyncio import create_async_engine
    
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
def load_quality_scores(limit: int = 50) -> pd.DataFrame:
    """Load quality score data"""
    async def _load():
        from app.services.analytics_service import AnalyticsService
        
        engine = get_cached_engine()
        service = AnalyticsService(engine=engine)
        
        try:
            data = await service.get_quality_scores(limit=limit)
            
            if not data or len(data) == 0:
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            
            # Ensure required fields exist
            required_fields = ['article_id', 'title', 'quality_score']
            if not all(field in df.columns for field in required_fields):
                st.error(f"Missing required fields. Available: {list(df.columns)}")
                return pd.DataFrame()
            
            # Truncate long titles
            df['title_short'] = df['title'].apply(lambda x: x[:50] + '...' if len(x) > 50 else x)
            
            return df
        except Exception as e:
            st.error(f"Error loading quality scores: {str(e)}")
            return pd.DataFrame()
    
    return run_async(_load())


@st.cache_data(ttl=300)
def load_read_time_analysis(limit: int = 50) -> pd.DataFrame:
    """Load read time analysis data"""
    async def _load():
        from app.services.analytics_service import AnalyticsService
        
        engine = get_cached_engine()
        service = AnalyticsService(engine=engine)
        
        try:
            data = await service.get_read_time_analysis(limit=limit)
            
            if not data or len(data) == 0:
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            df['title_short'] = df['title'].apply(lambda x: x[:40] + '...' if len(x) > 40 else x)
            
            return df
        except Exception as e:
            st.error(f"Error loading read time analysis: {str(e)}")
            return pd.DataFrame()
    
    return run_async(_load())


@st.cache_data(ttl=300)
def load_reaction_breakdown() -> pd.DataFrame:
    """Load reaction breakdown data"""
    async def _load():
        from app.services.analytics_service import AnalyticsService
        
        engine = get_cached_engine()
        service = AnalyticsService(engine=engine)
        
        try:
            data = await service.get_reaction_breakdown()
            
            if not data or len(data) == 0:
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            return df
        except Exception as e:
            st.error(f"Error loading reaction breakdown: {str(e)}")
            return pd.DataFrame()
    
    return run_async(_load())


def main():
    st.title("📊 Analytics Dashboard")
    st.markdown("Comprehensive performance metrics for your DEV.to articles")
    
    # Sidebar controls
    with st.sidebar:
        st.subheader("🎛️ Controls")
        
        limit = st.slider(
            "Number of articles to analyze",
            min_value=10,
            max_value=100,
            value=50,
            step=10,
            help="Select how many articles to include in the analysis"
        )
        
        chart_height = st.slider(
            "Chart height",
            min_value=400,
            max_value=800,
            value=500,
            step=50,
            help="Adjust the height of charts"
        )
        
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.success("Data refreshed!")
            st.rerun()
    
    # Load data
    with st.spinner("Loading analytics data..."):
        quality_df = load_quality_scores(limit=limit)
        readtime_df = load_read_time_analysis(limit=limit)
        reaction_df = load_reaction_breakdown()
    
    # Check for empty data
    if quality_df.empty:
        st.warning("⚠️ No data available. Please run the sync worker first:")
        st.code("python3 scripts/sync_worker.py", language="bash")
        return
    
    # === SECTION 1: Quality Scores ===
    st.header("⭐ Quality Score Rankings")
    st.markdown("Articles ranked by quality score (completion × 0.7 + engagement × 1.5)")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        avg_quality = quality_df['quality_score'].mean()
        st.metric(
            "Average Quality Score",
            f"{avg_quality:.1f}",
            help="Mean quality across all articles"
        )
    
    with col2:
        high_quality_count = len(quality_df[quality_df['quality_score'] >= 70])
        st.metric(
            "High Quality Articles",
            high_quality_count,
            help="Articles with quality score ≥ 70"
        )
    
    with col3:
        total_views = quality_df['total_views'].sum()
        st.metric(
            "Total Views (90d)",
            f"{total_views:,}",
            help="Sum of views across all articles"
        )
    
    # Quality score distribution
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Top Articles by Quality Score")
        
        # Horizontal bar chart
        top_10 = quality_df.nlargest(10, 'quality_score')
        
        fig = px.bar(
            top_10,
            x='quality_score',
            y='title_short',
            orientation='h',
            color='quality_score',
            color_continuous_scale=['#dc3545', '#ffc107', '#28a745'],
            labels={'quality_score': 'Quality Score', 'title_short': 'Article'},
            height=chart_height
        )
        
        fig.update_layout(
            yaxis={'categoryorder': 'total ascending'},
            showlegend=False,
            coloraxis_showscale=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Quality Distribution")
        
        # Create quality categories
        quality_df['quality_category'] = pd.cut(
            quality_df['quality_score'],
            bins=[0, 40, 60, 100],
            labels=['Low (0-40)', 'Medium (40-60)', 'High (60-100)']
        )
        
        category_counts = quality_df['quality_category'].value_counts()
        
        fig = px.pie(
            values=category_counts.values,
            names=category_counts.index,
            color=category_counts.index,
            color_discrete_map={
                'Low (0-40)': '#dc3545',
                'Medium (40-60)': '#ffc107',
                'High (60-100)': '#28a745'
            },
            height=400
        )
        
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # === SECTION 2: Read Time Analysis ===
    st.header("⏱️ Read Time Analysis")
    st.markdown("Understanding how reading time correlates with engagement")
    
    if not readtime_df.empty:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            avg_read_time = readtime_df['reading_time_minutes'].mean()
            st.metric(
                "Avg Reading Time",
                f"{avg_read_time:.1f} min",
                help="Average reading time across articles"
            )
        
        with col2:
            avg_completion = readtime_df['completion_percent'].mean()
            st.metric(
                "Avg Completion Rate",
                f"{avg_completion:.1f}%",
                help="Average percentage of articles read"
            )
        
        with col3:
            total_hours = readtime_df['total_hours'].sum()
            st.metric(
                "Total Reader Hours",
                f"{total_hours:,.0f}h",
                help="Total time readers spent on content"
            )
        
        # Scatter plot: reading time vs completion
        st.subheader("Reading Time vs Completion Rate")
        
        fig = px.scatter(
            readtime_df,
            x='reading_time_minutes',
            y='completion_percent',
            size='total_views',
            color='completion_percent',
            hover_data=['title'],
            color_continuous_scale='Viridis',
            labels={
                'reading_time_minutes': 'Reading Time (minutes)',
                'completion_percent': 'Completion Rate (%)'
            },
            height=500
        )
        
        fig.update_traces(marker=dict(line=dict(width=1, color='DarkSlateGrey')))
        st.plotly_chart(fig, use_container_width=True)
        
        # Data table
        with st.expander("📋 View Detailed Data"):
            display_df = readtime_df[['title', 'reading_time_minutes', 'avg_read_seconds', 'completion_percent', 'total_hours']]
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No read time data available")
    
    st.divider()
    
    # === SECTION 3: Engagement Metrics ===
    st.header("💬 Engagement Breakdown")
    st.markdown("Reactions and comments distribution across articles")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Quality Score Components")
        
        # Show breakdown of quality score components
        components_df = quality_df[['title_short', 'completion_percent', 'engagement_percent', 'quality_score']].head(15)
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name='Completion (×0.7)',
            x=components_df['title_short'],
            y=components_df['completion_percent'] * 0.7,
            marker_color='#667eea'
        ))
        
        fig.add_trace(go.Bar(
            name='Engagement (×1.5)',
            x=components_df['title_short'],
            y=components_df['engagement_percent'] * 1.5,
            marker_color='#764ba2'
        ))
        
        fig.update_layout(
            barmode='stack',
            height=500,
            xaxis={'tickangle': -45},
            yaxis={'title': 'Quality Score Contribution'},
            legend={'orientation': 'h', 'y': 1.1}
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Engagement Rate Distribution")
        
        # Histogram of engagement rates
        fig = px.histogram(
            quality_df,
            x='engagement_percent',
            nbins=20,
            color_discrete_sequence=['#667eea'],
            labels={'engagement_percent': 'Engagement Rate (%)'},
            height=500
        )
        
        fig.update_layout(
            showlegend=False,
            yaxis={'title': 'Number of Articles'}
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Reaction breakdown if available
    if not reaction_df.empty:
        st.subheader("📊 Reaction Breakdown")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Bar chart of reactions by article
            top_reactions = reaction_df.nlargest(15, 'reactions')
            
            fig = px.bar(
                top_reactions,
                x='reactions',
                y='title',
                orientation='h',
                color='reactions',
                color_continuous_scale='Blues',
                labels={'reactions': 'Total Reactions', 'title': 'Article'},
                height=500
            )
            
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Summary statistics
            st.markdown("**Summary Statistics**")
            st.metric("Total Reactions", f"{reaction_df['reactions'].sum():,}")
            st.metric("Average per Article", f"{reaction_df['reactions'].mean():.1f}")
            st.metric("Median Reactions", f"{reaction_df['reactions'].median():.0f}")
            
            highest = reaction_df.nlargest(1, 'reactions').iloc[0]
            st.info(f"🏆 **Top Article:**\n\n{highest['title'][:60]}...\n\n{highest['reactions']} reactions")
    
    st.divider()
    
    # Data export
    st.subheader("📥 Export Data")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        csv = quality_df.to_csv(index=False)
        st.download_button(
            label="Download Quality Scores (CSV)",
            data=csv,
            file_name="quality_scores.csv",
            mime="text/csv"
        )
    
    with col2:
        if not readtime_df.empty:
            csv = readtime_df.to_csv(index=False)
            st.download_button(
                label="Download Read Time Data (CSV)",
                data=csv,
                file_name="read_time_analysis.csv",
                mime="text/csv"
            )
    
    with col3:
        if not reaction_df.empty:
            csv = reaction_df.to_csv(index=False)
            st.download_button(
                label="Download Reactions (CSV)",
                data=csv,
                file_name="reactions.csv",
                mime="text/csv"
            )


if __name__ == "__main__":
    main()
