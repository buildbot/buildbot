.. -*- rst -*-

.. index::
   Upcloud
   Workers; Upcloud

.. bb:worker:: UpcloudLatentWorker

UpCloud
=======

.. @cindex UpcloudLatentWorker
.. py:class:: buildbot.worker.upcloud.UpcloudLatentWorker

`UpCloud <https://www.upcloud.com/>`_ is a web service that allows you to start virtual machines in cloud.
Please see their website for details, including costs.

This document will guide you through setup of a UpCloud latent worker:

.. contents::
   :depth: 1
   :local:

Get an UpCloud Account
----------------------

To start off, to use the UpCloud latent worker, you need to sign up on UpCloud.

1. Go to https://www.upcloud.com/ and create an account.

2. Once you are logged into your account, create a sub-account for buildbot to use.
   You need to tick the box enabling it for API usage.
   You should disable the box enabling web interface.
   You should not use your primary account for safety and security reasons.

Configure the Master with an :class:`~buildbot.worker.upcloud.UpcloudLatentWorker`
----------------------------------------------------------------------------------

Quick-start sample

.. code-block:: python

   from buildbot.plugins import worker
   c['workers'].append(upcloud.UpcloudLatentWorker('upcloud-worker','pass',
       image='Debian GNU/Linux 9.3 (Stretch)',
       api_username="username",
       api_password="password",
       hostconfig = {
           "user_data":"""
   /usr/bin/apt-get update
   /usr/bin/apt-get install -y buildbot-slave
   /usr/bin/buildslave create-slave --umask=022 /buildslave buildbot.example.com upcloud-01 slavepass
   /usr/bin/buildslave start /buildslave
   """}))

Complete example with default values

.. code-block:: python

   from buildbot.plugins import worker
   c['workers'].append(upcloud.UpcloudLatentWorker('upcloud-worker','pass',
       image='Debian GNU/Linux 9.3 (Stretch)',
       api_username="username",
       api_password="password",
       hostconfig = {
           "zone":"de-fra1",
           "plan":"1xCPU-1GB",
           "hostname":"hostname",
           "ssh_keys":["ssh-rsa ...."],
           "os_disk_size":10,
           "core_number":1,
           "memory_amount":512,
           "user_data":""
       }))


The ``image`` argument specifies the name of image in the image library.
UUID is not currently supported.

The ``api_username`` and ``api_password`` are for the sub-account you created on UpCloud.

``hostconfig`` can be used to set various aspects about the created host.
 - ``zone`` is a valid execution zone in UpCloud environment, check their `API documentation <https://developers.upcloud.com/>` for valid values.
 - ``plan`` is a valid pre-configured machine specification, or custom if you want to define your own.
   See their API documentation for valid values
 - ``user_data`` field is used to specify startup script to run on the host.
 - ``hostname`` specifies the hostname for the worker.
   Defaults to name of the worker.
 - ``ssh_keys`` specifies ssh key(s) to add for root account.
   Some images support only one SSH key.
   At the time of writing, only RSA keys are supported.
 - ``os_disk_size`` specifies size of the system disk.
 - ``core_number`` can be used to specify number of cores, when plan is custom.
 - ``memory_amount`` can be used to specify memory in megabytes, when plan is custom.
 - ``user_data`` can be used to specify either URL to script, or script to execute when machine is started.

Note that by default buildbot retains latent workers for 10 minutes, see ``build_wait_time`` on how to change this.
