#!/bin/bash
set -e
pkg=$1
(
    cd ${pkg}
    rm -rf MANIFEST dist

    python -m build
)
cp ${pkg}/dist/* dist/
