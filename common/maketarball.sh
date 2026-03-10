#!/bin/bash
set -e
pkg=$1
(
    cd ${pkg}
    rm -rf MANIFEST dist
    if [ ${pkg} == "master" ] || \
        [ ${pkg} == "www/base" ] || \
        [ ${pkg} == "www/console_view" ] || \
        [ ${pkg} == "www/badges" ]; then
        python -m build
    elif [ ${pkg} == "worker" ] || [ ${pkg} == "pkg" ]; then
        python -m build --no-isolation --sdist
        # wheels must be build separately in order to properly omit tests
        python -m build --no-isolation --wheel
    else
        # retry once to workaround instabilities
        python -m build --no-isolation || (git clean -xdf; python -m build --no-isolation)
    fi
)
cp ${pkg}/dist/* dist/
