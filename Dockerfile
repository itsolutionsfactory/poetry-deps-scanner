##############################################
# Build virtualenv
##############################################
FROM nexus.itsf.io:5005/python:3.8.8-buster AS venv

# Prepare system
##############################################
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
COPY --chown=python:python --from=venv /app/venv /app/venv/
ENV PATH /app/venv/bin:$PATH

COPY --chown=python:python src/scan_deps.py src/comment_gitlab.py /app/
RUN ln -s /app/scan_deps.py /usr/local/bin/scan-deps
RUN ln -s /app/comment_gitlab.py /usr/local/bin/comment-gitlab

USER python

CMD ["scan-deps"]
