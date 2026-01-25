"""
FastAPI Application - DEV.to Analytics Platform

Exposes all 5 PostgreSQL async services via REST API.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, AsyncGenerator

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

from app.services.devto_service import DevToService
from app.services.analytics_service import AnalyticsService
from app.services.nlp_service import NLPService
from app.services.content_service import ContentService
from app.services.theme_service import ThemeService
from app.db.tables import article_metrics, article_content, article_code_blocks, article_links
from app.api.models import (
    HealthResponse,
    QualityScoreResponse,
    ReadTimeResponse,
    OverviewResponse,
    ReactionBreakdownResponse,
    DNAReportResponse,
    ClassificationResponse,
    SentimentStatsResponse,
    QuestionResponse,
    ArticleResponse,
    ArticleContentResponse,
    CodeBlockResponse,
    LinkResponse,
    SyncRequest,
    SyncResponse,
    ErrorResponse,
    ThemeStatsResponse,
    SentimentMoodResponse,
)


# ============================================================================
# Configuration
# ============================================================================

load_dotenv()

API_VERSION = "1.0.0"
API_TITLE = "DEV.to Analytics API"
API_DESCRIPTION = """
Modern async PostgreSQL-based analytics platform for DEV.to content.

## Features
- **Analytics**: Quality scores, read time analysis, engagement trends
- **Author DNA**: Theme classification and content distribution
- **NLP**: Sentiment analysis and question detection
- **Content**: Article fetching and analysis
- **Sync**: Background data synchronization with DEV.to API

## Services
All endpoints use async PostgreSQL services with shared connection pooling.
"""


def get_database_url() -> str:
    """Construct async PostgreSQL URL from environment variables"""
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    database = os.getenv('POSTGRES_DB', 'devto_analytics')
    user = os.getenv('POSTGRES_USER')
    password = os.getenv('POSTGRES_PASSWORD')
    
    if not user or not password:
        raise ValueError(
            "Missing PostgreSQL credentials. Set POSTGRES_USER and POSTGRES_PASSWORD"
        )
    
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


# ============================================================================
# Lifespan Management
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle
    
    Startup:
    - Create AsyncEngine with connection pooling
    - Store in app.state for dependency injection
    
    Shutdown:
    - Dispose engine and close all connections
    """
    # Startup
    print("🚀 Starting DEV.to Analytics API...")
    engine = create_async_engine(
        get_database_url(),
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        echo=False,
    )
    app.state.engine = engine
    print(f"✅ Database engine created: {engine.url.database}")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down DEV.to Analytics API...")
    await engine.dispose()
    print("✅ Database connections closed")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# ============================================================================
# CORS Configuration
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:5173",  # Vite default
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request, exc: SQLAlchemyError):
    """Handle database errors"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Database error",
            "detail": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle unexpected errors"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )


# ============================================================================
# Dependency Injection
# ============================================================================

async def get_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Inject shared AsyncEngine"""
    yield app.state.engine


async def get_analytics_service(engine: AsyncEngine = Depends(get_engine)) -> AnalyticsService:
    """Create AnalyticsService with shared engine"""
    return AnalyticsService(engine=engine)


async def get_theme_service(engine: AsyncEngine = Depends(get_engine)) -> ThemeService:
    """Create ThemeService with shared engine"""
    return ThemeService(engine=engine)


async def get_nlp_service(engine: AsyncEngine = Depends(get_engine)) -> NLPService:
    """Create NLPService with shared engine"""
    return NLPService(engine=engine)


async def get_content_service(engine: AsyncEngine = Depends(get_engine)) -> ContentService:
    """Create ContentService with shared engine"""
    return ContentService(engine=engine)


async def get_devto_service(engine: AsyncEngine = Depends(get_engine)) -> DevToService:
    """Create DevToService with shared engine"""
    api_key = os.getenv('DEVTO_API_KEY')
    if not api_key:
        raise HTTPException(status_code=500, detail="DEVTO_API_KEY not configured")
    return DevToService(api_key=api_key, engine=engine)


# ============================================================================
# Health & Status Endpoints
# ============================================================================

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - API info"""
    return {
        "name": API_TITLE,
        "version": API_VERSION,
        "docs": "/docs",
        "health": "/api/health"
    }


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
async def health_check(engine: AsyncEngine = Depends(get_engine)):
    """
    Health check endpoint
    
    Verifies database connectivity and returns status.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        
        return HealthResponse(
            status="ok",
            database="connected",
            timestamp=datetime.now(timezone.utc),
            version=API_VERSION
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection failed: {str(e)}"
        )


# ============================================================================
# Analytics Endpoints
# ============================================================================

