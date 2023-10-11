# Tells pipenv to create virtualenvs in /root rather than $HOME/.local/share.
# We do this because GitHub modifies the HOME variable between `docker build` and
# `docker run`
# ENV WORKON_HOME /root

# Tells pipenv to use this specific Pipfile rather than the Pipfile in the 
# current working directory (the working directory changes between `docker build` 
# and `docker run`, this ensures we always use the same Pipfile)
ENV PIPENV_PIPFILE /Pipfile

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
