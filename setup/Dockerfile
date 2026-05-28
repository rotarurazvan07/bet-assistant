FROM node:22-alpine AS frontend-builder

WORKDIR /app

COPY bet_dashboard/frontend/package.json bet_dashboard/frontend/package-lock.json ./
RUN npm ci

COPY bet_dashboard/frontend/ ./
RUN npm run build

FROM python:3.11-slim AS python-deps

ENV PIP_NO_CACHE_DIR=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

COPY bet_dashboard/backend/requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV MATCHES_DB_PATH=/app/workspace/data/matches.db
ENV SLIPS_DB_PATH=/app/workspace/data/slips.db
ENV CONFIG_PATH=/app/workspace/config
ENV PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    ca-certificates \
    nginx \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

COPY --from=python-deps /install /usr/local
RUN scrapling install \
    && rm -rf /root/.cache /tmp/* /var/lib/apt/lists/* /var/cache/apt/*

COPY bet_framework/ ./bet_framework/
COPY bet_dashboard/backend/ .
COPY config/ config/

COPY bet_dashboard/__init__.py ./bet_dashboard/__init__.py
COPY bet_dashboard/backend/__init__.py ./bet_dashboard/backend/__init__.py
COPY bet_dashboard/backend/core/ ./bet_dashboard/backend/core/

COPY --from=frontend-builder /app/dist /usr/share/nginx/html
COPY setup/nginx.conf /etc/nginx/sites-available/default
COPY setup/start-dashboard.sh /usr/local/bin/start-dashboard.sh

RUN chmod +x /usr/local/bin/start-dashboard.sh

EXPOSE 80

CMD ["/usr/local/bin/start-dashboard.sh"]
