#!/bin/bash

if [ -z $1 ]; then
    suffixes="whl tar.gz"
else
    suffixes=$1
fi
set -e
for suffix in $suffixes
do
    VE=sandbox.$suffix
    rm -rf $VE
    if [ -z "$python" ]; then
        virtualenv $VE
    else
        virtualenv --python python$python $VE
    fi
    . $VE/bin/activate
    pip install -U pip
    pip install  mock requests flask
    pip install dist/buildbot-1*.$suffix
    pip install dist/buildbot?pkg*.$suffix
    pip install dist/*.$suffix
    smokes/run.sh
done
