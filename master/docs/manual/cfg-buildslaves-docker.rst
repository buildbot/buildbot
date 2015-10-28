.. index::
    Docker
    Buildslaves; Docker

Docker latent BuildSlave
========================

Docker_ is an open-source project that automates the deployment of applications inside software containers.
Using the Docker latent BuildSlave, an attempt is made at instantiating a fresh image upon each build, assuring consistency of the environment between builds.
Each image will be discarded once the slave finished processing the build queue (i.e. becomes ``idle``).
See :ref:`build_wait_timeout <Common-Latent-Buildslaves-Options>` to change this behavior.

This document will guide you through the setup of such slaves.

.. contents::
   :depth: 1
   :local:

.. _Docker: https://docker.com

Docker Installation
-------------------

An easy way to try Docker is through installation of dedicated Virtual machines.
Two of them stands out:

- CoreOS_
- boot2docker_

Beside, it is always possible to install Docker next to the buildmaster.
Beware that in this case, overall performance will depend on how many builds the computer where you have your buildmaster can handle as everything will happen on the same one.

.. note::
    It is not necessary to install Docker in the same environment as your master as we will make use to the Docker API through docker-py_.
    More in `master setup`_.

.. _CoreOS: https://coreos.com/
.. _boot2docker: http://boot2docker.io/
.. _docker-py: https://pypi.python.org/pypi/docker-py

CoreOS
......

CoreOS is targeted at building infrastructure and distributed systems.
In order to get the latent BuildSlave working with CoreOS, it is necessary to `expose the docker socket`_ outside of the Virtual Machine.
If you installed it via Vagrant_, it is also necessary to uncomment the following line in your :file:`config.rb` file:

.. code-block:: ruby

    $expose_docker_tcp=2375

The following command should allow you to confirm that your Docker socket is now available via the network:


.. code-block:: bash

    docker -H tcp://127.0.0.1:2375 ps

.. _`expose the docker socket`: https://coreos.com/docs/launching-containers/building/customizing-docker/
.. _Vagrant: https://coreos.com/docs/running-coreos/platforms/vagrant/

boot2docker
...........

boot2docker is one of the fastest ways to boot to Docker.
As it is meant to be used from outside of the Virtual Machine, the socket is already exposed.
Please follow the installation instructions on how to find the address of your socket.

Image Creation
--------------

Our build master will need the name of an image to perform its builds.
Each time a new build will be requested, the same base image will be used again and again, actually discarding the result of the previous build.
If you need some persistant storage between builds, you can `use Volumes <setting up volumes>`_.

Each Docker image has a single purpose.
Our buildslave image will be running a buildbot slave.

Docker uses ``Dockerfile``\s to describe the steps necessary to build an image.
The following example will build a minimal buildslave.
Don't forget to add your dependencies in there to get a succesfull build !

..
    XXX(sa2ajj): with Pygments 2.0 or better the following 'none' can be replaced with Docker to get proper syntax highlighting.

.. code-block:: none
    :linenos:
    :emphasize-lines: 11

    FROM debian:stable
    RUN apt-get update && apt-get install -y \
       python-dev \
       python-pip
    RUN pip install buildbot-slave
    RUN groupadd -r buildbot && useradd -r -g buildbot buildbot
    RUN mkdir /buildslave && chown buildbot:buildbot /buildslave
    # Install your build-dependencies here ...
    USER buildbot
    WORKDIR /buildslave
    RUN buildslave create-slave . <master-hostname> <slavename> <slavepassword>
    ENTRYPOINT ["/usr/local/bin/buildslave"]
    CMD ["start", "--nodaemon"]

On line 11, the hostname for your master instance, as well as the slave name and password is setup.
Don't forget to replace those values with some valid ones for your project.

It is a good practice to set the ``ENTRYPOINT`` to the buildslave executable, and the ``CMD`` to ``["start", "--nodaemon"]``.
This way, no parameter will be required when starting the image.

When your Dockerfile is ready, you can build your first image using the following command (replace *myslavename* with a relevant name for your case):

.. code-block:: bash

    docker build -t myslavename - < Dockerfile

