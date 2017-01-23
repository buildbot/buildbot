# buildbot/buildbot-worker

# please follow docker best practices
# https://docs.docker.com/engine/userguide/eng-image/dockerfile_best-practices/

# Provides a base Ubuntu (16.04) image with latest buildbot worker installed
# the worker image is not optimized for size, but rather uses ubuntu for wider package availability

FROM        ubuntu:16.04
MAINTAINER  Buildbot maintainers

COPY . /usr/src/buildbot-worker
COPY docker/buildbot.tac /buildbot/buildbot.tac

# Last build date - this can be updated whenever there are security updates so
# that everything is rebuilt
ENV         security_updates_as_of 2016-10-07

# This will make apt-get install without question
ARG         DEBIAN_FRONTEND=noninteractive

# Install security updates and required packages
RUN         apt-get update && \
            apt-get -y upgrade && \
            apt-get -y install -q \
                build-essential \
                git \
                subversion \
                python-dev \
                libffi-dev \
                libssl-dev \
                python-pip \
                curl && \
            rm -rf /var/lib/apt/lists/* && \
# Test runs produce a great quantity of dead grandchild processes.  In a
# non-docker environment, these are automatically reaped by init (process 1),
# so we need to simulate that here.  See https://github.com/Yelp/dumb-init
            curl -Lo /usr/local/bin/dumb-init https://github.com/Yelp/dumb-init/releases/download/v1.1.3/dumb-init_1.1.3_amd64 && \
            chmod +x /usr/local/bin/dumb-init && \
# ubuntu pip version has issues so we should upgrade it: https://github.com/pypa/pip/pull/3287
            pip install -U pip virtualenv && \
# Install required python packages, and twisted
            pip --no-cache-dir install \
                'twisted[tls]' && \
            pip install /usr/src/buildbot-worker && \

    useradd -ms /bin/bash buildbot && chown -R buildbot /buildbot

USER buildbot

WORKDIR /buildbot

CMD ["/usr/local/bin/dumb-init", "twistd", "-ny", "buildbot.tac"]
