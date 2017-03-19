#!/bin/bash
set -e
set -v
cd `dirname $0`
rm -rf workdir
buildbot create-master workdir
ln -s ../templates ../mydashboard.py ../master.cfg workdir
buildbot-worker create-worker workdir/worker localhost example-worker pass
buildbot checkconfig workdir
# on docker buildbot might be a little bit slower to start, so sleep another 20s in case of start to slow.
buildbot start workdir || sleep 20
buildbot-worker start workdir/worker

# CI mode: use preinstalled protractor with xvfb-run
if [ -f /usr/bin/protractor ]; then
    PROTRACTOR=/usr/bin/protractor
else
    yarn install
    ./node_modules/protractor/bin/webdriver-manager update
    PROTRACTOR=./node_modules/protractor/bin/protractor
fi
if [ -f /usr/bin/xvfb-run ] ; then
    xvfb-run $PROTRACTOR protractor-headless.conf.js
else
    # manual mode: install locally
    yarn install
    ./node_modules/protractor/bin/webdriver-manager update
    ./node_modules/protractor/bin/protractor protractor.conf.js
fi
set +e
buildbot stop workdir
buildbot-worker stop workdir/worker
rm -rf workdir
