FROM python:3.12-alpine
LABEL org.opencontainers.image.authors="geirawsm@pm.me"

WORKDIR /

COPY . ./app/
WORKDIR /app/

RUN pip install --upgrade pip
RUN pip install pipenv
RUN pipenv install --system --deploy --ignore-pipfile

VOLUME [ "/data" ]

ARG LAST_RUN_NUMBER="testrun"
ARG LAST_COMMIT="testcommit"
ARG BRANCH="testbranch"

RUN echo -e \
    "{\"BRANCH\": \"${BRANCH}\", "\
    "\"LAST_RUN_NUMBER\": \"${LAST_RUN_NUMBER}\", "\
    "\"LAST_COMMIT\": \"${LAST_COMMIT}\"}"\
    > /app/sausage_bot/version.json

# Run bot
CMD ["python", "-m", "sausage_bot", "--log", "--verbose", "--log-print", "--log-database", "--debug", "--log-file", "--data-dir", "/data"]
