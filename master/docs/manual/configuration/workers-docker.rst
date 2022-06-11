.. index::
    Docker
    Workers; Docker

.. bb:worker:: DockerLatentWorker

Docker latent worker
====================

.. py:class:: buildbot.worker.docker.DockerLatentWorker
.. py:class:: buildbot.plugins.worker.DockerLatentWorker

Docker_ is an open-source project that automates the deployment of applications inside software containers.
The :class:`DockerLatentWorker` attempts to instantiate a fresh image for each build to assure consistency of the environment between builds.
Each image will be discarded once the worker finished processing the build queue (i.e. becomes ``idle``).
See :ref:`build_wait_timeout <Common-Latent-Workers-Options>` to change this behavior.

This document will guide you through the setup of such workers.

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
.. _boot2docker: https://github.com/boot2docker/boot2docker
.. _docker-py: https://pypi.python.org/pypi/docker-py

CoreOS
......

CoreOS is targeted at building infrastructure and distributed systems.
In order to get the latent worker working with CoreOS, it is necessary to `expose the docker socket`_ outside of the Virtual Machine.
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
If you need some persistent storage between builds, you can `use Volumes <setting up volumes>`_.

Each Docker image has a single purpose.
Our worker image will be running a buildbot worker.

Docker uses ``Dockerfile``\s to describe the steps necessary to build an image.
The following example will build a minimal worker.
This example is voluntarily simplistic, and should probably not be used in production, see next paragraph.

.. code-block:: Docker
    :linenos:
    :emphasize-lines: 11

    FROM debian:stable
    RUN apt-get update && apt-get install -y \
       python-dev \
       python-pip
    RUN pip install buildbot-worker
    RUN groupadd -r buildbot && useradd -r -g buildbot buildbot
    RUN mkdir /worker && chown buildbot:buildbot /worker
    # Install your build-dependencies here ...
    USER buildbot
    WORKDIR /worker
    RUN buildbot-worker create-worker . <master-hostname> <workername> <workerpassword>
    ENTRYPOINT ["/usr/local/bin/buildbot-worker"]
    CMD ["start", "--nodaemon"]

On line 11, the hostname for your master instance, as well as the worker name and password is setup.
Don't forget to replace those values with some valid ones for your project.

It is a good practice to set the ``ENTRYPOINT`` to the worker executable, and the ``CMD`` to ``["start", "--nodaemon"]``.
This way, no parameter will be required when starting the image.

When your Dockerfile is ready, you can build your first image using the following command (replace *myworkername* with a relevant name for your case):

.. code-block:: bash

    docker build -t myworkername - < Dockerfile

Reuse same image for different workers
--------------------------------------

Previous simple example hardcodes the worker name into the dockerfile, which will not work if you want to share your docker image between workers.

You can find in buildbot source code in :contrib-src:`master/contrib/docker` one example configurations:

:contrib-src:`pythonnode_worker <master/contrib/docker/pythonnode_worker/>`
    a worker with Python and node installed, which demonstrate how to reuse the base worker to create variations of build environments.
    It is based on the official ``buildbot/buildbot-worker`` image.

The master setups several environment variables before starting the workers:

``BUILDMASTER``
    The address of the master the worker shall connect to

``BUILDMASTER_PORT``
    The port of the master's worker 'pb' protocol.

``WORKERNAME``
    The name the worker should use to connect to master

``WORKERPASS``
    The password the worker should use to connect to master

Master Setup
------------

We will rely on docker-py to connect our master with docker.
Now is the time to install it in your master environment.

Before adding the worker to your master configuration, it is possible to validate the previous steps by starting the newly created image interactively.
To do this, enter the following lines in a Python prompt where docker-py is installed:

.. code-block:: python

    >>> import docker
    >>> docker_socket = 'tcp://localhost:2375'
    >>> client = docker.client.APIClient(base_url=docker_socket)
    >>> worker_image = 'my_project_worker'
    >>> container = client.create_container(worker_image)
    >>> client.start(container['Id'])
    >>> # Optionally examine the logs of the master
    >>> client.stop(container['Id'])
    >>> client.wait(container['Id'])
    0

It is now time to add the new worker to the master configuration under :bb:cfg:`workers`.

The following example will add a Docker latent worker for docker running at the following address: ``tcp://localhost:2375``, the worker name will be ``docker``, its password: ``password``, and the base image name will be ``my_project_worker``:

.. code-block:: python

    from buildbot.plugins import worker
    c['workers'] = [
        worker.DockerLatentWorker('docker', 'password',
                                  docker_host='tcp://localhost:2375',
                                  image='my_project_worker')
    ]

