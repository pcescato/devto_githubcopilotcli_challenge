"""
DEV.to Analytics Services

Modern async PostgreSQL-first architecture for DEV.to data collection and analysis.

Services:
- DevToService: API collection and data synchronization
- AnalyticsService: Quality metrics and traffic analysis
- NLPService: Sentiment analysis and spam detection
- ContentService: Article content collection and parsing
- ThemeService: Thematic classification and Author DNA analysis
"""

def __getattr__(name):
    """Lazy import to avoid runpy warning when running services as modules"""
    if name == 'DevToService':
        from app.services.devto_service import DevToService
        return DevToService
    elif name == 'create_service':
        from app.services.devto_service import create_service
        return create_service
    elif name == 'AnalyticsService':
        from app.services.analytics_service import AnalyticsService
        return AnalyticsService
    elif name == 'create_analytics_service':
        from app.services.analytics_service import create_analytics_service
        return create_analytics_service
    elif name == 'NLPService':
        from app.services.nlp_service import NLPService
        return NLPService
    elif name == 'create_nlp_service':
        from app.services.nlp_service import create_nlp_service
        return create_nlp_service
    elif name == 'ContentService':
        from app.services.content_service import ContentService
        return ContentService
    elif name == 'create_content_service':
        from app.services.content_service import create_content_service
        return create_content_service
    elif name == 'ThemeService':
        from app.services.theme_service import ThemeService
        return ThemeService
    elif name == 'create_theme_service':
        from app.services.theme_service import create_theme_service
        return create_theme_service
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    'DevToService',
    'AnalyticsService',
    'NLPService',
    'ContentService',
    'ThemeService',
    'create_service',
    'create_analytics_service',
    'create_nlp_service',
    'create_content_service',
    'create_theme_service',
]
