# buildbot/buildbot-worker

# Provides a base Ubuntu (14.04) image with latest buildbot worker installed
# (based on twisted dockerfile https://github.com/cyli/docker-twisted)

FROM        ubuntu:14.04
MAINTAINER  Buildbot maintainers

COPY . /usr/src/buildbot-worker
COPY docker/buildbot.tac /buildbot/buildbot.tac

# Last build date - this can be updated whenever there are security updates so
# that everything is rebuilt
ENV         security_updates_as_of 2016-06-20

# Install security updates and required packages
RUN         apt-get update && \
            apt-get -y upgrade && \
            apt-get -y install -q \
            build-essential \
            git \
            subversion \
            python-dev libffi-dev libssl-dev python-pip

# Install required python packages, and twisted
RUN         pip install service_identity pycrypto && \
            pip install twisted && \
            pip install /usr/src/buildbot-worker

WORKDIR /buildbot

CMD ["twistd", "-ny", "buildbot.tac"]
