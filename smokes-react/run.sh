#!/bin/bash
set -e
set -v
cd `dirname $0`

YARN=$(which yarnpkg || which yarn)
if [ $?  -ne 0 ]; then
    echo "Neither yarnpkg nor yarn is available"
    exit 1
fi

echo "Using ${YARN} as yarn"

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
trap finish EXIT
rm -rf workdir
buildbot create-master workdir
ln -s ../templates ../mydashboard.py ../master.cfg workdir
buildbot-worker create-worker workdir/worker localhost example-worker pass
buildbot checkconfig workdir
# on docker buildbot might be a little bit slower to start, so sleep another 20s in case of start to slow.
buildbot start workdir || sleep 20
buildbot-worker start workdir/worker

trap finish EXIT
cat workdir/twistd.log &

yarn install --pure-lockfile
yarn playwright install
yarn playwright test
