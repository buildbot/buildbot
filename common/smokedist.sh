#!/bin/bash


set -e
for suffix in whl tar.gz
do
    VE=sandbox.$suffix
    rm -rf $VE
    virtualenv $VE
    . $VE/bin/activate
    pip install -U pip
    pip install  mock
    pip install dist/buildbot-0*.$suffix
    pip install dist/buildbot?pkg*.$suffix
    pip install dist/*.$suffix
    smokes/run.sh
done
