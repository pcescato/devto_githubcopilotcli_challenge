"""
Author DNA Page - Theme Distribution and Performance Analysis

Visualizes content theme classification and performance metrics by theme.
"""

import streamlit as st
import asyncio
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import List, Dict, Any

try:
    import nest_asyncio
    nest_asyncio.apply()
except (ValueError, RuntimeError):
    pass

st.set_page_config(
    page_title="Author DNA - DEV.to Dashboard",
    page_icon="🧬",
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
def load_dna_report() -> Dict[str, Any]:
    """Load Author DNA report"""
    async def _load():
        from app.services.theme_service import ThemeService
        
        engine = get_cached_engine()
        service = ThemeService(engine=engine)
        
        try:
            data = await service.generate_dna_report()
            return data
        except Exception as e:
            st.error(f"Error loading DNA report: {str(e)}")
            return {'total': 0, 'moods': []}
    
    return run_async(_load())


@st.cache_data(ttl=300)
def load_article_classifications() -> pd.DataFrame:
    """Load individual article classifications"""
    async def _load():
        from sqlalchemy import select, func
        from app.db.tables import article_theme_mapping, author_themes, article_metrics
        
        engine = get_cached_engine()
        
        try:
            async with engine.connect() as conn:
                # Get latest article snapshot with theme
                query = select(
                    article_metrics.c.article_id,
                    article_metrics.c.title,
                    article_metrics.c.views,
                    article_metrics.c.reactions,
                    author_themes.c.theme_name,
                    article_theme_mapping.c.confidence_score,
                    article_theme_mapping.c.matched_keywords
                ).select_from(
                    article_metrics
                    .join(
                        article_theme_mapping,
                        article_metrics.c.article_id == article_theme_mapping.c.article_id
                    )
                    .join(
                        author_themes,
                        article_theme_mapping.c.theme_id == author_themes.c.id
                    )
                ).where(
                    article_metrics.c.collected_at.in_(
                        select(func.max(article_metrics.c.collected_at))
                        .where(
                            article_metrics.c.article_id == article_theme_mapping.c.article_id
                        )
                        .scalar_subquery()
                    )
                ).order_by(article_metrics.c.views.desc())
                
                result = await conn.execute(query)
                rows = result.mappings().all()
                
                if not rows:
                    return pd.DataFrame()
                
                df = pd.DataFrame([dict(row) for row in rows])
                
                # Calculate engagement
                df['engagement_rate'] = (df['reactions'] / df['views'] * 100).round(2)
                
                return df
        except Exception as e:
            st.error(f"Error loading classifications: {str(e)}")
            return pd.DataFrame()
    
    return run_async(_load())


def main():
    st.title("🧬 Author DNA Analysis")
    st.markdown("Discover your content themes and their performance characteristics")
    
    # Sidebar controls
    with st.sidebar:
        st.subheader("🎛️ Controls")
        
        if st.button("🔄 Refresh DNA Report"):
            st.cache_data.clear()
            st.success("DNA report refreshed!")
            st.rerun()
        
        st.divider()
        
        st.subheader("📖 About Author DNA")
        st.info("""
        **Author DNA** classifies your articles into themes based on keyword matching.
        
        **Themes:**
        - 🔧 Expertise Tech
        - 👤 Human & Career
        - 🌱 Culture & Agile
        - 🎨 Free Exploration
        
        The algorithm uses:
        - Keyword matching
        - Confidence scoring
        - Performance tracking
        """)
    
    # Load data
    with st.spinner("Analyzing Author DNA..."):
        dna_data = load_dna_report()
        classifications_df = load_article_classifications()
    
    # Check for empty data
    if dna_data['total'] == 0:
        st.warning("⚠️ No theme data available. Run theme classification first:")
        st.code("python3 -m app.services.theme_service --full", language="bash")
        return
    
    # === SECTION 1: Overview ===
    st.header("📊 DNA Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    moods = dna_data.get('moods', [])
    
    with col1:
        st.metric(
            "Total Articles",
            dna_data['total'],
            help="Total number of classified articles"
        )
    
    with col2:
        st.metric(
            "Identified Themes",
            len(moods),
            help="Number of distinct themes"
        )
    
    with col3:
        if moods:
            dominant_theme = max(moods, key=lambda x: x['count'])
            st.metric(
                "Dominant Theme",
                dominant_theme['name'],
                help="Theme with most articles"
            )
    
    with col4:
        if moods:
            total_views = sum(m.get('total_views', 0) for m in moods)
            st.metric(
                "Total Views",
                f"{total_views:,}",
                help="Combined views across all themes"
            )
    
    st.divider()
    
    # === SECTION 2: Theme Distribution ===
    st.header("🎨 Theme Distribution")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Article Count by Theme")
        
        # Create DataFrame for plotting
        themes_df = pd.DataFrame(moods)
        
        if not themes_df.empty:
            # Pie chart
            fig = px.pie(
                themes_df,
                values='count',
                names='name',
                color='name',
                color_discrete_map={
                    'Expertise Tech': '#1f77b4',
                    'Human & Career': '#ff7f0e',
                    'Culture & Agile': '#2ca02c',
                    'Free Exploration': '#9467bd'
                },
                hole=0.4,
                height=400
            )
            
            fig.update_traces(
                textposition='inside',
                textinfo='percent+label',
                hovertemplate='<b>%{label}</b><br>%{value} articles<br>%{percent}<extra></extra>'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Theme summary table
        st.subheader("Theme Breakdown")
        
        for mood in sorted(moods, key=lambda x: x['count'], reverse=True):
            pct = (mood['count'] / dna_data['total'] * 100) if dna_data['total'] > 0 else 0
            st.markdown(f"""
            **{mood['name']}**  
            📝 {mood['count']} articles ({pct:.1f}%)  
            👁️ {mood.get('total_views', 0):,} views
            """)
            st.progress(pct / 100)
            st.markdown("---")
    
    with col2:
        st.subheader("Performance by Theme")
        
        if not themes_df.empty:
            # Create metrics DataFrame
            performance_data = []
            
            for mood in moods:
                performance_data.append({
                    'Theme': mood['name'],
                    'Articles': mood['count'],
                    'Avg Views': mood.get('avg_views', 0),
                    'Avg Reactions': mood.get('avg_reactions', 0),
                    'Avg Engagement (%)': mood.get('avg_engagement', 0)
                })
            
            perf_df = pd.DataFrame(performance_data)
            
            # Grouped bar chart
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                name='Avg Views',
                x=perf_df['Theme'],
                y=perf_df['Avg Views'],
                yaxis='y',
                marker_color='#667eea'
            ))
            
            fig.add_trace(go.Bar(
                name='Avg Reactions',
                x=perf_df['Theme'],
                y=perf_df['Avg Reactions'],
                yaxis='y',
                marker_color='#764ba2'
            ))
            
            fig.update_layout(
                barmode='group',
                height=400,
                yaxis={'title': 'Count'},
                legend={'orientation': 'h', 'y': 1.1}
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Engagement comparison
            st.subheader("Engagement Rate by Theme")
            
            fig = px.bar(
                perf_df,
                x='Theme',
                y='Avg Engagement (%)',
                color='Avg Engagement (%)',
                color_continuous_scale='Viridis',
                height=300
            )
            
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # === SECTION 3: Article Classifications ===
    st.header("📚 Article Classifications")
    st.markdown("View individual articles and their assigned themes")
    
    if not classifications_df.empty:
        # Theme filter
        col1, col2 = st.columns([1, 3])
        
        with col1:
            selected_theme = st.selectbox(
                "Filter by theme",
                options=['All'] + sorted(classifications_df['theme_name'].unique().tolist())
            )
        
        # Filter data
        if selected_theme != 'All':
            filtered_df = classifications_df[classifications_df['theme_name'] == selected_theme]
        else:
            filtered_df = classifications_df
        
        # Display stats for filtered data
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Articles", len(filtered_df))
        
        with col2:
            st.metric("Avg Views", f"{filtered_df['views'].mean():.0f}")
        
        with col3:
            st.metric("Avg Reactions", f"{filtered_df['reactions'].mean():.1f}")
        
        with col4:
            st.metric("Avg Engagement", f"{filtered_df['engagement_rate'].mean():.2f}%")
        
        # Article cards
        st.subheader(f"Articles {f'in {selected_theme}' if selected_theme != 'All' else ''}")
        
        # Pagination
        items_per_page = 10
        total_pages = (len(filtered_df) + items_per_page - 1) // items_per_page
        
        page = st.number_input(
            "Page",
            min_value=1,
            max_value=max(1, total_pages),
            value=1,
            step=1
        )
        
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        
        page_df = filtered_df.iloc[start_idx:end_idx]
        
        # Display articles
        for idx, row in page_df.iterrows():
            with st.expander(f"📄 {row['title']}", expanded=False):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Views", f"{row['views']:,}")
                    st.metric("Reactions", f"{row['reactions']}")
                
                with col2:
                    st.metric("Engagement", f"{row['engagement_rate']:.2f}%")
                    st.metric("Confidence", f"{row['confidence_score']:.2f}")
                
                with col3:
                    st.markdown(f"**Theme:** {row['theme_name']}")
                    
                    if row['matched_keywords']:
                        keywords = row['matched_keywords'][:5]  # Show first 5
                        st.markdown(f"**Keywords:** {', '.join(keywords)}")
        
        st.caption(f"Showing {start_idx + 1}-{min(end_idx, len(filtered_df))} of {len(filtered_df)} articles")
    else:
        st.info("No article classifications available")
    
    st.divider()
    
    # === SECTION 4: Insights ===
    st.header("💡 Strategic Insights")
    
    if moods:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🏆 Best Performing Theme")
            
            # Find theme with highest avg engagement
            best_theme = max(moods, key=lambda x: x.get('avg_engagement', 0))
            
            st.success(f"""
            **{best_theme['name']}**
            
            - 📝 {best_theme['count']} articles
            - 👁️ {best_theme.get('avg_views', 0):.0f} avg views
            - 💬 {best_theme.get('avg_reactions', 0):.1f} avg reactions
            - 📊 {best_theme.get('avg_engagement', 0):.2f}% engagement
            
            **Recommendation:** Focus more on this theme type to maximize engagement.
            """)
        
        with col2:
            st.subheader("📈 Growth Opportunities")
            
            # Find theme with lowest avg views but decent count
            growth_themes = [m for m in moods if m['count'] >= 3]
            if growth_themes:
                opportunity_theme = min(growth_themes, key=lambda x: x.get('avg_views', 0))
                
                st.info(f"""
                **{opportunity_theme['name']}**
                
                - 📝 {opportunity_theme['count']} articles
                - 👁️ {opportunity_theme.get('avg_views', 0):.0f} avg views
                - 💬 {opportunity_theme.get('avg_reactions', 0):.1f} avg reactions
                
                **Recommendation:** Articles in this theme have lower visibility. 
                Consider promoting them or improving titles/tags for better reach.
                """)
    
    st.divider()
    
    # Data export
    st.subheader("📥 Export Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if moods:
            themes_csv = pd.DataFrame(moods).to_csv(index=False)
            st.download_button(
                label="Download Theme Summary (CSV)",
                data=themes_csv,
                file_name="theme_summary.csv",
                mime="text/csv"
            )
    
    with col2:
        if not classifications_df.empty:
            classifications_csv = classifications_df.to_csv(index=False)
            st.download_button(
                label="Download Article Classifications (CSV)",
                data=classifications_csv,
                file_name="article_classifications.csv",
                mime="text/csv"
            )


if __name__ == "__main__":
    main()
