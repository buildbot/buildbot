#!/bin/bash
set -e
set -v
cd `dirname $0`

NPM=$(which npm)
if [ $?  -ne 0 ]; then
    echo "npm is not available"
    exit 1
fi

echo "Using ${NPM}"

function finish_failed_start {
    set +e
    kill %1
    buildbot stop workdir
    cat workdir/twistd.log
    rm -rf workdir
}

function finish {
    # uncomment for debug in kube
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

trap finish_failed_start EXIT

rm -rf workdir
buildbot create-master workdir
ln -s ../templates ../master.cfg workdir
buildbot-worker create-worker workdir/worker localhost example-worker pass
buildbot checkconfig workdir
# on docker buildbot might be a little bit slower to start, so sleep another 20s in case of start to slow.
buildbot start workdir || sleep 20

buildbot-worker start workdir/worker

trap finish EXIT
cat workdir/twistd.log &

NPM=`which npm`
if [ -z $NPM ]; then
    echo "npm is not available"
    exit 1
fi

$NPM ci
$NPM exec playwright install
LIBGL_ALWAYS_SOFTWARE=1 $NPM exec playwright test
