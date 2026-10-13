FROM node:22-alpine AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM python:3.12.12-slim
WORKDIR /opt/replaylab
COPY requirements.lock ./
RUN pip install --disable-pip-version-check --no-cache-dir -r requirements.lock \
    && groupadd --gid 10001 replaylab \
    && useradd --uid 10001 --gid 10001 --no-create-home replaylab \
    && mkdir /data && chown 10001:10001 /data
COPY backend/ backend/
COPY fixtures/ fixtures/
COPY evals/baselines/ evals/baselines/
COPY deploy/sandbox.Dockerfile deploy/sandbox.Dockerfile
COPY --from=web /web/dist/ apps/web/dist/
ARG REPLAYLAB_REVISION=uncommitted
ARG REPLAYLAB_SOURCE_CLEAN=false
ENV PYTHONPATH=/opt/replaylab/backend \
    PYTHONDONTWRITEBYTECODE=1 \
    REPLAYLAB_DATA_DIR=/data \
    REPLAYLAB_REVISION=${REPLAYLAB_REVISION} \
    REPLAYLAB_SOURCE_CLEAN=${REPLAYLAB_SOURCE_CLEAN}
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3))['ready']"
CMD ["python", "-m", "replaylab.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]
