FROM python:3.14-slim
LABEL org.opencontainers.image.authors="geirawsm@pm.me"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
  ffmpeg \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /

COPY /sausage_bot/cogs /app/sausage_bot/cog
COPY /sausage_bot/data/static /app/sausage_bot/data/static
COPY /sausage_bot/locale /app/sausage_bot/locale
COPY /sausage_bot/util /app/sausage_bot/util
COPY /sausage_bot/__init__.py /app/sausage_bot/
COPY /sausage_bot/__main__.py /app/sausage_bot/
COPY /Pipfile /app/Pipfile
COPY /Pipfile.lock /app/Pipfile.lock

WORKDIR /app/

RUN pip install pipenv
RUN pipenv install --system --deploy --ignore-pipfile

VOLUME [ "/data" ]

ARG BRANCH="testbranch"
ARG LAST_COMMIT_MSG="testcommit message"
ARG LAST_COMMIT="testcommit"
ARG LAST_RUN_NUMBER="testrun"

RUN echo \
  "{\"BRANCH\": \"${BRANCH}\","\
  "\"LAST_COMMIT_MSG\": \"${LAST_COMMIT_MSG}\","\
  "\"LAST_COMMIT\": \"${LAST_COMMIT}\","\
  "\"LAST_RUN_NUMBER\": \"${LAST_RUN_NUMBER}\"}"\
  > /app/sausage_bot/version.json


# Run bot
# --data-dir points the bot at the volume declared above. Without it the
# bot would write to `sausage_bot/data/` inside the image layer instead.
ENTRYPOINT [ "python", "-m", "sausage_bot", "--data-dir", "/data" ]
