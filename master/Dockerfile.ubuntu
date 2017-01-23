# buildbot/buildbot-master-ubuntu

# please follow docker best practices
# https://docs.docker.com/engine/userguide/eng-image/dockerfile_best-practices/

# Provides a base Ubuntu (16.04) image with latest buildbot master installed

FROM        ubuntu:16.04
MAINTAINER  Buildbot maintainers

# Last build date - this can be updated whenever there are security updates so
# that everything is rebuilt
ENV         security_updates_as_of 2016-10-07

# This will make apt-get install without question (only for the time of the docker build)
ARG         DEBIAN_FRONTEND=noninteractive

COPY . /usr/src/buildbot
# Install security updates and required packages
RUN         apt-get update && \
            apt-get -y upgrade && \
            apt-get -y install -q \
                build-essential \
                curl \
                python-dev \
                libffi-dev \
                libssl-dev \
                python-pip \
                python-psycopg2 && \
            rm -rf /var/lib/apt/lists/* && \
# Install required python packages, and twisted
            pip install --upgrade pip setuptools && \
            pip install "buildbot[bundle,tls]" && \
            pip install "/usr/src/buildbot"

WORKDIR /var/lib/buildbot
CMD ["/usr/src/buildbot/contrib/docker/master/start_buildbot.sh"]
