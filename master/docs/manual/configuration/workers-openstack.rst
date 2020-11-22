.. -*- rst -*-

.. bb:worker:: OpenStackLatentWorker

OpenStack
=========

.. @cindex OpenStackLatentWorker
.. py:class:: buildbot.worker.openstack.OpenStackLatentWorker

`OpenStack <http://openstack.org/>`_ is a series of interconnected components that facilitates managing compute, storage, and network resources in a data center.
It is available under the Apache License and has a REST interface along with a Python client.

This document will guide you through setup of an OpenStack latent worker:

.. contents::
   :depth: 1
   :local:

Install dependencies
--------------------

OpenStackLatentWorker requires python-novaclient to work, you can install it with pip install python-novaclient.

Get an Account in an OpenStack cloud
------------------------------------

Setting up OpenStack is outside the domain of this document.
There are four account details necessary for the Buildbot master to interact with your OpenStack cloud: username, password, a tenant name, and the auth URL to use.

Create an Image
---------------

OpenStack supports a large number of image formats.
OpenStack maintains a short list of prebuilt images; if the desired image is not listed, The `OpenStack Compute Administration Manual <http://docs.openstack.org/trunk/openstack-compute/admin/content/index.html>`_ is a good resource for creating new images.
You need to configure the image with a buildbot worker to connect to the master on boot.

Configure the Master with an OpenStackLatentWorker
--------------------------------------------------

With the configured image in hand, it is time to configure the buildbot master to create OpenStack instances of it.
You will need the aforementioned account details.
These are the same details set in either environment variables or passed as options to an OpenStack client.

:class:`OpenStackLatentWorker` accepts the following arguments:

``name``
    The worker name.

``password``
    A password for the worker to login to the master with.

``flavor``
    A string containing the flavor name or UUID to use for the instance.

``image``
    A string containing the image name or UUID to use for the instance.

``os_username``

``os_password``

``os_tenant_name``

``os_user_domain``

``os_project_domain``

``os_auth_url``
    The OpenStack authentication needed to create and delete instances.
    These are the same as the environment variables with uppercase names of the arguments.

``os_auth_args``
    Arguments passed directly to keystone.
    If this is specified, other authentication parameters (see above) are ignored.
    You can use ``auth_type`` to specify auth plugin to load.
    See `OpenStack documentation <https://docs.openstack.org/python-keystoneclient/>` for more information.
    Usually this should contain ``auth_url``, ``username``, ``password``, ``project_domain_name``
    and ``user_domain_name``.

``block_devices``
    A list of dictionaries.
    Each dictionary specifies a block device to set up during instance creation.
    The values support using properties from the build and will be rendered when the instance is started.

    Supported keys

    ``uuid``
        (required):
        The image, snapshot, or volume UUID.
    ``volume_size``
        (optional):
        Size of the block device in GiB.
        If not specified, the minimum size in GiB to contain the source will be calculated and used.
    ``device_name``
        (optional): defaults to ``vda``.
        The name of the device in the instance; e.g. vda or xda.
    ``source_type``
        (optional): defaults to ``image``.
        The origin of the block device.
        Valid values are ``image``, ``snapshot``, or ``volume``.
    ``destination_type``
        (optional): defaults to ``volume``.
        Destination of block device: ``volume`` or ``local``.
    ``delete_on_termination``
        (optional): defaults to ``True``.
        Controls if the block device will be deleted when the instance terminates.
    ``boot_index``
        (optional): defaults to ``0``.
        Integer used for boot order.

``meta``
    A dictionary of string key-value pairs to pass to the instance.
    These will be available under the ``metadata`` key from the metadata service.

``nova_args``
    (optional)
    A dict that will be appended to the arguments when creating a VM.
    Buildbot uses the OpenStack Nova version 2 API by default (see client_version).

``client_version``
    (optional)
    A string containing the Nova client version to use.
    Defaults to ``2``.
    Supports using ``2.X``, where X is a micro-version.
    Use ``1.1`` for the previous, deprecated, version.
    If using ``1.1``, note that an older version of novaclient will be needed so it won't switch to using ``2``.

``region``
    (optional)
    A string specifying region where to instantiate the worker.

Here is the simplest example of configuring an OpenStack latent worker.

.. code-block:: python

    from buildbot.plugins import worker
    c['workers'] = [
        worker.OpenStackLatentWorker('bot2', 'sekrit',
                    flavor=1, image='8ac9d4a4-5e03-48b0-acde-77a0345a9ab1',
                    os_username='user', os_password='password',
                    os_tenant_name='tenant',
                    os_auth_url='http://127.0.0.1:35357/v2.0')
    ]

The ``image`` argument also supports being given a callable.
The callable will be passed the list of available images and must return the image to use.
The invocation happens in a separate thread to prevent blocking the build master when interacting with OpenStack.

.. code-block:: python

    from buildbot.plugins import worker

    def find_image(images):
        # Sort oldest to newest.
        def key_fn(x):
            return x.created

        candidate_images = sorted(images, key=key_fn)
        # Return the oldest candidate image.
        return candidate_images[0]

    c['workers'] = [
        worker.OpenStackLatentWorker('bot2', 'sekrit',
                    flavor=1, image=find_image,
                    os_username='user', os_password='password',
                    os_tenant_name='tenant',
                    os_auth_url='http://127.0.0.1:35357/v2.0')
    ]


The ``block_devices`` argument is minimally manipulated to provide some defaults and passed directly to novaclient.
The simplest example is an image that is converted to a volume and the instance boots from that volume.
When the instance is destroyed, the volume will be terminated as well.

.. code-block:: python

    from buildbot.plugins import worker
    c['workers'] = [
        worker.OpenStackLatentWorker('bot2', 'sekrit',
                    flavor=1, image='8ac9d4a4-5e03-48b0-acde-77a0345a9ab1',
                    os_username='user', os_password='password',
                    os_tenant_name='tenant',
                    os_auth_url='http://127.0.0.1:35357/v2.0',
                    block_devices=[
                        {'uuid': '3f0b8868-67e7-4a5b-b685-2824709bd486',
                        'volume_size': 10}])
    ]


The ``nova_args`` can be used to specify additional arguments for the novaclient.
For example network mappings, which is required if your OpenStack tenancy has more than one network, and default cannot be determined.
Please refer to your OpenStack manual whether it wants net-id or net-name.

Other useful parameters are ``availability_zone``, ``security_groups`` and ``config_drive``.
Refer to `Python bindings to the OpenStack Nova API <http://docs.openstack.org/developer/python-novaclient/>`_ for more information.
It is found on section Servers, method create.

.. code-block:: python

    from buildbot.plugins import worker
    c['workers'] = [
        worker.OpenStackLatentWorker('bot2', 'sekrit',
                    flavor=1, image='8ac9d4a4-5e03-48b0-acde-77a0345a9ab1',
                    os_username='user', os_password='password',
                    os_tenant_name='tenant',
                    os_auth_url='http://127.0.0.1:35357/v2.0',
                    nova_args={
                      'nics': [
                                {'net-id':'uid-of-network'}
                              ]})
    ]

:class:`OpenStackLatentWorker` supports all other configuration from the standard :class:`Worker`.
The ``missing_timeout`` and ``notify_on_missing`` specify how long to wait for an OpenStack instance to attach before considering the attempt to have failed and email addresses to alert, respectively.
``missing_timeout`` defaults to 20 minutes.
