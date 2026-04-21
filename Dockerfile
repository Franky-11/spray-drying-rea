FROM node:22-bookworm-slim AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src:/app

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY core/ ./core/
COPY --from=frontend-build /app/frontend/dist/ ./frontend/dist/

EXPOSE 8000

CMD ["uvicorn", "spray_drying.api:app", "--host", "0.0.0.0", "--port", "8000"]
