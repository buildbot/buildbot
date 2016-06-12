Buildbot-Master docker container
================================

[Buildbot](http://buildbot.net) is a continuous integration framework written and configured in python.

You can look at the [tutorial](http://docs.buildbot.net/latest/tutorial/docker.html) to learn how to use it.

This container is based on alpine linux, and thus very lightweight. Another version based on ubuntu exists if you need more custom environment.

The container expects a /var/lib/buildbot volume to store its configuration, and will open port 8010 for web server, and 9989 for worker connection.
It is also expecting a postgresql container attached for storing state.
