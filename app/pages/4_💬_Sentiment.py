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
        from sqlalchemy import select, func
        from app.db.tables import comments, comment_insights, article_metrics
        
        engine = get_cached_engine()
        
        try:
            async with engine.connect() as conn:
                # Subquery to get latest article title per article_id
                latest_article_subq = (
                    select(
                        article_metrics.c.article_id,
                        article_metrics.c.title,
                        func.row_number().over(
                            partition_by=article_metrics.c.article_id,
                            order_by=article_metrics.c.collected_at.desc()
                        ).label('rn')
                    )
                    .subquery()
                )
                
                query = select(
                    comments.c.comment_id,
                    comments.c.article_id,
                    # Use article_title from comments table first, fallback to article_metrics
                    func.coalesce(
                        comments.c.article_title,
                        latest_article_subq.c.title
                    ).label('article_title'),
                    comments.c.author_username,
                    # Fallback chain: body_text -> body_markdown -> body_html
                    func.coalesce(
                        comments.c.body_text,
                        comments.c.body_markdown,
                        comments.c.body_html
                    ).label('body_text'),
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
                        latest_article_subq,
                        (comments.c.article_id == latest_article_subq.c.article_id) &
                        (latest_article_subq.c.rn == 1)
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
        from sqlalchemy import select, func
        from app.db.tables import comments, comment_insights, article_metrics
        
        engine = get_cached_engine()
        
        try:
            async with engine.connect() as conn:
                # Subquery to get latest article title per article_id
                latest_article_subq = (
                    select(
                        article_metrics.c.article_id,
                        article_metrics.c.title,
                        func.row_number().over(
                            partition_by=article_metrics.c.article_id,
                            order_by=article_metrics.c.collected_at.desc()
                        ).label('rn')
                    )
                    .subquery()
                )
                
                query = select(
                    comments.c.comment_id,
                    comments.c.article_id,
                    # Use article_title from comments table first, fallback to article_metrics
                    func.coalesce(
                        comments.c.article_title,
                        latest_article_subq.c.title
                    ).label('article_title'),
                    comments.c.author_username,
                    # Fallback chain: body_text -> body_markdown -> body_html
                    func.coalesce(
                        comments.c.body_text,
                        comments.c.body_markdown,
                        comments.c.body_html
                    ).label('body_text'),
                    comment_insights.c.is_spam,
                    comment_insights.c.sentiment_score
                ).select_from(
                    comments
                    .join(
                        comment_insights,
                        comments.c.comment_id == comment_insights.c.comment_id
                    )
                    .outerjoin(
                        latest_article_subq,
                        (comments.c.article_id == latest_article_subq.c.article_id) &
                        (latest_article_subq.c.rn == 1)
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
        st.subheader("Sentiment Volume by Category")
        
        if moods:
            # Bar chart showing count by mood
            mood_data = []
            for mood in moods:
                mood_data.append({
                    'Sentiment': mood['mood'].capitalize(),
                    'Count': mood['count'],
                    'Percentage': mood['percentage']
                })
            
            mood_df = pd.DataFrame(mood_data)
            
            fig = px.bar(
                mood_df,
                x='Sentiment',
                y='Count',
                color='Sentiment',
                color_discrete_map={
                    'Positive': '#28a745',
                    'Positif': '#28a745',
                    'Neutral': '#ffc107',
                    'Neutre': '#ffc107',
                    'Negative': '#dc3545',
                    'Négatif': '#dc3545'
                },
                text='Percentage',
                labels={'Count': 'Number of Comments'},
                height=400
            )
            
            fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
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
        
        # Debug info
        if len(filtered_comments) != len(comments_df):
            st.info(f"🔍 Filtered from {len(comments_df)} total comments to {len(filtered_comments)} matching your criteria")
        
        # Stats for filtered data
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Filtered Comments", len(filtered_comments))
        
        with col2:
            avg_sentiment = filtered_comments['sentiment_score'].mean()
            st.metric("Avg Sentiment Score", f"{avg_sentiment:.2f}" if not pd.isna(avg_sentiment) else "N/A")
        
        with col3:
            sentiment_counts = filtered_comments['sentiment'].value_counts()
            most_common = sentiment_counts.index[0] if not sentiment_counts.empty else "N/A"
            st.metric("Most Common", most_common)
        
        # Sentiment Score Distribution
        st.subheader("📊 Sentiment Score Distribution")
        
        valid_data = filtered_comments.dropna(subset=['sentiment_score'])
        
        if not valid_data.empty:
            fig = px.histogram(
                valid_data,
                x='sentiment_score',
                color='sentiment',
                color_discrete_map={
                    'Positive': '#28a745',
                    'Neutral': '#ffc107',
                    'Negative': '#dc3545',
                    'Unknown': '#6c757d'
                },
                nbins=20,
                labels={'sentiment_score': 'VADER Sentiment Score (-1.0 to +1.0)'},
                height=400
            )
            
            # Add threshold lines
            fig.add_vline(x=0.3, line_dash="dash", line_color="green", opacity=0.5, 
                         annotation_text="Positive threshold")
            fig.add_vline(x=-0.2, line_dash="dash", line_color="red", opacity=0.5,
                         annotation_text="Negative threshold")
            
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
            
            # Use text_preview if body_text is None
            comment_text = comment.get('body_text') or comment.get('text_preview', '[No comment text]')
            
            with st.expander(f"{sentiment_emoji} {comment['author_username']} on {comment['article_title'][:50]}...", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Comment:**")
                    if comment_text and comment_text != '[No comment text]':
                        st.write(comment_text)
                    else:
                        st.info("💬 Comment text not available (may not have been synced yet)")
                    
                    st.caption(f"Posted: {comment['created_at']}")
                
                with col2:
                    st.metric("Sentiment", comment['sentiment'])
                    
                    if not pd.isna(comment.get('sentiment_score')):
                        st.metric("VADER Score", f"{comment['sentiment_score']:.2f}")
                    
                    if comment.get('is_spam', False):
                        st.metric("Spam Status", "🚨 Flagged")
                    else:
                        st.metric("Spam Status", "✅ Clean")
        
        st.caption(f"Showing {start_idx + 1}-{min(end_idx, len(filtered_comments))} of {len(filtered_comments)} comments")
    else:
        st.info("No comments available")
    
    st.divider()
    
    # === SECTION 4: Spam Detection ===
    st.header("🚫 Spam Detection")
    st.markdown("Comments flagged as spam")
    
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
