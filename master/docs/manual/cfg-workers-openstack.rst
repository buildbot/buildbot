.. -*- rst -*-

OpenStack
=========

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
    The flavor ID to use for the instance.

``image``
    A string containing the image UUID to use for the instance.
    A callable may instead be passed.
    It will be passed the list of available images and must return the image to use.

``os_username``

``os_password``

``os_tenant_name``

``os_auth_url``
    The OpenStack authentication needed to create and delete instances.
    These are the same as the environment variables with uppercase names of the arguments.

``block_devices``
    A list of dictionaries.
    Each dictionary specifies a block device to set up during instance creation.

    Supported keys

    ``uuid``
        (required):
        The image, snapshot, or volume UUID.
    ``volume_size``
        (required):
        Size of the block device in GiB.
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
    Buildbot uses the OpenStack Nova version 1.1 API by default (see client_version).

``client_version``
    (optional)
    Nova client version to use. Defaults to 1.1 (deprecated). Use 2 or 2.minor for
    version 2 API.

Here is the simplest example of configuring an OpenStack latent worker.

::

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

::

    from buildbot.plugins import worker

    def find_image(images):
        # Sort oldest to newest.
        cmp_fn = lambda x,y: cmp(x.created, y.created)
        candidate_images = sorted(images, cmp=cmp_fn)
        # Return the oldest candiate image.
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

::

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


:class:`OpenStackLatentWorker` supports all other configuration from the standard :class:`Worker`.
The ``missing_timeout`` and ``notify_on_missing`` specify how long to wait for an OpenStack instance to attach before considering the attempt to have failed and email addresses to alert, respectively.
``missing_timeout`` defaults to 20 minutes.
