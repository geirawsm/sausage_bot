FROM python:3.9-alpine
LABEL Maintainer="geirawsm"

WORKDIR /

COPY . ./app/
WORKDIR /app/

RUN pip install --upgrade pip
RUN pip3 install -r requirements.txt

VOLUME [ "/data" ]

# Run bot
ENTRYPOINT ["python", "-m", "sausage_bot", "-l", "-lm", "-d", "--data-dir", "/data"]