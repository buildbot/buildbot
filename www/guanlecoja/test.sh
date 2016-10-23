set -e
gulp scripts vendors
yarn link || true
cd test
yarn install
yarn link guanlecoja ||true
gulp
gulp --coverage
