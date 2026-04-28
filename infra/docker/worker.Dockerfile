FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY app /app/app
COPY infra /app/infra
COPY migrations /app/migrations
COPY scripts /app/scripts

RUN pip install --no-cache-dir .

CMD ["celery", "-A", "app.celery_app.celery_app", "worker", "--beat", "--loglevel=info"]
