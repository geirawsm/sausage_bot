FROM python:3.12-slim
LABEL org.opencontainers.image.authors="geirawsm@pm.me"

WORKDIR /

COPY / /app/
WORKDIR /app/

RUN pip install --upgrade pip
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