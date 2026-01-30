"""
Evolution Page - Engagement Trends and Historical Analysis

Visualizes how engagement metrics evolve over time using sismograph data.
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
from datetime import datetime, timedelta
from typing import List, Dict, Any

try:
    import nest_asyncio
    nest_asyncio.apply()
except (ValueError, RuntimeError):
    pass

st.set_page_config(
    page_title="Evolution - DEV.to Dashboard",
    page_icon="📈",
    layout="wide"
)


def run_async(coro):
    """Helper to run async functions"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@st.cache_resource
def get_cached_engine():
    """Get cached database engine"""
    from app.db.connection import get_async_engine
    return get_async_engine()


@st.cache_data(ttl=300)
def load_engagement_evolution(article_id: int) -> pd.DataFrame:
    """Load engagement evolution for a specific article"""
    async def _load():
        from sqlalchemy import select
        from app.db.tables import article_metrics
        
        engine = get_cached_engine()
        
        try:
            async with engine.connect() as conn:
                query = select(
                    article_metrics.c.collected_at,
                    article_metrics.c.views,
                    article_metrics.c.reactions,
                    article_metrics.c.comments
                ).where(
                    article_metrics.c.article_id == article_id
                ).order_by(article_metrics.c.collected_at)
                
                result = await conn.execute(query)
                rows = result.mappings().all()
                
                if not rows:
                    return pd.DataFrame()
                
                df = pd.DataFrame([dict(row) for row in rows])
                
                # Calculate engagement rate
                df['engagement_rate'] = (df['reactions'] / df['views'].replace(0, 1) * 100).round(2)
                
                # Calculate deltas
                df['views_delta'] = df['views'].diff().fillna(0)
                df['reactions_delta'] = df['reactions'].diff().fillna(0)
                
                return df
        except Exception as e:
            st.error(f"Error loading evolution data: {str(e)}")
            return pd.DataFrame()
    
    return run_async(_load())


@st.cache_data(ttl=300)
def load_all_articles_list() -> List[Dict[str, Any]]:
    """Load list of all articles for selection"""
    async def _load():
        from sqlalchemy import select, func
        from app.db.tables import article_metrics
        
        engine = get_cached_engine()
        
        try:
            async with engine.connect() as conn:
                # Get latest snapshot for each article
                subquery = select(
                    article_metrics.c.article_id,
                    func.max(article_metrics.c.collected_at).label('max_collected')
                ).group_by(article_metrics.c.article_id).subquery()
                
                query = select(
                    article_metrics.c.article_id,
                    article_metrics.c.title,
                    article_metrics.c.views,
                    article_metrics.c.reactions,
                    article_metrics.c.published_at
                ).select_from(
                    article_metrics.join(
                        subquery,
                        (article_metrics.c.article_id == subquery.c.article_id) &
                        (article_metrics.c.collected_at == subquery.c.max_collected)
                    )
                ).order_by(article_metrics.c.views.desc())
                
                result = await conn.execute(query)
                rows = result.mappings().all()
                
                return [dict(row) for row in rows]
        except Exception as e:
            st.error(f"Error loading articles: {str(e)}")
            return []
    
    return run_async(_load())


@st.cache_data(ttl=300)
def load_global_trends(days: int = 90) -> pd.DataFrame:
    """Load global engagement trends"""
    async def _load():
        from sqlalchemy import select, func
        from app.db.tables import daily_analytics
        
        engine = get_cached_engine()
        
        try:
            async with engine.connect() as conn:
                cutoff_date = datetime.now().date() - timedelta(days=days)
                
                query = select(
                    daily_analytics.c.date,
                    func.sum(daily_analytics.c.views).label('total_views'),
                    func.sum(daily_analytics.c.reactions).label('total_reactions'),
                    func.sum(daily_analytics.c.comments).label('total_comments')
                ).where(
                    daily_analytics.c.date >= cutoff_date
                ).group_by(
                    daily_analytics.c.date
                ).order_by(daily_analytics.c.date)
                
                result = await conn.execute(query)
                rows = result.mappings().all()
                
                if not rows:
                    return pd.DataFrame()
                
                df = pd.DataFrame([dict(row) for row in rows])
                
                # Calculate engagement rate
                df['engagement_rate'] = (df['total_reactions'] / df['total_views'].replace(0, 1) * 100).round(2)
                
                return df
        except Exception as e:
            st.error(f"Error loading global trends: {str(e)}")
            return pd.DataFrame()
    
    return run_async(_load())


