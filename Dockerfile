##############################################
# Build virtualenv
##############################################
FROM nexus.itsf.io:5005/python:3.10.4-bullseye AS venv

# Prepare system
##############################################
ENV POETRY_VERSION=1.1.11
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | python -

ENV PATH /root/.local/bin:$PATH

# Install python dependencies
##############################################
RUN pip install --user poetry-lock-check==0.1.0

WORKDIR /app
COPY pyproject.toml poetry.lock ./

RUN python -m poetry_lock_check check-lock

RUN python -m venv --copies ./venv
RUN . /app/venv/bin/activate \
    && poetry install

# will install the scripts as executable
COPY poetry_deps_scanner/ ./poetry_deps_scanner/
COPY README.md ./
RUN . /app/venv/bin/activate \
    && poetry install


##############################################
# Main image
##############################################
FROM nexus.itsf.io:5005/python:3.10.4-slim-bullseye as final

# Expected env vars to comment in Gitlab MR
ENV BOT_USERNAME ""
ENV BOT_TOKEN ""

# Setup unprivileged user
##############################################
RUN groupadd -g 1000 python
RUN useradd -M -d /srv -u 1000 -g 1000 -s /bin/bash python

# Fetch project requirements
##############################################
COPY --chown=python:python --from=venv /app/venv /app/venv/
ENV PATH /app/venv/bin:$PATH

# still required for the executable scripts to run
COPY --chown=python:python poetry_deps_scanner/ /app/poetry_deps_scanner/

USER python

CMD ["scan-deps"]
