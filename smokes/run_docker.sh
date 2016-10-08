#!/bin/bash
docker rm -f buildmaster
docker rm -f buildworker
function finish {
    docker rm -f buildmaster
    docker rm -f buildworker
}
trap finish EXIT

set -e
set -v
cd `dirname $0`
npm install
./node_modules/protractor/bin/webdriver-manager update


MASTER_IMAGE=${MASTER_IMAGE:-buildbot/buildbot-master:master}
WORKER_IMAGE=${WORKER_IMAGE:-buildbot/buildbot-worker:master}
BUILDBOT_CONFIG_URL=${BUILDBOT_CONFIG_URL:-https://raw.githubusercontent.com/buildbot/buildbot/master/smokes/master.cfg}

MASTERENV="-e http_proxy=$http_proxy -e https_proxy=$https_proxy -e BUILDBOT_CONFIG_DIR=config -e BUILDBOT_CONFIG_URL=$BUILDBOT_CONFIG_URL"
docker run --name buildmaster $MASTERENV -d -p 8010:8010 -p 9989:9989 -h buildmaster $MASTER_IMAGE

WORKERENV="-e https_proxy=$https_proxy -e BUILDMASTER=buildmaster -e BUILDMASTER_PORT=9989 -e WORKERNAME=example-worker -e WORKERPASS=pass"
docker run --name buildworker --link buildmaster -d $WORKERENV $WORKER_IMAGE

until curl http://localhost:8010 >/dev/null 2>/dev/null
do
docker logs buildmaster
sleep 1
done
./node_modules/protractor/bin/protractor protractor.conf.js
