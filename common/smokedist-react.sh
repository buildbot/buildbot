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
    uv venv --python "python${python:-3}" $VE
    . $VE/bin/activate
    uv pip install requests==2.32.3 flask==3.0.3
    uv pip install dist/buildbot-[0-9]*.$suffix
    uv pip install dist/*.$suffix
    e2e/run.sh
done
