# buildbot/buildbot-master

# Provides a base alpine 3.4 image with latest buildbot master installed
# Alpine base build is ~130MB vs ~500MB for the ubuntu build

FROM        alpine:3.4
MAINTAINER  Buildbot maintainers

# Last build date - this can be updated whenever there are security updates so
# that everything is rebuilt
ENV         security_updates_as_of 2016-06-20
COPY . /usr/src/buildbot
# We install as much as possible python packages from the distro in order to avoid
# having to pull gcc for building native extensions
# Some packages are at the moment (06/2016) only available on @testing
RUN \
    echo @testing http://nl.alpinelinux.org/alpine/edge/testing >> /etc/apk/repositories && \
    apk add --no-cache \
    python \
    py-pip \
    py-psycopg2 py-twisted py-cryptography \
    py-service_identity@testing py-sqlalchemy@testing \
    gosu@testing dumb-init@testing\
    py-jinja2 && \
    python -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip install --upgrade pip setuptools && \
    pip install  --pre "buildbot[bundle]" && \
    pip install  "/usr/src/buildbot" && \
    rm -r /root/.cache

WORKDIR /var/lib/buildbot
VOLUME /var/lib/buildbot
CMD ["/usr/src/buildbot/contrib/docker/master/start_buildbot.sh"]
