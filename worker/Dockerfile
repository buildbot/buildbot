# buildbot/buildbot-worker

# Provides a base Ubuntu (14.04) image with latest buildbot worker installed
# (based on twisted dockerfile https://github.com/cyli/docker-twisted)

FROM        ubuntu:14.04
MAINTAINER  Buildbot maintainers

COPY . /usr/src/buildbot-worker
COPY docker/buildbot.tac /buildbot/buildbot.tac

# Last build date - this can be updated whenever there are security updates so
# that everything is rebuilt
ENV         security_updates_as_of 2016-08-23

# Install security updates and required packages
RUN         apt-get update && \
            apt-get -y upgrade && \
            apt-get -y install -q \
            build-essential \
            git \
            subversion \
            python-dev libffi-dev libssl-dev python-pip python-virtualenv curl && \
            apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Test runs produce a great quantity of dead grandchild processes.  In a
# non-docker environment, these are automatically reaped by init (process 1),
# so we need to simulate that here.  See https://github.com/Yelp/dumb-init
RUN curl -Lo /usr/local/bin/dumb-init https://github.com/Yelp/dumb-init/releases/download/v1.0.0/dumb-init_1.0.0_amd64
RUN chmod +x /usr/local/bin/dumb-init

# Install required python packages, and twisted
RUN         pip install service_identity pycrypto && \
            pip install twisted && \
            pip install /usr/src/buildbot-worker

RUN useradd -ms /bin/bash buildbot && chown -R buildbot /buildbot
USER buildbot

WORKDIR /buildbot

CMD ["/usr/local/bin/dumb-init", "twistd", "-ny", "buildbot.tac"]
