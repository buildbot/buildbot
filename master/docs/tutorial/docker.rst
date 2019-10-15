.. _first-run-docker-label:

==============================
First Buildbot run with Docker
==============================

.. note::

    Docker can be tricky to get working correctly if you haven't used it before.
    If you're having trouble, first determine whether it is a Buildbot issue or a Docker issue by running:

    .. code-block:: bash

      docker run ubuntu:12.04 apt-get update

    If that fails, look for help with your Docker install.
    On the other hand, if that succeeds, then you may have better luck getting help from members of the Buildbot community.


Docker_ is a tool that makes building and deploying custom environments a breeze.
It uses lightweight linux containers (LXC) and performs quickly, making it a great instrument for the testing community.
The next section includes a Docker pre-flight check.
If it takes more that 3 minutes to get the 'Success' message for you, try the Buildbot pip-based :ref:`first run <getting-code-label>` instead.

.. _Docker: https://www.docker.com

Current Docker dependencies
---------------------------

* Linux system, with at least kernel 3.8 and AUFS support.
  For example, Standard Ubuntu, Debian and Arch systems.
* Packages: lxc, iptables, ca-certificates, and bzip2 packages.
* Local clock on time or slightly in the future for proper SSL communication.
* This tutorial uses docker-compose to run a master, a worker, and a postgresql database server

Installation
------------

* Use the `Docker installation instructions <https://docs.docker.com/engine/installation/>`_ for your operating system.

* Make sure you install docker-compose.
  As root or inside a virtualenv, run:

  .. code-block:: bash

    pip install docker-compose

* Test docker is happy in your environment:

  .. code-block:: bash

    sudo docker run -i busybox /bin/echo Success

Building and running Buildbot
-----------------------------

.. code-block:: bash

  # clone the example repository
  git clone --depth 1 https://github.com/buildbot/buildbot-docker-example-config

  # Build the Buildbot container (it will take a few minutes to download packages)
  cd buildbot-docker-example-config/simple
  docker-compose up


You should now be able to go to http://localhost:8010 and see a web page similar to:

.. image:: _images/index.png
   :alt: index page

Click on "Builds" at the left to open the submenu and then `Builders <http://localhost:8010/#/builders>`_ to see that the worker you just started has connected to the master:

.. image:: _images/builders.png
   :alt: builder runtests is active.


Overview of the docker-compose configuration
--------------------------------------------

This docker-compose configuration is made as a basis for what you would put in production

- Separated containers for each component
- A solid database backend with postgresql
- A buildbot master that exposes its configuration to the docker host
- A buildbot worker that can be cloned in order to add additional power
- Containers are linked together so that the only port exposed to external is the web server
- The default master container is based on Alpine linux for minimal footprint
- The default worker container is based on more widely known Ubuntu distribution, as this is the container you want to customize.
- Download the config from a tarball accessible via a web server

Playing with your Buildbot containers
-------------------------------------

If you've come this far, you have a Buildbot environment that you can freely experiment with.

In order to modify the configuration, you need to fork the project on github https://github.com/buildbot/buildbot-docker-example-config
Then you can clone your own fork, and start the docker-compose again.

To modify your config, edit the master.cfg file, commit your changes, and push to your fork.
You can use the command buildbot check-config in order to make sure the config is valid before the push.
You will need to change ``docker-compose.yml`` the variable ``BUILDBOT_CONFIG_URL`` in order to point to your github fork.

The ``BUILDBOT_CONFIG_URL`` may point to a ``.tar.gz`` file accessible from HTTP.
Several git servers like github can generate that tarball automatically from the master branch of a git repository
If the ``BUILDBOT_CONFIG_URL`` does not end with ``.tar.gz``, it is considered to be the URL to a ``master.cfg`` file accessible from HTTP.

Customize your Worker container
-------------------------------
It is advised to customize you worker container in order to suit your project's build dependencies and need.
An example DockerFile is available which the buildbot community uses for its own CI purposes:

https://github.com/buildbot/metabbotcfg/blob/nine/docker/metaworker/Dockerfile

Multi-master
------------
A multi-master environment can be setup using the ``multimaster/docker-compose.yml`` file in the example repository

  # Build the Buildbot container (it will take a few minutes to download packages)
  cd buildbot-docker-example-config/simple
  docker-compose up -d
  docker-compose scale buildbot=4

Going forward
-------------

You've got a taste now, but you're probably curious for more.
Let's step it up a little in the second tutorial by changing the configuration and doing an actual build.
Continue on to :ref:`quick-tour-label`.
