# Production Dockerfile for DEV.to Analytics FastAPI + Streamlit Application
FROM python:3.11-slim

# Set working directory
WORKDIR /code

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files from both locations
COPY requirements.txt /code/requirements.txt
COPY app/requirements.txt /code/app-requirements.txt
COPY app/requirements-streamlit.txt /code/streamlit-requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /code/requirements.txt \
    && pip install --no-cache-dir -r /code/app-requirements.txt \
    && pip install --no-cache-dir -r /code/streamlit-requirements.txt \
    && pip install --no-cache-dir gunicorn \
    && rm /code/requirements.txt /code/app-requirements.txt /code/streamlit-requirements.txt

# Copy application code
COPY app /code/app

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /code
USER appuser

# Expose ports (FastAPI: 8000, Streamlit: 8501)
EXPOSE 8000 8501

# Health check (default for FastAPI, override in docker-compose for Streamlit)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Default command (run gunicorn for FastAPI, override for Streamlit)
CMD ["gunicorn", "app.api.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