@app.get(
    "/api/analytics/quality",
    response_model=List[QualityScoreResponse],
    tags=["Analytics"]
)
async def get_quality_scores(
    limit: int = 10,
    analytics: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get quality scores for top articles
    
    Quality score formula: (completion × 0.7) + (min(engagement, 20) × 1.5)
    Based on 90-day performance metrics.
    """
    try:
        scores = await analytics.get_quality_scores(limit=limit)
        # Map service response to API response model
        return [
            QualityScoreResponse(
                article_id=s['article_id'],
                title=s['title'],
                quality_score=s['quality_score'],
                completion_percent=s['completion_percent'],
                engagement_percent=s['engagement_percent'],
                views_90d=s.get('total_views', 0)  # Map total_views to views_90d
            )
            for s in scores
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/analytics/read-time",
    response_model=List[ReadTimeResponse],
    tags=["Analytics"]
)
async def get_read_time_analysis(
    limit: int = 10,
    analytics: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get read time analysis for top articles
    
    Analyzes completion rates and total reading hours.
    Based on 90-day data from daily_analytics.
    """
    try:
        analysis = await analytics.get_read_time_analysis(limit=limit)
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/analytics/overview",
    response_model=OverviewResponse,
    tags=["Analytics"]
)
async def get_overview(
    days: int = 7,
    analytics: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get global analytics overview with trends
    
    Compares current period vs previous period.
    Returns delta and percentage change.
    """
    try:
        overview = await analytics.get_overview(days=days)
        return overview
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/analytics/reactions",
    response_model=List[ReactionBreakdownResponse],
    tags=["Analytics"]
)
async def get_reaction_breakdown(
    limit: int = 10,
    analytics: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get reaction breakdown for articles
    
    Shows Like, Unicorn, Readinglist counts with lifetime totals.
    Gap indicates removed reactions or data loss.
    """
    try:
        breakdown = await analytics.get_reaction_breakdown(limit=limit)
        return breakdown
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Author DNA Endpoints
# ============================================================================

@app.get(
    "/api/dna",
    response_model=DNAReportResponse,
    tags=["Author DNA"]
)
async def get_dna_report(
    theme_service: ThemeService = Depends(get_theme_service)
):
    """
    Get Author DNA report
    
    Shows content distribution across themes with engagement metrics.
    Themes: Expertise Tech, Human & Career, Culture & Agile, Free Exploration
    """
    try:
        report = await theme_service.generate_dna_report()
        
        # Transform to response model
        themes = [
            ThemeStatsResponse(**theme)
            for theme in report.get('themes', [])
        ]
        
        return DNAReportResponse(themes=themes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/dna/classify/{article_id}",
    response_model=ClassificationResponse,
    tags=["Author DNA"]
)
async def classify_article(
    article_id: int,
    theme_service: ThemeService = Depends(get_theme_service)
):
    """
    Classify article into theme
    
    Uses keyword matching algorithm to determine best theme fit.
    Selection: HIGHEST absolute match_count, confidence as tie-breaker.
    """
    try:
        result = await theme_service.classify_article(article_id)
        return ClassificationResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# NLP Endpoints
# ============================================================================

@app.get(
    "/api/nlp/sentiment",
    response_model=SentimentStatsResponse,
    tags=["NLP"]
)
async def get_sentiment_stats(
    nlp_service: NLPService = Depends(get_nlp_service)
):
    """
    Get global sentiment statistics
    
    Analyzes comment sentiment: positive, neutral, negative.
    Thresholds: ≥0.3 positive, ≤-0.2 negative.
    """
    try:
        stats = await nlp_service.get_sentiment_stats()
        
        # Transform to response model
        moods = [
            SentimentMoodResponse(**mood)
            for mood in stats.get('moods', [])
        ]
        
        return SentimentStatsResponse(
            total=stats.get('total', 0),
            moods=moods
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/nlp/questions",
    response_model=List[QuestionResponse],
    tags=["NLP"]
)
async def get_unanswered_questions(
    limit: int = 10,
    nlp_service: NLPService = Depends(get_nlp_service)
):
    """
    Find unanswered questions in comments
    
    Detects questions using pattern matching and sentiment analysis.
    Returns questions that haven't been replied to.
    """
    try:
        questions = await nlp_service.find_unanswered_questions(limit=limit)
        return [QuestionResponse(**q) for q in questions]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Article Endpoints
# ============================================================================

@app.get(
    "/api/articles",
    response_model=List[ArticleResponse],
    tags=["Articles"]
)
async def get_articles(
    limit: int = 20,
    engine: AsyncEngine = Depends(get_engine)
):
    """
    Get latest article snapshots
    
    Returns most recent metrics for all articles.
    Uses DISTINCT ON to avoid duplicates from multiple snapshots.
    """
    try:
        async with engine.connect() as conn:
            # Get latest snapshot for each article
            result = await conn.execute(
                select(
                    article_metrics.c.article_id,
                    article_metrics.c.title,
                    article_metrics.c.published_at,
                    article_metrics.c.views,
                    article_metrics.c.reactions,
                    article_metrics.c.comments,
                    article_metrics.c.reading_time_minutes,
                    article_metrics.c.tag_list,
                )
                .distinct(article_metrics.c.article_id)
                .order_by(
                    article_metrics.c.article_id,
                    article_metrics.c.collected_at.desc()
                )
                .limit(limit)
            )
            
            articles = []
            for row in result:
                row_dict = dict(row._mapping)
                articles.append(
                    ArticleResponse(
                        article_id=row_dict['article_id'],
                        title=row_dict['title'],
                        published_at=row_dict['published_at'],
                        views=row_dict['views'],
                        reactions=row_dict['reactions'],
                        comments=row_dict['comments'],
                        reading_time_minutes=row_dict['reading_time_minutes'],
                        tags=row_dict['tag_list'] or []
                    )
                )
            
            return articles
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/articles/{article_id}/content",
    response_model=ArticleContentResponse,
    tags=["Articles"]
)
async def get_article_content(
    article_id: int,
    engine: AsyncEngine = Depends(get_engine)
):
    """
    Get full article content with analysis
    
    Returns markdown, code blocks, links, and metadata.
    """
    try:
        async with engine.connect() as conn:
            # Get article content
            result = await conn.execute(
                select(article_content)
                .where(article_content.c.article_id == article_id)
            )
            content_row = result.fetchone()
            
            if not content_row:
                raise HTTPException(status_code=404, detail="Article content not found")
            
            content_dict = dict(content_row._mapping)
            
            # Get code blocks
            result = await conn.execute(
                select(article_code_blocks)
                .where(article_code_blocks.c.article_id == article_id)
                .order_by(article_code_blocks.c.block_order)
            )
            code_blocks = [
                CodeBlockResponse(
                    language=row.language,
                    line_count=row.line_count,
                    block_order=row.block_order
                )
                for row in result
            ]
            
            # Get links
            result = await conn.execute(
                select(article_links)
                .where(article_links.c.article_id == article_id)
                .order_by(article_links.c.link_order)
            )
            links = [
                LinkResponse(
                    url=row.url,
                    link_text=row.link_text,
                    link_order=row.link_order
                )
                for row in result
            ]
            
            return ArticleContentResponse(
                article_id=article_id,
                body_markdown=content_dict['body_markdown'] or '',
                word_count=content_dict['word_count'] or 0,
                code_blocks=code_blocks,
                links=links
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Sync Endpoints
# ============================================================================

async def sync_background(mode: str, engine: AsyncEngine):
    """Background task for data synchronization"""
    api_key = os.getenv('DEVTO_API_KEY')
    if not api_key:
        print("⚠️  DEVTO_API_KEY not configured")
        return
    
    try:
        service = DevToService(api_key=api_key, engine=engine)
        
        print(f"🔄 Starting {mode} sync...")
        
        if mode == "snapshot":
            await service.sync_articles()
        elif mode == "full":
            await service.sync_all()
        elif mode == "rich":
            await service.sync_rich_analytics()
        
        print(f"✅ {mode} sync complete")
    except Exception as e:
        print(f"❌ Sync error: {e}")
        import traceback
        traceback.print_exc()


@app.post(
    "/api/sync",
    response_model=SyncResponse,
    tags=["Sync"]
)
async def trigger_sync(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    engine: AsyncEngine = Depends(get_engine)
):
    """
    Trigger data synchronization with DEV.to API
    
    Modes:
    - **snapshot**: Sync article metrics only (fast)
    - **full**: Sync articles, followers, comments (comprehensive)
    - **rich**: Include historical analytics and referrers (slow)
    
    Runs in background, returns immediately.
    """
    background_tasks.add_task(sync_background, request.mode, engine)
    
    return SyncResponse(
        mode=request.mode,
        status="started",
        message=f"Background sync initiated with mode: {request.mode}",
        timestamp=datetime.now(timezone.utc)
    )


# ============================================================================
# Test Endpoint
# ============================================================================

@app.get("/api/test", tags=["Testing"])
async def test_endpoint(
    analytics: AnalyticsService = Depends(get_analytics_service),
    theme_service: ThemeService = Depends(get_theme_service)
):
    """
    Test endpoint to verify service integration
    
    Calls multiple services and returns sample data.
    """
    try:
        # Test analytics service
        scores = await analytics.get_quality_scores(limit=1)
        
        # Test theme service
        dna = await theme_service.generate_dna_report()
        
        return {
            "status": "ok",
            "services": {
                "analytics": "working" if scores else "no data",
                "theme": "working" if dna.get('themes') else "no data"
            },
            "sample_quality_score": scores[0] if scores else None,
            "theme_count": len(dna.get('themes', []))
        }
    except Exception as e:
        return {
            "status": "error",
            "detail": str(e)
        }


# ============================================================================
# Main (for direct execution)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print(f"""
    🚀 Starting {API_TITLE} v{API_VERSION}
    
    📚 Documentation: http://localhost:8000/docs
    🔍 ReDoc: http://localhost:8000/redoc
    ❤️  Health: http://localhost:8000/api/health
    """)
    
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
