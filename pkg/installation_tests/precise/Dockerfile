FROM ubuntu:precise

RUN apt-get update && \
    apt-get install -y python-software-properties && \
    add-apt-repository -y ppa:chris-lea/node.js && \
    apt-get update && \
    apt-get install -y python-virtualenv wget unzip python python-dev python-distribute \
                       python-pip nodejs libmysqlclient-dev git bzip2

ADD common /buildbot
RUN /bin/bash /buildbot/install.sh
