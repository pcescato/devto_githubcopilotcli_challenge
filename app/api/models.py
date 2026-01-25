"""
Pydantic Response Models for FastAPI

Defines all request/response schemas for the DEV.to Analytics API.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict, Any


# ============================================================================
# Analytics Models
# ============================================================================

class QualityScoreResponse(BaseModel):
    """Quality score for an article (90-day period)"""
    article_id: int
    title: str
    quality_score: float
    completion_percent: float
    engagement_percent: float
    views_90d: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "article_id": 3180743,
                "title": "Building My Own DEV.to Analytics",
                "quality_score": 87.5,
                "completion_percent": 82.3,
                "engagement_percent": 8.97,
                "views_90d": 1472
            }
        }


class ReadTimeResponse(BaseModel):
    """Read time analysis for an article"""
    article_id: int
    title: str
    reading_time_minutes: int
    avg_read_seconds: int
    completion_percent: float
    total_hours: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "article_id": 3180743,
                "title": "Building My Own DEV.to Analytics",
                "reading_time_minutes": 8,
                "avg_read_seconds": 394,
                "completion_percent": 82.1,
                "total_hours": 161.2
            }
        }


class OverviewResponse(BaseModel):
    """Global analytics overview with trends"""
    period_days: int
    current: Dict[str, int]
    previous: Dict[str, int]
    delta: Dict[str, int]
    delta_percent: Dict[str, float]
    
    class Config:
        json_schema_extra = {
            "example": {
                "period_days": 7,
                "current": {"views": 3420, "reactions": 156, "comments": 42},
                "previous": {"views": 2890, "reactions": 134, "comments": 38},
                "delta": {"views": 530, "reactions": 22, "comments": 4},
                "delta_percent": {"views": 18.3, "reactions": 16.4, "comments": 10.5}
            }
        }


class ReactionBreakdownResponse(BaseModel):
    """Reaction breakdown for an article"""
    article_id: int
    title: str
    age_days: int
    lifetime_reactions: int
    like: int
    unicorn: int
    readinglist: int
    sum_reactions: int
    gap: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "article_id": 3180743,
                "title": "Building My Own DEV.to Analytics",
                "age_days": 7,
                "lifetime_reactions": 88,
                "like": 62,
                "unicorn": 15,
                "readinglist": 11,
                "sum_reactions": 88,
                "gap": 0
            }
        }


# ============================================================================
# Theme/DNA Models
# ============================================================================

class ThemeStatsResponse(BaseModel):
    """Statistics for a theme"""
    theme_name: str
    article_count: int
    total_views: int
    total_reactions: int
    avg_views: float
    engagement_pct: float


class DNAReportResponse(BaseModel):
    """Author DNA report with theme distribution"""
    themes: List[ThemeStatsResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "themes": [
                    {
                        "theme_name": "Expertise Tech",
                        "article_count": 14,
                        "total_views": 3472,
                        "total_reactions": 138,
                        "avg_views": 248.0,
                        "engagement_pct": 3.97
                    }
                ]
            }
        }


class ClassificationResponse(BaseModel):
    """Article theme classification result"""
    article_id: int
    theme_name: str
    match_count: int
    confidence_score: float
    matched_keywords: List[str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "article_id": 3180743,
                "theme_name": "Expertise Tech",
                "match_count": 1,
                "confidence_score": 0.10,
                "matched_keywords": ["python"]
            }
        }


# ============================================================================
# NLP Models
# ============================================================================

class SentimentMoodResponse(BaseModel):
    """Sentiment mood statistics"""
    mood: str
    count: int
    percentage: float


class SentimentStatsResponse(BaseModel):
    """Global sentiment statistics"""
    total: int
    moods: List[SentimentMoodResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 145,
                "moods": [
                    {"mood": "positive", "count": 98, "percentage": 67.6},
                    {"mood": "neutral", "count": 32, "percentage": 22.1},
                    {"mood": "negative", "count": 15, "percentage": 10.3}
                ]
            }
        }


class QuestionResponse(BaseModel):
    """Unanswered question from comments"""
    comment_id: str
    article_title: str
    author_username: str
    text_preview: str
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "comment_id": "abc123",
                "article_title": "Building Analytics Platform",
                "author_username": "john_doe",
                "text_preview": "How did you handle rate limiting?",
                "created_at": "2026-01-25T20:00:00Z"
            }
        }


# ============================================================================
# Article Models
# ============================================================================

class ArticleResponse(BaseModel):
    """Article metadata (latest snapshot)"""
    article_id: int
    title: str
    published_at: Optional[datetime]
    views: int
    reactions: int
    comments: int
    reading_time_minutes: Optional[int]
    tags: Optional[List[str]] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "article_id": 3180743,
                "title": "Building My Own DEV.to Analytics",
                "published_at": "2026-01-18T20:27:16.124Z",
                "views": 1474,
                "reactions": 88,
                "comments": 44,
                "reading_time_minutes": 8,
                "tags": ["devto", "analytics", "python", "opensource"]
            }
        }


class CodeBlockResponse(BaseModel):
    """Code block metadata"""
    language: Optional[str]
    line_count: int
    block_order: int


class LinkResponse(BaseModel):
    """Link metadata"""
    url: str
    link_text: Optional[str]
    link_order: int


class ArticleContentResponse(BaseModel):
    """Full article content with analysis"""
    article_id: int
    body_markdown: str
    word_count: int
    code_blocks: List[CodeBlockResponse]
    links: List[LinkResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "article_id": 3180743,
                "body_markdown": "# Building Analytics\\n\\nContent here...",
                "word_count": 1542,
                "code_blocks": [
                    {"language": "python", "line_count": 24, "block_order": 0}
                ],
                "links": [
                    {"url": "https://dev.to", "link_text": "DEV.to", "link_order": 0}
                ]
            }
        }


# ============================================================================
# Sync Models
# ============================================================================

class SyncRequest(BaseModel):
    """Sync operation request"""
    mode: str = Field(..., pattern="^(snapshot|full|rich)$")
    
    class Config:
        json_schema_extra = {
            "example": {
                "mode": "snapshot"
            }
        }


class SyncResponse(BaseModel):
    """Sync operation response"""
    mode: str
    status: str
    message: str
    timestamp: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "mode": "snapshot",
                "status": "started",
                "message": "Background sync initiated",
                "timestamp": "2026-01-25T22:30:00Z"
            }
        }


# ============================================================================
# Health Models
# ============================================================================

class HealthResponse(BaseModel):
    """API health check response"""
    status: str
    database: str
    timestamp: datetime
    version: str = "1.0.0"
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "database": "connected",
                "timestamp": "2026-01-25T22:30:00Z",
                "version": "1.0.0"
            }
        }


# ============================================================================
# Error Models
# ============================================================================

class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "Database error",
                "detail": "Connection timeout",
                "timestamp": "2026-01-25T22:30:00Z"
            }
        }
