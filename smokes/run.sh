#!/bin/bash
set -e
set -v
cd `dirname $0`
yarn install
rm -rf workdir
buildbot create-master workdir
cp master.cfg workdir
buildbot-worker create-worker workdir/worker localhost example-worker pass
buildbot start workdir
buildbot-worker start workdir/worker
./node_modules/protractor/bin/webdriver-manager update
./node_modules/protractor/bin/protractor protractor.conf.js
buildbot stop workdir
buildbot-worker stop workdir/worker
rm -rf workdir
