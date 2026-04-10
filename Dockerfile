# --- Build Stage (Frontend) ---
FROM node:18-slim AS frontend-builder
WORKDIR /app
COPY package.json ./
RUN npm install
COPY src/frontend ./src/frontend
COPY tsconfig.json ./
RUN npm run build

# --- Runtime Stage (Backend) ---
FROM python:3.14-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uv/bin/uv
ENV PATH="/uv/bin:${PATH}"

# Copy backend files
COPY pyproject.toml VERSION README.md requirements.txt ./
COPY src/matika ./src/matika
# Copy compiled frontend from build stage
COPY --from=frontend-builder /app/src/matika/static/js ./src/matika/static/js

# Install dependencies using uv
RUN uv pip install --system -r requirements.txt

# Set environment variables
ENV PYTHONPATH="/app/src"
ENV DATABASE_URL="sqlite:///./data/matika.db"
ENV SECRET_KEY="insecure-default-change-me"

# Expose port
EXPOSE 8000

# Create data and logs directories
RUN mkdir -p /app/data /app/logs

# Run the application
CMD ["uvicorn", "matika.main:app", "--host", "0.0.0.0", "--port", "8000"]
