"""
Sentiment Page - Comment Sentiment Analysis and Spam Detection

Visualizes comment sentiment distribution and identifies spam patterns.
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

st.set_page_config(
    page_title="Sentiment - DEV.to Dashboard",
    page_icon="💬",
    layout="wide"
)


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
    """Get cached database engine"""
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
def load_sentiment_stats() -> Dict[str, Any]:
    """Load sentiment statistics"""
    async def _load():
        from app.services.nlp_service import NLPService
        
        engine = get_cached_engine()
        service = NLPService(engine=engine)
        
        try:
            data = await service.get_sentiment_stats()
            return data
        except Exception as e:
            st.error(f"Error loading sentiment stats: {str(e)}")
            return {'total': 0, 'moods': []}
    
    return run_async(_load())


@st.cache_data(ttl=300)
def load_recent_comments(limit: int = 50) -> pd.DataFrame:
    """Load recent comments with sentiment"""
    async def _load():
        from sqlalchemy import select
        from app.db.tables import comments, comment_insights, article_metrics
        
        engine = get_cached_engine()
        
        try:
            async with engine.connect() as conn:
                query = select(
                    comments.c.comment_id,
                    comments.c.article_id,
                    article_metrics.c.title.label('article_title'),
                    comments.c.author_username,
                    comments.c.body_text,
                    comments.c.created_at,
                    comment_insights.c.sentiment_score,
                    comment_insights.c.mood,
                    comment_insights.c.is_spam
                ).select_from(
                    comments
                    .outerjoin(
                        comment_insights,
                        comments.c.comment_id == comment_insights.c.comment_id
                    )
                    .outerjoin(
                        article_metrics,
                        comments.c.article_id == article_metrics.c.article_id
                    )
                ).order_by(comments.c.created_at.desc()).limit(limit)
                
                result = await conn.execute(query)
                rows = result.mappings().all()
                
                if not rows:
                    return pd.DataFrame()
                
                df = pd.DataFrame([dict(row) for row in rows])
                
                # Use mood if available, otherwise classify from sentiment_score
                def get_sentiment(row):
                    if pd.notna(row.get('mood')):
                        # mood is already classified, just clean it up
                        mood_str = str(row['mood']).lower()
                        if 'positif' in mood_str or 'positive' in mood_str:
                            return 'Positive'
                        elif 'négatif' in mood_str or 'negative' in mood_str:
                            return 'Negative'
                        elif 'neutre' in mood_str or 'neutral' in mood_str:
                            return 'Neutral'
                    
                    # Fallback to sentiment_score classification
                    score = row.get('sentiment_score')
                    if pd.isna(score):
                        return 'Unknown'
                    elif score >= 0.3:
                        return 'Positive'
                    elif score <= -0.2:
                        return 'Negative'
                    else:
                        return 'Neutral'
                
                df['sentiment'] = df.apply(get_sentiment, axis=1)
                
                # Truncate text
                df['text_preview'] = df['body_text'].apply(
                    lambda x: x[:100] + '...' if isinstance(x, str) and len(x) > 100 else x
                )
                
                return df
        except Exception as e:
            st.error(f"Error loading comments: {str(e)}")
            return pd.DataFrame()
    
    return run_async(_load())


@st.cache_data(ttl=300)
def load_spam_candidates() -> pd.DataFrame:
    """Load potential spam comments"""
    async def _load():
        from sqlalchemy import select
        from app.db.tables import comments, comment_insights, article_metrics
        
        engine = get_cached_engine()
        
        try:
            async with engine.connect() as conn:
                query = select(
                    comments.c.comment_id,
                    comments.c.article_id,
                    article_metrics.c.title.label('article_title'),
                    comments.c.author_username,
                    comments.c.body_text,
                    comment_insights.c.is_spam,
                    comment_insights.c.sentiment_score
                ).select_from(
                    comments
                    .join(
                        comment_insights,
                        comments.c.comment_id == comment_insights.c.comment_id
                    )
                    .outerjoin(
                        article_metrics,
                        comments.c.article_id == article_metrics.c.article_id
                    )
                ).where(
                    comment_insights.c.is_spam == True
                ).order_by(comments.c.created_at.desc())
                
                result = await conn.execute(query)
                rows = result.mappings().all()
                
                if not rows:
                    return pd.DataFrame()
                
                df = pd.DataFrame([dict(row) for row in rows])
                
                df['text_preview'] = df['body_text'].apply(
                    lambda x: x[:80] + '...' if isinstance(x, str) and len(x) > 80 else x
                )
                
                df['text_preview'] = df['body_text'].apply(
                    lambda x: x[:80] + '...' if isinstance(x, str) and len(x) > 80 else x
                )
                
                return df
        except Exception as e:
            st.error(f"Error loading spam candidates: {str(e)}")
            return pd.DataFrame()
    
    return run_async(_load())


def main():
    st.title("💬 Sentiment Analysis")
    st.markdown("Understand comment sentiment and detect potential spam")
    
    # Sidebar controls
    with st.sidebar:
        st.subheader("🎛️ Controls")
        
        comment_limit = st.slider(
            "Recent comments to analyze",
            min_value=10,
            max_value=200,
            value=50,
            step=10
        )
        
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.success("Data refreshed!")
            st.rerun()
        
        st.divider()
        
        st.subheader("📖 About Sentiment")
        st.info("""
        **Sentiment Analysis** uses:
        
        - 🎭 VADER Sentiment Score: -1.0 to +1.0
        - 😊 Mood Classification: Positive/Neutral/Negative
        - 🚫 Spam Detection: Keyword-based filtering
        
        **Thresholds:**
        - Positive: ≥ 0.3
        - Negative: ≤ -0.2
        - Neutral: Between -0.2 and 0.3
        """)
    
    # Load data
    with st.spinner("Analyzing sentiment..."):
        sentiment_stats = load_sentiment_stats()
        comments_df = load_recent_comments(limit=comment_limit)
        spam_df = load_spam_candidates()
    
    # Check for empty data
    if sentiment_stats['total'] == 0:
        st.warning("⚠️ No sentiment data available. Run NLP analysis first:")
        st.code("python3 -m app.services.nlp_service --analyze-all", language="bash")
        return
    
    # === SECTION 1: Overview ===
    st.header("📊 Sentiment Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    moods = sentiment_stats.get('moods', [])
    
    with col1:
        st.metric(
            "Total Comments",
            sentiment_stats['total'],
            help="Total comments analyzed"
        )
    
    with col2:
        positive_count = next((m['count'] for m in moods if m['mood'] == 'positive'), 0)
        positive_pct = (positive_count / sentiment_stats['total'] * 100) if sentiment_stats['total'] > 0 else 0
        st.metric(
            "Positive",
            positive_count,
            delta=f"{positive_pct:.1f}%",
            help="Comments with positive sentiment"
        )
    
    with col3:
        negative_count = next((m['count'] for m in moods if m['mood'] == 'negative'), 0)
        negative_pct = (negative_count / sentiment_stats['total'] * 100) if sentiment_stats['total'] > 0 else 0
        st.metric(
            "Negative",
            negative_count,
            delta=f"-{negative_pct:.1f}%" if negative_count > 0 else "0%",
            delta_color="inverse",
            help="Comments with negative sentiment"
        )
    
    with col4:
        spam_count = len(spam_df) if not spam_df.empty else 0
        st.metric(
            "Potential Spam",
            spam_count,
            help="Comments detected as spam"
        )
    
    st.divider()
    
    # === SECTION 2: Sentiment Distribution ===
    st.header("🎭 Sentiment Distribution")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Sentiment Breakdown")
        
        if moods:
            # Prepare data
            sentiment_data = []
            for mood in moods:
                pct = (mood['count'] / sentiment_stats['total'] * 100) if sentiment_stats['total'] > 0 else 0
                sentiment_data.append({
                    'Sentiment': mood['mood'].capitalize(),
                    'Count': mood['count'],
                    'Percentage': pct
                })
            
            sentiment_df = pd.DataFrame(sentiment_data)
            
            # Pie chart
            fig = px.pie(
                sentiment_df,
                values='Count',
                names='Sentiment',
                color='Sentiment',
                color_discrete_map={
                    'Positive': '#28a745',
                    'Neutral': '#ffc107',
                    'Negative': '#dc3545'
                },
                hole=0.4,
                height=400
            )
            
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
            
            # Summary table
            st.dataframe(sentiment_df, use_container_width=True, hide_index=True)
    
    with col2:
        st.subheader("Average Polarity by Sentiment")
        
        if moods:
            # Bar chart
            polarity_data = []
            for mood in moods:
                polarity_data.append({
                    'Sentiment': mood['mood'].capitalize(),
                    'Avg Polarity': mood.get('avg_polarity', 0)
                })
            
            polarity_df = pd.DataFrame(polarity_data)
            
            fig = px.bar(
                polarity_df,
                x='Sentiment',
                y='Avg Polarity',
                color='Avg Polarity',
                color_continuous_scale=['#dc3545', '#ffc107', '#28a745'],
                labels={'Avg Polarity': 'Average Polarity Score'},
                height=400
            )
            
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
            # Insight
            st.info(f"""
            **Sentiment Health Score:** {positive_pct:.1f}% positive
            
            {"✅ Great! Most comments are positive." if positive_pct > 60 else
             "⚠️ Consider engaging more with commenters." if positive_pct > 40 else
             "🚨 High negativity detected. Review recent content."}
            """)
    
    st.divider()
    
    # === SECTION 3: Recent Comments ===
    st.header("📝 Recent Comments")
    st.markdown(f"Last {comment_limit} comments with sentiment analysis")
    
    if not comments_df.empty:
        # Filter controls
        col1, col2, col3 = st.columns(3)
        
        with col1:
            sentiment_filter = st.multiselect(
                "Filter by sentiment",
                options=['Positive', 'Neutral', 'Negative', 'Unknown'],
                default=['Positive', 'Neutral', 'Negative', 'Unknown']
            )
        
        # Apply filter
        filtered_comments = comments_df[comments_df['sentiment'].isin(sentiment_filter)]
        
        # Stats for filtered data
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Filtered Comments", len(filtered_comments))
        
        with col2:
            avg_polarity = filtered_comments['polarity'].mean()
            st.metric("Avg Polarity", f"{avg_polarity:.2f}" if not pd.isna(avg_polarity) else "N/A")
        
        with col3:
            avg_subjectivity = filtered_comments['subjectivity'].mean()
            st.metric("Avg Subjectivity", f"{avg_subjectivity:.2f}" if not pd.isna(avg_subjectivity) else "N/A")
        
        # Polarity vs Subjectivity scatter
        st.subheader("📊 Polarity vs Subjectivity")
        
        valid_data = filtered_comments.dropna(subset=['polarity', 'subjectivity'])
        
        if not valid_data.empty:
            fig = px.scatter(
                valid_data,
                x='polarity',
                y='subjectivity',
                color='sentiment',
                color_discrete_map={
                    'Positive': '#28a745',
                    'Neutral': '#ffc107',
                    'Negative': '#dc3545',
                    'Unknown': '#6c757d'
                },
                hover_data=['author_username', 'text_preview'],
                labels={'polarity': 'Polarity', 'subjectivity': 'Subjectivity'},
                height=500
            )
            
            # Add quadrant lines
            fig.add_hline(y=0.5, line_dash="dash", line_color="gray", opacity=0.5)
            fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Comment list
        st.subheader("💬 Comment Feed")
        
        # Pagination
        items_per_page = 10
        total_pages = (len(filtered_comments) + items_per_page - 1) // items_per_page
        
        page = st.number_input(
            "Page",
            min_value=1,
            max_value=max(1, total_pages),
            value=1,
            step=1
        )
        
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        
        page_comments = filtered_comments.iloc[start_idx:end_idx]
        
        # Display comments
        for idx, comment in page_comments.iterrows():
            sentiment_emoji = {
                'Positive': '😊',
                'Neutral': '😐',
                'Negative': '😞',
                'Unknown': '❓'
            }.get(comment['sentiment'], '❓')
            
            with st.expander(f"{sentiment_emoji} {comment['author_username']} on {comment['article_title'][:50]}...", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Comment:**")
                    st.write(comment['text'])
                    
                    st.caption(f"Posted: {comment['created_at']}")
                
                with col2:
                    st.metric("Sentiment", comment['sentiment'])
                    
                    if not pd.isna(comment['polarity']):
                        st.metric("Polarity", f"{comment['polarity']:.2f}")
                    
                    if not pd.isna(comment['subjectivity']):
                        st.metric("Subjectivity", f"{comment['subjectivity']:.2f}")
                    
                    if not pd.isna(comment['spam_score']):
                        spam_risk = "🚨 High" if comment['spam_score'] >= spam_threshold else "✅ Low"
                        st.metric("Spam Risk", spam_risk)
        
        st.caption(f"Showing {start_idx + 1}-{min(end_idx, len(filtered_comments))} of {len(filtered_comments)} comments")
    else:
        st.info("No comments available")
    
    st.divider()
    
    # === SECTION 4: Spam Detection ===
    st.header("🚫 Spam Detection")
    st.markdown(f"Comments with spam score ≥ {spam_threshold}")
    
    if not spam_df.empty:
        st.warning(f"⚠️ Found {len(spam_df)} potential spam comments")
        
        # Spam list
        for idx, spam in spam_df.iterrows():
            with st.expander(f"🚨 {spam['author_username']} (Score: {spam['spam_score']:.2f})", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Article:** {spam['article_title']}")
                    st.markdown(f"**Comment:**")
                    st.write(spam['text'])
                
                with col2:
                    st.metric("Spam Score", f"{spam['spam_score']:.2f}")
                    st.metric("Comment ID", spam['comment_id'])
                    
                    st.button("Mark as Spam", key=f"spam_{idx}", disabled=True, help="Feature not implemented")
                    st.button("Mark as Safe", key=f"safe_{idx}", disabled=True, help="Feature not implemented")
    else:
        st.success("✅ No spam detected with current threshold!")
    
    st.divider()
    
    # Export
    st.subheader("📥 Export Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if not comments_df.empty:
            csv = comments_df.to_csv(index=False)
            st.download_button(
                label="Download Comments (CSV)",
                data=csv,
                file_name="comments_sentiment.csv",
                mime="text/csv"
            )
    
    with col2:
        if not spam_df.empty:
            csv = spam_df.to_csv(index=False)
            st.download_button(
                label="Download Spam Candidates (CSV)",
                data=csv,
                file_name="spam_candidates.csv",
                mime="text/csv"
            )


if __name__ == "__main__":
    main()
