# buildbot/buildbot-worker

# please follow docker best practices
# https://docs.docker.com/engine/userguide/eng-image/dockerfile_best-practices/

# Provides a base Debian image with latest buildbot worker installed

FROM docker.io/library/debian:12
MAINTAINER  Buildbot maintainers

# Last build date - this can be updated whenever there are security updates so
# that everything is rebuilt
ENV security_updates_as_of 2023-09-01

# This will make apt-get install without question
ARG DEBIAN_FRONTEND=noninteractive

# Install security updates and required packages
RUN apt-get update \
    && apt-get -y upgrade \
    && apt-get -y install -q \
        build-essential \
        git \
        subversion \
        python3-dev \
        libffi-dev \
        libssl-dev \
        virtualenv \
        # Test runs produce a great quantity of dead grandchild processes.  In a
        # non-docker environment, these are automatically reaped by init (process 1),
        # so we need to simulate that here.  See https://github.com/Yelp/dumb-init
        dumb-init \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && virtualenv --python=python3 /buildbot_venv \
    && /buildbot_venv/bin/pip3 install 'twisted[tls]' \
    && mkdir /buildbot \
    && useradd -ms /bin/bash buildbot

COPY . /usr/src/buildbot-worker
COPY docker/buildbot.tac /buildbot/buildbot.tac

RUN /buildbot_venv/bin/pip3 install /usr/src/buildbot-worker && \
    chown -R buildbot /buildbot

USER buildbot
WORKDIR /buildbot

CMD ["/usr/bin/dumb-init", "/buildbot_venv/bin/twistd", "--pidfile=", "-ny", "buildbot.tac"]
