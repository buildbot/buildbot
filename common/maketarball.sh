#!/bin/bash
set -e
pkg=$1
(
    cd ${pkg}
    rm -rf MANIFEST dist
    if [ ${pkg} == "master" ] || [ ${pkg} == "worker" ]; then
        python setup.py sdist
        # wheels must be build separately in order to properly omit tests
        python setup.py bdist_wheel
    else
        # retry once to workaround instabilities
        python setup.py sdist bdist_wheel || (git clean -xdf; python setup.py sdist bdist_wheel)
    fi
)
cp ${pkg}/dist/* dist/
