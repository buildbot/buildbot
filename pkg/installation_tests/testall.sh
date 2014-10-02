#!/bin/bash
if [[ ! -d pkg || ! -d .git ]]
then
    echo This script is supposed to be run from the root of the git cloned buildbot repository >> /dev/stderr
    exit 1
fi
git archive --prefix buildbot-master/ --format zip --output pkg/installation_tests/common/master.zip HEAD
cd pkg/installation_tests
find . -type d | while read dir
do
    if [[ -f $dir/Dockerfile ]]
    then
        cp -rf common $dir
        docker build $dir || exit 1
    fi
done
