FROM python:3.12-alpine
LABEL Maintainer="geirawsm"

WORKDIR /

COPY . ./app/
WORKDIR /app/

RUN pip install --upgrade pip
RUN pip install pipenv
RUN pipenv install --system --deploy --ignore-pipfile

VOLUME [ "/data" ]

# Run bot
CMD ["python", "-m", "sausage_bot", "--log", "--verbose", "--log-print", "--log-database", "--debug", "--data-dir", "/data"]
