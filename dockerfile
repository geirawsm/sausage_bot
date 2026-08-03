FROM python:3.14-slim
LABEL org.opencontainers.image.authors="geirawsm@pm.me"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
  ffmpeg \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /

COPY / /app/
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
ENTRYPOINT [ "python", "-m", "sausage_bot", "--log-all", "--data-dir", "/data" ]
