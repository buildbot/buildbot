# buildbot/buildbot-master

# please follow docker best practices
# https://docs.docker.com/engine/userguide/eng-image/dockerfile_best-practices/
#

# Use a multi-stage build:
# https://docs.docker.com/develop/develop-images/multistage-build/
#
# Provide an intermediate Docker image named "buildbot-build".
# This intermediate image builds binary wheels
# which get installed in the final image.
# This allows us to avoid installing build tools like gcc in the final image.

FROM        alpine:3.7 AS buildbot-build
MAINTAINER  Buildbot maintainers

# Last build date - this can be updated whenever there are security updates so
# that everything is rebuilt
ENV         security_updates_as_of 2018-04-10


COPY . /usr/src/buildbot
RUN \
    echo @edgecommunity http://nl.alpinelinux.org/alpine/edge/community >> /etc/apk/repositories && \
    echo @testing http://nl.alpinelinux.org/alpine/edge/testing >> /etc/apk/repositories && \
    apk add --no-cache \
        git \
        python-dev \
        libffi-dev \
        libressl-dev \
        postgresql-dev \
        py-pip \
        alpine-sdk \
        tar \
        tzdata \
        curl && \
# install pip dependencies
    pip install --upgrade pip setuptools wheel && \
    pip install "buildbot[bundle,tls]" && \
    pip install -r /usr/src/buildbot/requirements-docker-extras.txt && \
    pip install "/usr/src/buildbot" && \
    mkdir -p wheels && \
    pip list --format freeze | grep -v '^buildbot=' > wheels/wheels.txt && \
    cd wheels && \
    pip wheel -r wheels.txt



#==============================================================================================
# Build the final image here.  Use build artifacts from the buildbot-build
# container.

# Note that the UI and worker packages are the latest version published on pypi
# This is to avoid pulling node inside this container

FROM        alpine:3.7
MAINTAINER  Buildbot maintainers

# Last build date - this can be updated whenever there are security updates so
# that everything is rebuilt
ENV         security_updates_as_of 2018-04-11


COPY . /usr/src/buildbot

# Build wheels in other container using the Dockerfile.build
# and copy them into this container.
# We do this to avoid having to pull gcc for building native extensions.
COPY --from=buildbot-build /wheels /wheels
RUN \
    echo @edgecommunity http://nl.alpinelinux.org/alpine/edge/community >> /etc/apk/repositories && \
    echo @testing http://nl.alpinelinux.org/alpine/edge/testing >> /etc/apk/repositories && \
    apk add --no-cache \
        git \
        python \
        postgresql-libs \
        py-pip \
        gosu@testing \
        dumb-init \
        tar \
        tzdata \
        curl \
        openssh && \
# install pip dependencies
    pip install --upgrade pip setuptools && \
    pip install /wheels/*.whl && \
    pip install "buildbot[bundle,tls]" && \
    pip install "/usr/src/buildbot" && \
    rm -r /root/.cache /wheels


WORKDIR /var/lib/buildbot
CMD ["dumb-init", "/usr/src/buildbot/docker/start_buildbot.sh"]
