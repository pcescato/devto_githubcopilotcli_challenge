# DEV.to Analytics Platform

[![PostgreSQL 18](https://img.shields.io/badge/PostgreSQL-18-blue.svg)](https://www.postgresql.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red.svg)](https://www.sqlalchemy.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> AI-assisted migration of DEV.to analytics from CLI to production web platform using GitHub Copilot CLI

## 📖 Overview

A comprehensive analytics platform for tracking and analyzing DEV.to content performance, migrating from a SQLite-based CLI tool to a production-ready web application with PostgreSQL 18 and modern web technologies.

**Challenge Entry**: [GitHub Copilot CLI Challenge](https://dev.to/challenges/github-copilot-cli-challenge)

## 🏗️ Tech Stack

- **Backend**: FastAPI (Python 3.10+)
- **Database**: PostgreSQL 18
- **ORM**: SQLAlchemy Core (NOT ORM models)
- **Advanced Features**: pgvector for embeddings, JSONB, partitioning
- **Analytics**: Apache Superset
- **API Integration**: DEV.to Forem API

## 📊 Current Status

**Phase 2 Complete**: PostgreSQL 18 Schema Migration ✅

- ✅ Complete technical documentation (2,218 lines)
- ✅ 18 SQLAlchemy Core table definitions
- ✅ Business logic preservation (quality scores, attribution, sentiment)
- ✅ PostgreSQL 18 features (JSONB, ARRAY, Vector, partitioning)
- ✅ Migration guide and validation scripts

**Next Phase**: FastAPI REST API development

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 18
- pip

### Installation

```bash
# 1. Clone repository
git clone https://github.com/YOUR_USERNAME/devto_githubcopilotcli_challenge.git
cd devto_githubcopilotcli_challenge

# 2. Install dependencies
cd app
pip install -r requirements.txt

# 3. Configure database
cp .env.example .env
# Edit .env with your PostgreSQL credentials

# 4. Initialize database
python3 init_database.py

# 5. Verify installation
python3 validate_schema.py
```

## 📁 Project Structure

```
devto_githubcopilotcli_challenge/
├── app/                          # PostgreSQL schema & backend
│   ├── db/
│   │   ├── tables.py             # 18 SQLAlchemy Core tables
│   │   ├── connection.py         # Connection pooling
│   │   ├── queries.py            # Business logic
│   │   └── README.md             # Usage guide
│   ├── init_database.py          # Database setup
│   ├── validate_schema.py        # Schema validation
│   └── requirements.txt          # Python dependencies
│
├── TECHNICAL_DOCUMENTATION.md    # Complete system analysis
├── README_SCHEMA.md              # Schema migration details
├── README.md                     # This file
│
└── [Original CLI tools]          # SQLite-based scripts
    ├── devto_tracker.py
    ├── content_collector.py
    ├── nlp_analyzer.py
    └── ...
```

## 🎯 Features

### Current (CLI Tools)
- Article metrics tracking
- Follower attribution analysis
- Sentiment analysis on comments
- Quality scoring system
- Content collection and NLP analysis

### Planned (Web Platform)
- RESTful API with FastAPI
- Real-time dashboards
- Apache Superset integration
- Semantic search with pgvector
- Advanced analytics and reporting

## 📚 Documentation

- **[TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md)** - Complete system analysis (2,218 lines)
- **[README_SCHEMA.md](README_SCHEMA.md)** - PostgreSQL migration overview
- **[app/INSTALL.md](app/INSTALL.md)** - Installation guide
- **[app/MIGRATION_SUMMARY.md](app/MIGRATION_SUMMARY.md)** - Migration details
- **[app/db/README.md](app/db/README.md)** - Database usage examples

## 🔑 Key Components

### Database Schema (18 Tables)

**Core Tables**: snapshots, article_metrics, follower_events, comments, followers  
**Analytics**: daily_analytics (partitioned), referrers  
**Content**: article_content, code_blocks, links  
**Analysis**: comment_insights, article_history, milestones  
**Intelligence**: author_themes, theme_mapping, stats_cache  

### Business Logic Preserved

- **Follower Attribution**: 7-day window with 6-hour tolerance
- **Quality Score**: (completion × 0.7) + (min(engagement, 20) × 1.5)
- **Sentiment**: Positive ≥0.3, Negative ≤-0.2
- **Proximity Search**: 6-hour tolerance for timestamp matching

## 🤖 AI-Assisted Development

This project was developed with assistance from **GitHub Copilot CLI**, demonstrating:

- Comprehensive codebase analysis (7 Python files, 13 tables)
- SQLite → PostgreSQL migration patterns
- SQLAlchemy Core table definitions
- Business logic preservation
- Complete documentation generation

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

## 🙏 Acknowledgments

- Built for the [GitHub Copilot CLI Challenge](https://dev.to/challenges/github-2026-01-21)
- Powered by [DEV.to Forem API](https://developers.forem.com/api/v1)
- Generated with GitHub Copilot CLI

## 🔗 Links

- [DEV.to Profile](https://dev.to/pascal_cescato_692b7a8a20)
- [Challenge Announcement](https://dev.to/challenges/github-2026-01-21)
- [GitHub Repository](https://github.com/pcescato/devto_githubcopilotcli_challenge)