``password``
    (mandatory)
    The worker password part of the :ref:`Latent-Workers` API.
    If the password is ``None``, then it will be automatically generated from random number, and transmitted to the container via environment variable.

In addition to the arguments available for any :ref:`Latent-Workers`, :class:`DockerLatentWorker` will accept the following extra ones:

``docker_host``
    (renderable string, mandatory)
    This is the address the master will use to connect with a running Docker instance.

``image``
    (renderable string, mandatory)
    This is the name of the image that will be started by the build master. It should start a worker.
    This option can be a renderable, like :ref:`Interpolate`, so that it generates from the build request properties.

``command``
    (optional)
    This will override the command setup during image creation.

``volumes``
    (a renderable list of strings, optional)
    Allows to share directory between containers, or between a container and the host system.
    Refer to Docker documentation for more information about Volumes.

    Each string within the ``volumes`` array specify a volume in the following format: :samp:`{volumename}:{bindname}`.
    The volume name has to be appended with ``:ro`` if the volume should be mounted *read-only*.

    .. note:: This is the same format as when specifying volumes on the command line for docker's own ``-v`` option.

``dockerfile``
    (renderable string, optional if ``image`` is given)
    This is the content of the Dockerfile that will be used to build the specified image if the image is not found by Docker.
    It should be a multiline string.

    .. note:: In case ``image`` and ``dockerfile`` are given, no attempt is made to compare the image with the content of the Dockerfile parameter if the image is found.

``version``
    (optional, default to the highest version known by docker-py)
    This will indicates which API version must be used to communicate with Docker.

``tls``
    (optional)
    This allow to use TLS when connecting with the Docker socket.
    This should be a ``docker.tls.TLSConfig`` object.
    See `docker-py's own documentation <https://docker-py.readthedocs.io/en/stable/tls.html>`_ for more details on how to initialise this object.

``followStartupLogs``
    (optional, defaults to false)
    This transfers docker container's log inside master logs during worker startup (before connection). This can be useful to debug worker startup. e.g network issues, etc.

``masterFQDN``
    (optional, defaults to socket.getfqdn())
    Address of the master the worker should connect to. Use if you master machine does not have proper fqdn.
    This value is passed to the docker image via environment variable ``BUILDMASTER``

``hostconfig``
    (renderable dictionary, optional)
    Extra host configuration parameters passed as a dictionary used to create HostConfig object.
    See `docker-py's HostConfig documentation <https://docker-py.readthedocs.io/en/stable/api.html#docker.api.container.ContainerApiMixin.create_host_config>`_ for all the supported options.

``autopull``
    (optional, defaults to false)
    Automatically pulls image if requested image is not on docker host.

``alwaysPull``
    (optional, defaults to false)
    Always pulls (update) image if autopull is set to true.
    Also affects the base image specified by `FROM ....` if using a dockerfile, autopull is not needed then.

``target``
    (renderable string, optional)
    Sets target build stage for multi-stage builds when using a dockerfile.

``custom_context``
    (renderable boolean, optional)
	Boolean indicating that the user wants to use custom build arguments for the docker environment. Defaults to False.

``encoding``
    (renderable string, optional)
	String indicating the compression format for the build context. defaults to 'gzip', but 'bzip' can be used as well.

``buildargs``
    (renderable dictionary, optional if ``custom_context`` is True)
	Dictionary, passes information for the docker to build its environment. Eg. {'DISTRO':'ubuntu', 'RELEASE':'11.11'}. Defaults to None.

``hostname``
    (renderable string, optional)
    This will set container's hostname.

Marathon latent worker
======================

Marathon_ Marathon is a production-grade container orchestration platform for Mesosphere's Data-center Operating System (DC/OS) and Apache ``Mesos``.

Buildbot supports using Marathon_ to host your latent workers.
It requires either `txrequests`_ or `treq`_ to be installed to allow interaction with http server.
See :class:`HTTPClientService` for details.

.. py:class:: buildbot.worker.marathon.MarathonLatentWorker
.. py:class:: buildbot.plugins.worker.MarathonLatentWorker

The :class:`MarathonLatentWorker` attempts to instantiate a fresh image for each build to assure consistency of the environment between builds.
Each image will be discarded once the worker finished processing the build queue (i.e. becomes ``idle``).
See :ref:`build_wait_timeout <Common-Latent-Workers-Options>` to change this behavior.

In addition to the arguments available for any :ref:`Latent-Workers`, :class:`MarathonLatentWorker` will accept the following extra ones:

