FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app

FROM base AS dependencies

RUN python -m venv /opt/venv
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --requirement /tmp/requirements.txt

FROM base AS runtime

COPY --from=dependencies /opt/venv /opt/venv
COPY --chown=app:app . /app
RUN mkdir -p /app/uploads && chown app:app /app/uploads

USER app
EXPOSE 8000

FROM runtime AS development

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--no-access-log"]

FROM runtime AS production

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
