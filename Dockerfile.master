# buildbot/buildbot-master

# please follow docker best practices
# https://docs.docker.com/engine/userguide/eng-image/dockerfile_best-practices/

# Use a multi-stage build:
# https://docs.docker.com/develop/develop-images/multistage-build/

# Provides a base Debian (10) image with latest buildbot mater installed
# the master image is not optimized for size, but rather uses Debian for wider package availability

# Provide an intermediate Docker image named "buildbot-build".
# This intermediate image builds binary wheels
# which get installed in the final image.
# This allows us to avoid installing build tools like gcc in the final image.

FROM        debian:11 AS buildbot-build
MAINTAINER  Buildbot maintainers

# Last build date - this can be updated whenever there are security updates so
# that everything is rebuilt
ENV         security_updates_as_of 2022-03-06

RUN \
    apt-get update && \
    apt-get -y upgrade && \
    apt-get -y install -q \
        curl \
        git \
        libcairo-gobject2 \
        libcairo2-dev \
        libgirepository1.0-dev \
        libglib2.0-dev \
        libffi-dev \
        libpq-dev \
        libssl-dev \
        pkg-config \
        python3 \
        python3-dev \
        python3-pip \
        yarnpkg \
        tar \
        tzdata \
        virtualenv \
        && \
    rm -rf /var/lib/apt/lists/*

COPY . /usr/src/buildbot

RUN cd /usr/src/buildbot && make tarballs
RUN virtualenv --python=python3 /buildbot_venv && \
    /buildbot_venv/bin/pip3 install -r /usr/src/buildbot/requirements-master-docker-extras.txt && \
    env CRYPTOGRAPHY_DONT_BUILD_RUST=1 /buildbot_venv/bin/pip3 install /usr/src/buildbot/dist/*.whl

RUN mkdir -p /wheels && \
    /buildbot_venv/bin/pip3 list --format freeze | grep -v '^buildbot' | grep -v '^pkg-resources' > /wheels/wheels.txt && \
    cat /wheels/wheels.txt && \
    cd /wheels && \
    /buildbot_venv/bin/pip3 wheel -r wheels.txt && \
    rm /wheels/wheels.txt && \
    cp /usr/src/buildbot/dist/*.whl /wheels

#==============================================================================================
# Build the final image here.  Use build artifacts from the buildbot-build
# container.

# Note that the UI and worker packages are the latest version published on pypi
# This is to avoid pulling node inside this container

FROM        debian:11-slim
MAINTAINER  Buildbot maintainers

# Last build date - this can be updated whenever there are security updates so
# that everything is rebuilt
ENV         security_updates_as_of 2022-03-06

RUN \
    apt-get update && \
    apt-get -y upgrade && \
    apt-get -y install -q \
        curl \
        dumb-init \
        git \
        libpq5 \
        libcairo2 \
        openssh-client \
        python3 \
        python3-pip \
        tar \
        tzdata \
        virtualenv \
        && \
    rm -rf /var/lib/apt/lists

# Build wheels in other container using the Dockerfile.build
# and copy them into this container.
# We do this to avoid having to pull gcc for building native extensions.
COPY --from=buildbot-build /wheels /wheels

# install pip dependencies
RUN virtualenv --python=python3 /buildbot_venv && \
    /buildbot_venv/bin/pip3 install --upgrade pip setuptools && \
    cd /wheels && /buildbot_venv/bin/pip3 install $(ls -1 | grep -v 'buildbot-worker') && \
    rm -r /root/.cache /wheels

COPY master/docker/buildbot.tac /usr/src/buildbot/buildbot.tac
COPY master/docker/start_buildbot.sh /usr/src/buildbot/start_buildbot.sh

WORKDIR /buildbot
CMD ["dumb-init", "/usr/src/buildbot/start_buildbot.sh"]
