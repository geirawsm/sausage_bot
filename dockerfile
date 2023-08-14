FROM python:3.11.4-alpine3.18
LABEL Maintainer="geirawsm"

WORKDIR /

COPY . ./app/
WORKDIR /app/

RUN pip install --upgrade pip
RUN pip install pipenv
RUN pipenv install --system --deploy --ignore-pipfile

VOLUME [ "/data" ]

# Run bot
ENTRYPOINT ["python", "-m", "sausage_bot", "-l", "-lm", "-lp", "-d", "--data-dir", "/data"]