``marathon_url``
    (mandatory)
    This is the URL to Marathon_ server.
    Its REST API will be used to start docker containers.

``marathon_auth``
    (optional)
    This is the optional ``('userid', 'password')`` ``BasicAuth`` credential.
    If txrequests_ is installed, this can be a `requests authentication plugin`_.

``image``
    (mandatory)
    This is the name of the image that will be started by the build master. It should start a worker.
    This option can be a renderable, like :ref:`Interpolate`, so that it generates from the build request properties.
    Images are by pulled from the default docker registry.
    MarathonLatentWorker does not support starting a worker built from a Dockerfile.

``masterFQDN``
    (optional, defaults to socket.getfqdn())
    Address of the master the worker should connect to. Use if you master machine does not have proper fqdn.
    This value is passed to the docker image via environment variable ``BUILDMASTER``

    If the value contains a colon (``:``), then BUILDMASTER and BUILDMASTER_PORT environment variables will be passed, following scheme: ``masterFQDN="$BUILDMASTER:$BUILDMASTER_PORT"``

``marathon_extra_config``
    (optional, defaults to ``{}```)
    Extra configuration to be passed to `Marathon API`_.
    This implementation will setup the minimal configuration to run a worker (docker image, ``BRIDGED`` network)
    It will let the default for everything else, including memory size, volume mounting, etc.
    This configuration is voluntarily very raw so that it is easy to use new marathon features.
    This dictionary will be merged into the Buildbot generated config, and recursively override it.
    See `Marathon API`_ documentation to learn what to include in this config.

.. _Marathon: https://mesosphere.github.io/marathon/
.. _Marathon API: http://mesosphere.github.io/marathon/docs/rest-api.html#post-v2-apps
.. _txrequests: https://pypi.python.org/pypi/txrequests
.. _treq: https://pypi.python.org/pypi/treq
.. _requests authentication plugin: https://2.python-requests.org/en/master/user/authentication/

Kubernetes latent worker
========================

Kubernetes_ is an open-source system for automating deployment, scaling, and management of containerized applications.

Buildbot supports using Kubernetes_ to host your latent workers.

.. py:class:: buildbot.worker.kubernetes.KubeLatentWorker
.. py:class:: buildbot.plugins.worker.KubeLatentWorker

The :class:`KubeLatentWorker` attempts to instantiate a fresh container for each build to assure consistency of the environment between builds
Each container will be discarded once the worker finished processing the build queue (i.e. becomes ``idle``).
See :ref:`build_wait_timeout <Common-Latent-Workers-Options>` to change this behavior.

.. _Kubernetes: https://kubernetes.io/

In addition to the arguments available for any :ref:`Latent-Workers`, :class:`KubeLatentWorker` will accept the following extra ones:

``image``
    (optional, default to ``buildbot/buildbot-worker``)
    Docker image. Default to the `official buildbot image`.

``namespace``
    (optional)
    This is the name of the namespace. Default to the current namespace

``kube_config``
    (mandatory)
    This is the object specifying how to connect to the kubernetes cluster.
    This object must be an instance of abstract class :class:`KubeConfigLoaderBase`, which have 3 implementations:

    - :class:`KubeHardcodedConfig`

    - :class:`KubeCtlProxyConfigLoader`

    - :class:`KubeInClusterConfigLoader`

``masterFQDN``
    (optional, default to ``None``)
    Address of the master the worker should connect to. Put the service master service name if you want to place a load-balancer between the workers and the masters.
    The default behaviour is to compute address IP of the master. This option works out-of-the box inside kubernetes but don't leverage the load-balancing through service.
    You can pass any callable, such as ``KubeLatentWorker.get_fqdn`` that will set ``masterFQDN=socket.getfqdn()``.

For more customization, you can subclass :class:`KubeLatentWorker` and override following methods.
All those methods can optionally return a deferred.
All those methods take props object which is a L{IProperties} allowing to get some parameters from the build properties

    .. py:method:: createEnvironment(self, props)

        This method compute the environment from your properties.
        Don't forget to first call `super().createEnvironment(props)` to get the base properties necessary to connect to the master.

    .. py:method:: getBuildContainerResources(self, props)

        This method compute the `pod resources` part of the container spec (`spec.containers[].resources`.
        This is important to reserve some CPU and memory for your builds, and to trigger node auto-scaling if needed.
        You can also limit the CPU and memory for your container.

    .. py:method:: getServicesContainers(self, props)

        This method compute a list of containers spec to put alongside the worker container.
        This is useful for starting services around your build pod, like a database container.
        All containers within the same pod share the same localhost interface, so you can access the other containers TCP ports very easily.


.. _official buildbot image: https://hub.docker.com/r/buildbot/buildbot-worker/
.. _pod resources: https://kubernetes.io/docs/concepts/configuration/manage-compute-resources-container/#resource-requests-and-limits-of-pod-and-container

Kubernetes config loaders
-------------------------

Kubernetes provides many options to connect to a cluster.
It is especially more complicated as some cloud providers use specific methods to connect to their managed kubernetes.
Config loaders objects can be shared between LatentWorker.

There are three options you may use to connect to your clusters.

When running both the master and slaves run on the same Kubernetes cluster, you should use the KubeInClusterConfigLoader.
If not, but having a configured ``kubectl`` tool available to the build master is an option for you, you should use KubeCtlProxyConfigLoader.
If neither of these options is convenient, use KubeHardcodedConfig.

.. py:class:: buildbot.util.kubeclientservice.KubeCtlProxyConfigLoader
.. py:class:: buildbot.plugins.util.KubeCtlProxyConfigLoader

``KubeCtlProxyConfigLoader``
............................

With :class:`KubeCtlProxyConfigLoader`, buildbot will user ``kubectl proxy`` to get access to the cluster.
This delegates the authentication to the ``kubectl`` ``golang`` binary, and thus avoid to implement a python version for every authentication scheme that kubernetes provides.
``kubectl`` must be available in the ``PATH``, and configured to be able to start pods.
While this method is very convenient and easy, it also opens an unauthenticated http access to your cluster via localhost.
You must ensure that this is properly secured, and your buildbot master machine is not on a shared multi-user server.

``proxy_port``
    (optional defaults to 8001)
    HTTP port to use.

``namespace``
    (optional defaults to ``"default"``
    default namespace to use if the latent worker do not provide one already.


.. py:class:: buildbot.util.kubeclientservice.KubeHardcodedConfig
.. py:class:: buildbot.plugins.util.KubeHardcodedConfig

``KubeHardcodedConfig``
.......................


With :class:`KubeHardcodedConfig`, you just configure the necessary parameters to connect to the clusters.

``master_url``
    (mandatory)
    The http url of you kubernetes master.
    Only http and https protocols are supported

``headers``
    (optional)
    Additional headers to be passed to the HTTP request

``basicAuth``
    (optional)
    Basic authorization info to connect to the cluster, as a `{'user': 'username', 'password': 'psw' }` dict.

    Unlike the headers argument, this argument supports secret providers, e.g:

    .. code-block:: python

        basicAuth={'user': 'username', 'password': Secret('k8spassword')}

``bearerToken``
    (optional)

    A bearer token to authenticate to the cluster, as a string.
    Unlike the headers argument, this argument supports secret providers, e.g:

    .. code-block:: python

        bearerToken=Secret('k8s-token')

    When using the Google Kubernetes Engine (GKE), a bearer token for the default service account can be had with:

    .. code-block:: bash

        gcloud container clusters get-credentials --region [YOURREGION] YOURCLUSTER
        kubectl describe sa
        kubectl describe secret [SECRET_ID]

    Where SECRET_ID is displayed by the ``describe sa`` command line.
    The default service account does not have rights on the cluster (to create/delete pods), which is required by BuildBot's integration.
    You may give it this right by making it a cluster admin with

    .. code-block:: bash

        kubectl create clusterrolebinding service-account-admin \
            --clusterrole=cluster-admin \
            --serviceaccount default:default

``cert``
    (optional)
    Client certificate and key to use to authenticate.
    This only works if ``txrequests`` is installed:

    .. code-block:: python

        cert=('/path/to/certificate.crt', '/path/to/certificate.key')

``verify``
    (optional)
    Path to server certificate authenticate the server:

    .. code-block:: python

        verify='/path/to/kube_server_certificate.crt'

    When using the Google Kubernetes Engine (GKE), this certificate is available from the admin console, on the Cluster page.
    Verify that it is valid (i.e. no copy/paste errors) with ``openssl verify PATH_TO_PEM``.

``namespace``
    (optional defaults to ``"default"``
    default namespace to use if the latent worker do not provide one already.


.. py:class:: buildbot.util.kubeclientservice.KubeInClusterConfigLoader
.. py:class:: buildbot.plugins.util.KubeInClusterConfigLoader

``KubeInClusterConfigLoader``
.............................

Use :class:`KubeInClusterConfigLoader`, if your Buildbot master is itself located within the kubernetes cluster.
In this case, you would associated a service account to the Buildbot master pod, and :class:`KubeInClusterConfigLoader` will get the credentials from that.

This config loader takes no arguments.
