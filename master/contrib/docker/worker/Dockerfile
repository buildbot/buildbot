# Provides a base Ubuntu (14.04) image with latest buildbot worker installed
# (based on twsited dockerfile https://github.com/cyli/docker-twisted)

FROM        ubuntu:14.04
MAINTAINER  Buildbot maintainers

# Last build date - this can be updated whenever there are security updates so
# that everything is rebuilt
ENV         security_updates_as_of 2015-09-13

# Install security updates and required packages
RUN         apt-get update && \
            apt-get -y upgrade && \
            apt-get -y install -q build-essential && \
            apt-get -y install -q python-dev libffi-dev libssl-dev python-pip

# Install required python packages, and twisted
RUN         pip install service_identity pycrypto && \
            pip install twisted==14.0.0 && \
            pip install buildbot-slave

WORKDIR /buildbot/
ADD buildbot.tac /buildbot/buildbot.tac

CMD ["twistd", "-ny", "buildbot.tac"]
