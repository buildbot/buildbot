#!/bin/bash
find . -name VERSION -exec rm {} \;
rm -rf dist
mkdir dist
for pkg in pkg master slave pkg www/base www/console_view www/waterfall_view
do
  pip install -e ${pkg}
  (
    cd ${pkg}
    rm -rf MANIFEST dist
    python setup.py sdist
  )
  cp ${pkg}/dist/* dist/
  pip wheel ${pkg} -w dist
done
