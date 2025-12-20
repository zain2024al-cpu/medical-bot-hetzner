# ================================================
# Dockerfile - High-Performance Production for Hetzner VPS
# 🚀 محسّن للأداء العالي والضغط الثقيل
# ================================================

FROM python:3.12-slim

# 🚀 تحسينات الأداء للنظام
RUN apt-get update && apt-get install -y --no-install-recommends \
    # WeasyPrint dependencies
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
    # 🚀 تحسينات الأداء الإضافية
    curl \
    && update-ca-certificates \
    # تنظيف لتقليل حجم الصورة
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

# 🚀 إنشاء المجلدات مع صلاحيات محسّنة
RUN mkdir -p db exports uploads/schedules templates logs && \
    chmod -R 755 db exports uploads templates logs

# 🚀 متغيرات البيئة محسّنة للأداء العالي
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    DATABASE_PATH=/app/db/medical_reports.db \
    # 🚀 تحسينات Python للأداء العالي
    PYTHONOPTIMIZE=1 \
    PYTHONHASHSEED=random \
    # 🚀 إعدادات الذاكرة والـ GC
    PYTHONMALLOC=malloc \
    MALLOC_ARENA_MAX=2

# 🚀 تحسينات إضافية للأداء العالي
RUN echo '* soft nofile 65536' >> /etc/security/limits.conf && \
    echo '* hard nofile 65536' >> /etc/security/limits.conf && \
    echo 'vm.max_map_count=262144' >> /etc/sysctl.conf

# Expose port
EXPOSE 8080

# 🚀 Health check محسّن (اختياري - يمكن تعطيله إذا أثر على الأداء)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# 🚀 تشغيل البوت مع تحسينات الأداء
CMD ["python", "-u", "-O", "app.py"]

