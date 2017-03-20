# buildbot/buildbot-master

# please follow docker best practices
# https://docs.docker.com/engine/userguide/eng-image/dockerfile_best-practices/
#
# Provides a base alpine 3.4 image with latest buildbot master installed
# Alpine base build is ~130MB vs ~500MB for the ubuntu build

# Note that the UI and worker packages are the latest version published on pypi
# This is to avoid pulling node inside this container

FROM        alpine:3.5
MAINTAINER  Buildbot maintainers

# Last build date - this can be updated whenever there are security updates so
# that everything is rebuilt
ENV         security_updates_as_of 2017-02-08


COPY . /usr/src/buildbot
# We install as much as possible python packages from the distro in order to avoid
# having to pull gcc for building native extensions
# Some packages are at the moment (10/2016) only available on @testing
RUN \
    echo @testing http://nl.alpinelinux.org/alpine/edge/testing >> /etc/apk/repositories && \
    echo @edge http://nl.alpinelinux.org/alpine/edge/community >> /etc/apk/repositories && \
    apk add --no-cache \
        git \
        python \
        py-pip \
        py-psycopg2 \
        py-twisted \
        py-cffi \
        py-openssl@edge \
        py-cryptography@edge \
        py-service_identity@edge \
        py-sqlalchemy@edge \
        gosu@testing \
        dumb-init@edge\
        py-jinja2 \
        tar \
        tzdata \
        curl && \
# install pip dependencies
    pip install --upgrade pip setuptools && \
    pip install "buildbot[bundle,tls]" && \
    pip install "/usr/src/buildbot" && \
    rm -r /root/.cache

WORKDIR /var/lib/buildbot
CMD ["dumb-init", "/usr/src/buildbot/docker/start_buildbot.sh"]
