# buildbot/buildbot-worker-python-node

# This example docker file show how to customize the base worker docker image
# to add build dependencies to build the python+nodejs buildbot_www package

FROM        buildbot/buildbot-worker:master
MAINTAINER  Buildbot maintainers

# This will make apt-get install without question
ARG         DEBIAN_FRONTEND=noninteractive

user root
# Install required npm packages
RUN  curl -sL https://deb.nodesource.com/setup_6.x | bash - && \
        apt-get update && apt-get install -y -o APT::Install-Recommends=false -o APT::Install-Suggests=false \
        nodejs \
        git && \
    rm -rf /var/lib/apt/lists/*

user buildbot
