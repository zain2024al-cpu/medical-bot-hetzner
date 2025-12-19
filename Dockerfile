# ================================================
# Dockerfile - Production-Ready for Google Cloud Run
# ================================================

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies for WeasyPrint and PDF generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libcairo2 \
    libgobject-2.0-0 \
    shared-mime-info \
    ca-certificates \
    libssl-dev \
    openssl \
    && update-ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache/pip

# Ensure templates are copied explicitly
COPY templates/ /app/templates/

# Copy project files
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p db exports uploads/schedules templates && \
    chmod -R 755 db exports uploads templates

# Set environment variables for production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_PATH=/app/db/medical_reports.db

# Expose port (for Cloud Run)
EXPOSE 8080

# NO HEALTHCHECK - Cloud Run handles health checks automatically
# Health checks break startup for Telegram bots

# Run the bot
CMD ["python", "-u", "app.py"]

