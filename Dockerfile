##############################################
# Build virtualenv
##############################################
FROM nexus.itsf.io:5005/python:3.8.8-buster AS venv

# Prepare system
##############################################
# https://python-poetry.org/docs/#installation
ENV POETRY_VERSION=1.1.5
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | python -

ENV PATH /root/.poetry/bin:/root/.local/bin:$PATH
ENV PYTHONPATH $PYTHONPATH:/root/.poetry/lib

# Install python dependencies
##############################################
RUN pip install --user poetry-lock-check==0.1.0

WORKDIR /app
COPY pyproject.toml poetry.lock ./

RUN python -m poetry_lock_check check-lock

RUN python -m venv --copies /app/venv
RUN . /app/venv/bin/activate \
    && poetry install



##############################################
# write git info
##############################################
FROM nexus.itsf.io:5005/alpine/git:v2.26.2 AS git

WORKDIR /app
COPY .git /app/.git/
RUN git describe --tags --always > /git-describe
RUN git rev-parse HEAD > /git-commit



##############################################
# Main image
##############################################
FROM nexus.itsf.io:5005/python:3.8.8-slim-buster as final

# Expected env vars to comment in Gitlab MR
ENV BOT_USERNAME ""
ENV BOT_TOKEN ""

# Setup unprivileged user
##############################################
RUN groupadd -g 1000 python
RUN useradd -M -d /srv -u 1000 -g 1000 -s /bin/bash python

# Fetch project requirements
##############################################
COPY --chown=python:python --from=git /git-describe /git-commit /app/git/
COPY --chown=python:python --from=venv /app/venv /app/venv/
ENV PATH /app/venv/bin:$PATH

COPY --chown=python:python scan_deps.py comment_gitlab.py /app/
RUN ln -s /app/scan_deps.py /usr/local/bin/scan-deps
RUN ln -s /app/comment_gitlab.py /usr/local/bin/comment-gitlab

CMD ["scan-deps"]
