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
        python3 -m venv $VE
    else
        python$python -m venv $VE
    fi
    . $VE/bin/activate
    pip install -r requirements-pip.txt
    pip install requests==2.32.3 flask==3.0.3
    pip install dist/buildbot-[0-9]*.$suffix
    pip install dist/buildbot?pkg*.$suffix
    pip install dist/*.$suffix
    e2e/run.sh
done
