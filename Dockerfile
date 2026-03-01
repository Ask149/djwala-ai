# DjwalaAI Production Dockerfile
FROM python:3.11-slim

# Install system dependencies (ffmpeg for yt-dlp audio extraction)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/
COPY static/ ./static/

# Install Python dependencies
RUN pip install --no-cache-dir .

# Create directory for database
RUN mkdir -p /data

# Set static directory path for production
ENV DJWALA_STATIC_DIR=/app/static

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "djwala.main:app", "--host", "0.0.0.0", "--port", "8000"]
