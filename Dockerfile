# One image for both jobs: the web server (python -m mfsim.server) and the daily data
# refresh (python -m mfsim.refresh), which is the only part that needs zstandard.

FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
# Pre-compressed copies; the server sends them to browsers that accept gzip.
RUN npm run build \
    && find dist -type f \( -name '*.js' -o -name '*.css' -o -name '*.html' -o -name '*.svg' \) \
       -size +1k -exec gzip -9 -k {} \;

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data \
    STATE_DIR=/state \
    WEB_DIR=/app/web \
    PORT=8501
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --disable-pip-version-check --root-user-action=ignore -r requirements.txt
COPY mfsim/ mfsim/
RUN python -m compileall -q mfsim
COPY --from=web /web/dist/ web/
USER 1000:1000
EXPOSE 8501
CMD ["python", "-m", "mfsim.server"]