def main():
    st.title("📈 Evolution Analysis")
    st.markdown("Track how your content performance evolves over time")
    
    # Sidebar controls
    with st.sidebar:
        st.subheader("🎛️ Controls")
        
        view_mode = st.radio(
            "View Mode",
            options=["Global Trends", "Individual Article"],
            help="Choose between global analytics or single article tracking"
        )
        
        if view_mode == "Global Trends":
            days_range = st.slider(
                "Time Range (days)",
                min_value=7,
                max_value=365,
                value=90,
                step=7,
                help="Select time range for global trends"
            )
        
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.success("Data refreshed!")
            st.rerun()
        
        st.divider()
        
        st.subheader("📖 About Evolution")
        st.info("""
        **Evolution Analysis** tracks:
        
        - 📊 View growth over time
        - 💬 Reaction accumulation
        - 📈 Engagement rate changes
        - 🎯 Performance patterns
        
        Use this to identify:
        - Viral moments
        - Steady performers
        - Content decay
        """)
    
    # === MODE 1: Global Trends ===
    if view_mode == "Global Trends":
        st.header("🌍 Global Engagement Trends")
        st.markdown(f"Analyzing activity over the last {days_range} days")
        
        with st.spinner("Loading global trends..."):
            trends_df = load_global_trends(days=days_range)
        
        if trends_df.empty:
            st.warning("⚠️ No historical data available. Run sync with --rich flag:")
            st.code("python3 -m app.services.devto_service --rich", language="bash")
            return
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_views = trends_df['total_views'].sum()
            st.metric(
                "Total Views",
                f"{total_views:,}",
                help="Sum of all views in selected period"
            )
        
        with col2:
            total_reactions = trends_df['total_reactions'].sum()
            st.metric(
                "Total Reactions",
                f"{total_reactions:,}",
                help="Sum of all reactions in selected period"
            )
        
        with col3:
            avg_daily_views = trends_df['total_views'].mean()
            st.metric(
                "Avg Daily Views",
                f"{avg_daily_views:.0f}",
                help="Average views per day"
            )
        
        with col4:
            avg_engagement = trends_df['engagement_rate'].mean()
            st.metric(
                "Avg Engagement",
                f"{avg_engagement:.2f}%",
                help="Average engagement rate"
            )
        
        st.divider()
        
        # Time series chart
        st.subheader("📊 Views & Reactions Over Time")
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=trends_df['date'],
            y=trends_df['total_views'],
            name='Views',
            mode='lines+markers',
            line=dict(color='#667eea', width=2),
            yaxis='y1'
        ))
        
        fig.add_trace(go.Scatter(
            x=trends_df['date'],
            y=trends_df['total_reactions'],
            name='Reactions',
            mode='lines+markers',
            line=dict(color='#764ba2', width=2),
            yaxis='y2'
        ))
        
        fig.update_layout(
            height=500,
            hovermode='x unified',
            yaxis=dict(title='Views', side='left'),
            yaxis2=dict(title='Reactions', side='right', overlaying='y'),
            legend=dict(orientation='h', y=1.1)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Engagement rate trend
        st.subheader("💡 Engagement Rate Trend")
        
        fig = px.area(
            trends_df,
            x='date',
            y='engagement_rate',
            color_discrete_sequence=['#28a745'],
            labels={'date': 'Date', 'engagement_rate': 'Engagement Rate (%)'},
            height=400
        )
        
        fig.update_traces(line=dict(width=2))
        st.plotly_chart(fig, use_container_width=True)
        
        # Weekly aggregation
        st.subheader("📅 Weekly Summary")
        
        trends_df['week'] = pd.to_datetime(trends_df['date']).dt.to_period('W').astype(str)
        
        weekly_df = trends_df.groupby('week').agg({
            'total_views': 'sum',
            'total_reactions': 'sum',
            'total_comments': 'sum',
            'engagement_rate': 'mean'
        }).reset_index()
        
        fig = px.bar(
            weekly_df,
            x='week',
            y=['total_views', 'total_reactions'],
            barmode='group',
            labels={'value': 'Count', 'week': 'Week'},
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # === MODE 2: Individual Article ===
    else:
        st.header("📄 Individual Article Evolution")
        st.markdown("Track a single article's performance over time")
        
        # Load article list
        with st.spinner("Loading articles..."):
            articles = load_all_articles_list()
        
        if not articles:
            st.warning("⚠️ No articles found. Sync data first:")
            st.code("python3 -m app.services.devto_service --snapshot", language="bash")
            return
        
        # Article selector
        article_options = {
            f"{a['title'][:60]}... (ID: {a['article_id']}, {a['views']} views)": a['article_id']
            for a in articles
        }
        
        selected_article_label = st.selectbox(
            "Select Article",
            options=list(article_options.keys()),
            help="Choose an article to analyze its evolution"
        )
        
        selected_article_id = article_options[selected_article_label]
        
        # Load evolution data
        with st.spinner(f"Loading evolution for article {selected_article_id}..."):
            evolution_df = load_engagement_evolution(selected_article_id)
        
        if evolution_df.empty:
            st.warning(f"⚠️ No historical data for article {selected_article_id}")
            return
        
        # Article info
        selected_article = next(a for a in articles if a['article_id'] == selected_article_id)
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader(selected_article['title'])
        
        with col2:
            st.metric("Snapshots", len(evolution_df))
        
        # Current stats
        col1, col2, col3, col4 = st.columns(4)
        
        latest = evolution_df.iloc[-1]
        
        with col1:
            st.metric(
                "Current Views",
                f"{int(latest['views']):,}",
                delta=f"+{int(latest['views_delta'])}" if latest['views_delta'] > 0 else None
            )
        
        with col2:
            st.metric(
                "Current Reactions",
                f"{int(latest['reactions'])}",
                delta=f"+{int(latest['reactions_delta'])}" if latest['reactions_delta'] > 0 else None
            )
        
        with col3:
            st.metric(
                "Current Comments",
                f"{int(latest['comments'])}"
            )
        
        with col4:
            st.metric(
                "Engagement Rate",
                f"{latest['engagement_rate']:.2f}%"
            )
        
        st.divider()
        
        # Evolution charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("👁️ Views Evolution")
            
            fig = px.line(
                evolution_df,
                x='collected_at',
                y='views',
                markers=True,
                color_discrete_sequence=['#667eea'],
                labels={'collected_at': 'Date', 'views': 'Views'},
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("💬 Reactions Evolution")
            
            fig = px.line(
                evolution_df,
                x='collected_at',
                y='reactions',
                markers=True,
                color_discrete_sequence=['#764ba2'],
                labels={'collected_at': 'Date', 'reactions': 'Reactions'},
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Engagement rate over time
        st.subheader("📈 Engagement Rate Over Time")
        
        fig = px.area(
            evolution_df,
            x='collected_at',
            y='engagement_rate',
            color_discrete_sequence=['#28a745'],
            labels={'collected_at': 'Date', 'engagement_rate': 'Engagement Rate (%)'},
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Growth velocity
        st.subheader("🚀 Growth Velocity")
        st.markdown("Daily changes in views and reactions")
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=evolution_df['collected_at'],
            y=evolution_df['views_delta'],
            name='Views Delta',
            marker_color='#667eea'
        ))
        
        fig.add_trace(go.Bar(
            x=evolution_df['collected_at'],
            y=evolution_df['reactions_delta'],
            name='Reactions Delta',
            marker_color='#764ba2',
            yaxis='y2'
        ))
        
        fig.update_layout(
            height=400,
            yaxis=dict(title='Views Change'),
            yaxis2=dict(title='Reactions Change', overlaying='y', side='right'),
            legend=dict(orientation='h', y=1.1)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Data table
        with st.expander("📋 View Raw Data"):
            display_df = evolution_df[['collected_at', 'views', 'reactions', 'comments', 'engagement_rate', 'views_delta', 'reactions_delta']]
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # Export
    st.subheader("📥 Export Data")
    
    if view_mode == "Global Trends" and not trends_df.empty:
        csv = trends_df.to_csv(index=False)
        st.download_button(
            label="Download Global Trends (CSV)",
            data=csv,
            file_name=f"global_trends_{days_range}d.csv",
            mime="text/csv"
        )
    elif view_mode == "Individual Article" and not evolution_df.empty:
        csv = evolution_df.to_csv(index=False)
        st.download_button(
            label="Download Article Evolution (CSV)",
            data=csv,
            file_name=f"article_{selected_article_id}_evolution.csv",
            mime="text/csv"
        )


if __name__ == "__main__":
    main()
