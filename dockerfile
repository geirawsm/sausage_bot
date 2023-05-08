FROM python:latest
LABEL Maintainer="geirawsm"

WORKDIR /

RUN pip install --upgrade pip
COPY . ./app/
WORKDIR /app
RUN pip3 install -r requirements.txt

VOLUME [ "/app/json", "/app/logs" , "/app/static"]

# Run bot
ENTRYPOINT ["python", "-m", "sausage_bot", "-l", "-lp", "-lm", "-d"]