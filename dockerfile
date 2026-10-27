FROM python:3.14-slim
LABEL org.opencontainers.image.authors="geirawsm@pm.me"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy \
  PYTHONUNBUFFERED=1 \
  PATH="/app/.venv/bin:$PATH"

WORKDIR /app/

# Dependencies first
COPY uv.lock pyproject.toml /app/
COPY sausage_bot/flake8-l10n-checker/flake8_l10n_checker.py /app/sausage_bot/flake8-l10n-checker/
COPY sausage_bot/flake8-l10n-checker/setup.py /app/sausage_bot/flake8-l10n-checker/
RUN uv sync --frozen --no-install-project --no-dev

# Application code
COPY sausage_bot/cogs /app/sausage_bot/cogs
COPY sausage_bot/data/static /app/sausage_bot/data/static
COPY sausage_bot/locale /app/sausage_bot/locale
COPY sausage_bot/util /app/sausage_bot/util
COPY sausage_bot/__init__.py /app/sausage_bot/
COPY sausage_bot/__main__.py /app/sausage_bot/

VOLUME [ "/data" ]

ARG BRANCH="testbranch"
ARG LAST_PUSH_TIME="testpush time"
ARG LAST_COMMIT_MSG="testcommit message"
ARG LAST_COMMIT="testcommit"
ARG LAST_RUN_NUMBER="testrun"

ENV BRANCH=${BRANCH} \
  LAST_PUSH_TIME=${LAST_PUSH_TIME} \
  LAST_COMMIT_MSG=${LAST_COMMIT_MSG} \
  LAST_COMMIT=${LAST_COMMIT} \
  LAST_RUN_NUMBER=${LAST_RUN_NUMBER}

RUN python -c "import json, os; json.dump({k: os.environ[k] for k in ('BRANCH','LAST_PUSH_TIME',LAST_COMMIT_MSG','LAST_COMMIT','LAST_RUN_NUMBER')}, open('/app/sausage_bot/version.json','w'))"

# Run bot
ENTRYPOINT [ "python", "-m", "sausage_bot", "--data-dir", "/data" ]
