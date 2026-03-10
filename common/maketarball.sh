#!/bin/bash
set -e
pkg=$1
(
    cd ${pkg}
    rm -rf MANIFEST dist
    if [ ${pkg} == "pkg" ]; then
        python -m build --no-isolation --sdist
        # wheels must be build separately in order to properly omit tests
        python -m build --no-isolation --wheel
    else
        python -m build
    fi
)
cp ${pkg}/dist/* dist/
