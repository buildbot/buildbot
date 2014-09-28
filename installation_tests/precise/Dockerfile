FROM ubuntu:precise

RUN apt-get update && apt-get install -y python-software-properties && add-apt-repository -y ppa:chris-lea/node.js && apt-get update

RUN apt-get install -y python-virtualenv wget unzip python python-dev python-distribute python-pip nodejs libmysqlclient-dev git bzip2
RUN wget  --no-check-certificate https://github.com/tardyp/buildbot/archive/pkg_fixes.zip -O /tmp/master.zip
#RUN wget --no-check-certificate https://github.com/buildbot/buildbot/archive/master.zip -O /tmp/master.zip
ADD install.sh /tmp/install.sh
RUN /bin/bash /tmp/install.sh
