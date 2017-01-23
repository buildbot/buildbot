#!/bin/bash
find . -name VERSION -exec rm {} \;
rm -rf dist
mkdir dist
pip install mock wheel
set -e
for pkg in pkg master worker www/base www/console_view www/waterfall_view
do
  pip install -e ${pkg}
  (
    cd ${pkg}
    rm -rf MANIFEST dist
    python setup.py sdist
    # wheels must be build separatly in order to properly omit tests
    python setup.py bdist_wheel
  )
  cp ${pkg}/dist/* dist/
done
