# Pin a registry digest in your release after building; record the resolved
# Contree checkpoint UUID in CONTREE_IMAGE and every run manifest.
FROM python:3.12.12-slim
WORKDIR /opt/replaylab
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/replaylab /opt/replaylab/backend/replaylab
COPY deploy/sandbox.Dockerfile /opt/replaylab/deploy/sandbox.Dockerfile
ENV PYTHONPATH=/opt/replaylab/backend
ENV PYTHONDONTWRITEBYTECODE=1
# Candidate code is executed as nobody; root observer files are not writable.
RUN python -m replaylab.sandboxes.fingerprint && chmod -R a-w /opt/replaylab && chmod 1777 /tmp
USER root
ENTRYPOINT ["python", "-m", "replaylab.sandboxes.entrypoint"]
