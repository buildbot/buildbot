# About #

This directory contains the components that comprise the Buildbot web
interface.  The core interface is defined in `www/base`, with other plugins
in sibling directories.

# Connection to Python #

The setup.py script in each directory is designed to create wheel packages
containing pre-built Angular files.  This means that installing the
buildbot-www package from PyPI gets all of the code required to run the
Buildbot UI, without any requirement for Node.js or any NPM install.

The ordinary 'python setup.py sdist' and 'python setup.py install' commands
will work just as expected.

# For Python Hackers #

If you're finding yourself facing errors due to buildbot_www not being
installed, try running `make prebuilt_frontend` in the root directory; this
will install prebuilt versions of each of these distributions, based on the
latest commits to the upstream master.
