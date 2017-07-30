#!/bin/bash
set -e
set -v
cd `dirname $0`
function finish {
    # uncomment for debug in hyper
    # for i in `seq 1000`
    # do
    #   echo please debug me!
    #   sleep 60
    # done
    set +e
    kill %1
    buildbot stop workdir
    buildbot-worker stop workdir/worker
    rm -rf workdir
}
trap finish EXIT
rm -rf workdir
buildbot create-master workdir
ln -s ../templates ../mydashboard.py ../master.cfg workdir
buildbot-worker create-worker workdir/worker localhost example-worker pass
buildbot checkconfig workdir
# on docker buildbot might be a little bit slower to start, so sleep another 20s in case of start to slow.
buildbot start workdir || sleep 20
buildbot-worker start workdir/worker
cat workdir/twistd.log &

# CI mode: use preinstalled protractor with xvfb-run
if [ -f /usr/bin/protractor ]; then
    PROTRACTOR=/usr/bin/protractor
else
    yarn install --pure-lockfile
    ./node_modules/protractor/bin/webdriver-manager update
    PROTRACTOR=./node_modules/protractor/bin/protractor
fi
if [ -f /usr/bin/xvfb-run ] ; then
    xvfb-run --server-args="-screen 0 1024x768x24" $PROTRACTOR protractor-headless.conf.js
else
    # manual mode: install locally
    yarn install
    ./node_modules/protractor/bin/webdriver-manager update
    ./node_modules/protractor/bin/protractor protractor.conf.js
fi