Reuse same image for different slaves
-------------------------------------

Previous simple example hardcodes the slave name into the dockerfile, which will not work if you want to share your docker image between slaves.

You can find in buildbot source code in ``master/contrib/docker`` two example configurations:

``slave``
    the base buildslave configuration, including a custom buildbot.tac, which takes environment variables into account for setting the correct slave name, and connect to the correct master.

``pythonnode_slave``
    a slave with python and node installed, which demonstrate how to reuse the base slave to create variations of build environments.

The master setups several environment variables before starting the buildslaves:

``BUILDMASTER``
    The address of the master the slave shall connect to

``BUILDMASTER_PORT``
    The port of the master's slave 'pb' protocol.

``SLAVENAME``
    The name the slave should use to connect to master

``SLAVEPASS``
    The password the slave should use to connect to master

Master Setup
------------

We will rely on docker-py to connect our master with docker.
Now is the time to install it in your master environment.

Before adding the slave to your master configuration, it is possible to validate the previous steps by starting the newly created image interactively.
To do this, enter the following lines in a python prompt where docker-py is installed::

    >>> import docker
    >>> docker_socket = 'tcp://localhost:2375'
    >>> client = docker.client.Client(base_url=docker_socket)
    >>> slave_image = 'my_project_slave'
    >>> container = client.create_container(slave_image)
    >>> client.start(container['Id'])
    >>> # Optionally examine the logs of the master
    >>> client.stop(container['Id'])
    >>> client.wait(container['Id'])
    0

It is now time to add the new build slave to the master configuration under :bb:cfg:`slaves`.

The following example will add a Docker latent slave for docker running at the following adress: ``tcp://localhost:2375``, the slave name will be ``docker``, its password: ``password``, and the base image name will be ``my_project_slave``::

    from buildbot.plugins import buildslave
    c['slaves'] = [
        buildslave.DockerLatentBuildSlave('docker', 'password',
                                          docker_host='tcp://localhost:2375',
                                          image='my_project_slave')
    ]

In addition to the arguments available for any :ref:`Latent-Buildslaves`, :class:`DockerLatentBuildSlave` will accept the following extra ones:

``docker_host``
    (mandatory)
    This is the adress the master will use to connect with a running Docker instance.

``image``
    (optional if ``dockerfile`` is given)
    This is the name of the image that will be started by the build master. It should start a buildslave.
    This option can be a renderable, like :ref:`Interpolate`, so that it generates from the build request properties.
    
``command``
    (optional)
    This will override the command setup during image creation.

``volumes``
    (optional)
    See `Setting up Volumes`_

``dockerfile``
    (optional if ``image`` is given)
    This is the content of the Dockerfile that will be used to build the specified image if the image is not found by Docker.
    It should be a multiline string.

    .. note:: In case ``image`` and ``dockerfile`` are given, no attempt is made to compare the image with the content of the Dockerfile parameter if the image is found.

``version``
    (optional, default to the highest version known by docker-py)
    This will indicates wich API version must be used to communicate with Docker.

``tls``
    (optional)
    This allow to use TLS when connecting with the Docker socket.
    This should be a ``docker.tls.TLSConfig`` object.
    See `docker-py's own documentation <http://docker-py.readthedocs.org/en/latest/tls/>`_ for more details on how to initialise this object.

``followStartupLogs``
    (optional, defaults to false)
    This transfers docker container's log inside master logs during slave startup (before connection). This can be useful to debug slave startup. e.g network issues, etc.

``masterFQDN``
    (optional, defaults to socket.getfqdn())
    Address of the master the slave should connect to. Use if you master machine does not have proper fqdn.
    This value is passed to the docker image via environment variable ``BUILDMASTER``

Setting up Volumes
..................

The ``volume`` parameter allows to share directory between containers, or between a container and the host system.
Refer to Docker documentation for more information about Volumes.

The format of that variable has to be an array of string.
Each string specify a volume in the following format: :samp:`{volumename}:{bindname}`.
The volume name has to be appended with ``:ro`` if the volume should be mounted *read-only*.

.. note:: This is the same format as when specifying volumes on the command line for docker's own ``-v`` option.
