"""
📉 Sismographe - Master-Detail Article Pulse Analysis

Master View: Browse all articles with summary metrics
Detail View: Analyze activity pulses (deltas) for selected article
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from typing import Optional

from app.services.analytics_service import create_analytics_service


# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="Sismographe | Dev.to Analytics",
    page_icon="📉",
    layout="wide"
)

st.title("📉 Sismographe - Activity Pulses")
st.markdown("**Master-Detail view**: Select an article to visualize its traffic spikes")


# ============================================================================
# DATA LOADING
# ============================================================================

@st.cache_data(ttl=300, show_spinner="Loading articles...")
def load_articles_summary():
    """Load summary of all articles for master view"""
    import asyncio
    
    async def _load():
        service = await create_analytics_service()
        return await service.get_all_articles_summary()
    
    return asyncio.run(_load())


def load_article_pulses(article_id: int):
    """Load pulse data for specific article"""
    import asyncio
    
    async def _load():
        service = await create_analytics_service()
        return await service.get_article_pulses(article_id)
    
    return asyncio.run(_load())


# ============================================================================
# MASTER VIEW - ARTICLE SUMMARY
# ============================================================================

st.subheader("📚 All Articles")
st.markdown("Click on a row to view detailed pulse analysis")

# Load articles
try:
    articles_data = load_articles_summary()
    
    if not articles_data:
        st.warning("No articles found in the database.")
        st.stop()
    
    # Convert to DataFrame
    df_articles = pd.DataFrame(articles_data)
    
    # Reorder columns for better display
    df_articles = df_articles[['title', 'total_views', 'total_reactions', 'total_comments', 'article_id']]
    
    # Display searchable dataframe with single-row selection
    event = st.dataframe(
        df_articles,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "title": st.column_config.TextColumn("Article Title", width="large"),
            "total_views": st.column_config.NumberColumn("Views", format="%d"),
            "total_reactions": st.column_config.NumberColumn("Reactions", format="%d"),
            "total_comments": st.column_config.NumberColumn("Comments", format="%d"),
            "article_id": st.column_config.NumberColumn("ID", format="%d"),
        }
    )
    
    # Handle selection
    selected_rows = event.selection.rows if event and event.selection else []
    
    if not selected_rows:
        st.info("👆 Click a row in the table above to see activity pulses")
        st.stop()
    
    # Get selected article
    selected_idx = selected_rows[0]
    selected_article = df_articles.iloc[selected_idx]
    article_id = int(selected_article['article_id'])
    article_title = selected_article['title']
    
except Exception as e:
    st.error(f"Error loading articles: {e}")
    st.stop()


# ============================================================================
# DETAIL VIEW - PULSE ANALYSIS
# ============================================================================

st.divider()
st.subheader(f"📉 Pulse Analysis: {article_title}")

# Load pulses for selected article
try:
    with st.spinner("Loading pulse data..."):
        pulses_data = load_article_pulses(article_id)
    
    if not pulses_data:
        st.warning(f"No pulse data available for article {article_id}")
        st.stop()
    
    # Convert to DataFrame
    df_pulses = pd.DataFrame(pulses_data)
    
    # Ensure datetime format
    df_pulses['collected_at'] = pd.to_datetime(df_pulses['collected_at'])
    
    # Sort by date
    df_pulses = df_pulses.sort_values('collected_at')
    
    # ========================================================================
    # PULSE INSIGHT CARD
    # ========================================================================
    
    st.markdown("### 💥 Pulse Insight")
    
    # Find highest spikes
    max_views_spike = df_pulses['delta_views'].max()
    max_reactions_spike = df_pulses['delta_reactions'].max()
    max_comments_spike = df_pulses['delta_comments'].max()
    
    # Get dates of highest spikes
    max_views_date = df_pulses.loc[df_pulses['delta_views'] == max_views_spike, 'collected_at'].iloc[0]
    max_reactions_date = df_pulses.loc[df_pulses['delta_reactions'] == max_reactions_spike, 'collected_at'].iloc[0]
    max_comments_date = df_pulses.loc[df_pulses['delta_comments'] == max_comments_spike, 'collected_at'].iloc[0]
    
    # Display insights in columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "📊 Highest Views Spike",
            f"+{max_views_spike:,}",
            delta=f"on {max_views_date.strftime('%Y-%m-%d %H:%M')}"
        )
    
    with col2:
        st.metric(
            "❤️ Highest Reactions Spike",
            f"+{max_reactions_spike:,}",
            delta=f"on {max_reactions_date.strftime('%Y-%m-%d %H:%M')}"
        )
    
    with col3:
        st.metric(
            "💬 Highest Comments Spike",
            f"+{max_comments_spike:,}",
            delta=f"on {max_comments_date.strftime('%Y-%m-%d %H:%M')}"
        )
    
    st.divider()
    
    # ========================================================================
    # PULSE CHARTS
    # ========================================================================
    
    st.markdown("### 📈 Pulse Charts")
    
    # Chart 1: Delta Views
    fig_views = go.Figure()
    fig_views.add_trace(go.Scatter(
        x=df_pulses['collected_at'],
        y=df_pulses['delta_views'],
        mode='lines+markers',
        name='Delta Views',
        line=dict(color='#1f77b4', width=2),
        marker=dict(size=6),
        fill='tozeroy',
        fillcolor='rgba(31, 119, 180, 0.2)'
    ))
    fig_views.update_layout(
        title="📊 Views Activity Pulse",
        xaxis_title="Time",
        yaxis_title="Delta Views",
        height=300,
        hovermode='x unified',
        showlegend=False
    )
    st.plotly_chart(fig_views, use_container_width=True)
    
    # Chart 2: Delta Reactions
    fig_reactions = go.Figure()
    fig_reactions.add_trace(go.Scatter(
        x=df_pulses['collected_at'],
        y=df_pulses['delta_reactions'],
        mode='lines+markers',
        name='Delta Reactions',
        line=dict(color='#ff7f0e', width=2),
        marker=dict(size=6),
        fill='tozeroy',
        fillcolor='rgba(255, 127, 14, 0.2)'
    ))
    fig_reactions.update_layout(
        title="❤️ Reactions Activity Pulse",
        xaxis_title="Time",
        yaxis_title="Delta Reactions",
        height=300,
        hovermode='x unified',
        showlegend=False
    )
    st.plotly_chart(fig_reactions, use_container_width=True)
    
    # Chart 3: Delta Comments
    fig_comments = go.Figure()
    fig_comments.add_trace(go.Scatter(
        x=df_pulses['collected_at'],
        y=df_pulses['delta_comments'],
        mode='lines+markers',
        name='Delta Comments',
        line=dict(color='#2ca02c', width=2),
        marker=dict(size=6),
        fill='tozeroy',
        fillcolor='rgba(44, 160, 44, 0.2)'
    ))
    fig_comments.update_layout(
        title="💬 Comments Activity Pulse",
        xaxis_title="Time",
        yaxis_title="Delta Comments",
        height=300,
        hovermode='x unified',
        showlegend=False
    )
    st.plotly_chart(fig_comments, use_container_width=True)
    
    # ========================================================================
    # DATA TABLE
    # ========================================================================
    
    with st.expander("📋 View Raw Pulse Data"):
        st.dataframe(
            df_pulses[['collected_at', 'views', 'reactions', 'comments', 'delta_views', 'delta_reactions', 'delta_comments']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "collected_at": st.column_config.DatetimeColumn("Timestamp", format="YYYY-MM-DD HH:mm"),
                "views": st.column_config.NumberColumn("Views", format="%d"),
                "reactions": st.column_config.NumberColumn("Reactions", format="%d"),
                "comments": st.column_config.NumberColumn("Comments", format="%d"),
                "delta_views": st.column_config.NumberColumn("Δ Views", format="%+d"),
                "delta_reactions": st.column_config.NumberColumn("Δ Reactions", format="%+d"),
                "delta_comments": st.column_config.NumberColumn("Δ Comments", format="%+d"),
            }
        )

except Exception as e:
    st.error(f"Error loading pulse data: {e}")
    import traceback
    st.code(traceback.format_exc())
