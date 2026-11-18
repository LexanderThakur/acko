# syntax=docker/dockerfile:1
# Contract Guard backend — Django + gunicorn on Alpine.
#
# Layer order = cache order: the virtualenv only rebuilds when
# requirements.txt changes; source edits reuse everything above.

########################
# deps — build the venv
########################
FROM python:3.14-alpine AS deps
# toolchain lives only in this stage; used to compile sdists that
# don't ship musl wheels (e.g. PyYAML)
RUN apk add --no-cache build-base

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# manifest only — this is the cache boundary: any code edit below
# still hits the cached pip install layer
COPY requirements.txt .

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

########################
# runtime — slim final image
########################
FROM python:3.14-alpine AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# same base image, so the compiled venv is ABI-compatible; gcc not needed here
COPY --from=deps /opt/venv /opt/venv

WORKDIR /app

COPY . .

EXPOSE 8000

# migrations are idempotent and run on every start; SQLite lives on a
# mounted volume (SQLITE_DIR). `exec` hands PID 1 to gunicorn so it
# receives SIGTERM on `docker compose stop`.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn backend.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 2 --timeout 60"]
