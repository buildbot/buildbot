#!/bin/bash


set -e
for suffix in whl tar.gz
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
    pip install dist/buildbot-0*.$suffix
    pip install dist/buildbot?pkg*.$suffix
    pip install dist/*.$suffix
    smokes/run.sh
done
