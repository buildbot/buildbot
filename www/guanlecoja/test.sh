set -e
gulp scripts vendors
npm link
cd test
npm install
npm link guanlecoja
gulp
gulp --coverage
