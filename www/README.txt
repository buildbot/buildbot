# About #

This is buildbot-www, the Buildbot UI.

# Connection to Python #

The setup.py script here is designed to create sdist (source-distribution)
packages containing pre-built Angular files.  This means that installing the
buildbot-www package from PyPi gets all of the code required to run the
Buildbot UI, without any requirement for Node.js or any NPM install.

The ordinary 'python setup.py sdist' and 'python setup.py install' commands
will work just as expected.

# Hacking #

To hack on the UI, first install it into your Python virtualenv with `pip
install -e www`, run from the top-level of the git repository.  This will
configure the Python glue to use the built version at `www/buildbot_www`.
This command will use Node.js and NPM to install all of the prerequisites for
building the UI.

Then, simply treat the `www` directory as a normal AngularJs project.  Either
run `gulp` to build on demand, or use `gulp dev` to set up a watcher to
build whenever files change.
