# These should be updated whenever we change ci/build-layer.sh, or the
# variables in CI.
ARG PYTHON_VERSION=3.9.23

FROM python:${PYTHON_VERSION}-slim-bookworm
ARG PYTHON_PIP_VERSION=25.1.1

RUN apt-get -qq update && \
    apt-get -qq install build-essential libffi-dev && \
    pip install -U pip==$PYTHON_PIP_VERSION

RUN useradd -m mozilla-iam
USER mozilla-iam
WORKDIR /home/mozilla-iam

RUN --mount=type=bind,source=requirements,destination=/home/mozilla-iam/requirements \
    pip install --no-warn-script-location -r requirements/core.txt -r requirements/run.txt
COPY --chown=mozilla-iam:mozilla-iam python-modules/ /home/mozilla-iam/python-modules/
RUN pip install -e python-modules/cis_*

ENTRYPOINT ["python", "-m", "gunicorn", "--bind", "0:8000"]
