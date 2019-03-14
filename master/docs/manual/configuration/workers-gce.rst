.. -*- rst -*-

.. index::
   GCE
   Workers; GCE

.. bb:worker:: GCELatentWorker

Google Compute Engine (GCE)
=====================================================

.. @cindex GCELatentWorker
.. py:class:: buildbot.worker.gce.GCELatentWorker

`GCE <https://cloud.google.com/compute/>`_ is a web service that allows you
to start virtual machines in a Google data center. Please see their website
for details, including costs.

Using a GCE latent worker involves setting up a boot disk image and a GCE
node. The worker will reset the node's disk using the "base" image and boot
the virtual machine one time for each

Compared to the Kubernetes latent worker, this allows you to use things
that are currently not available on Kubernetes (e.g. OpenGL)

This document will guide you through setup of a GCE latent worker. It assumes
that you already have a Google Cloud account.

.. contents::
   :depth: 1
   :local:

Create the worker VM
--------------------
You first need to create yourself a VM instance. In the console, this is
done through Compute Engine/VM Instances. This instance will be the worker
VM. Buildbot will never delete it.

By default, however, Buildbot *will* delete the instance's boot disk and
replace it with a "fresh" disk from a template you specify.

The worker is expected to connect to the buildbot master on boot. Buildbot
will restart the VM instance, either on stop (usually), or on start if
stopping it on stop failed - or during VM setup (see next section).

The buildbot master URL and port, as well as the worker name and passwords,
are available as instance metadata through the BUILDMASTER, BUILDMASTER_PORT,
WORKERNAME and WORKERPASS metadata. Metadata is available from the VM
instance through the http://metadata.google.internal/computeMetadata/v1/
endpoint. For instance:

.. code-block:: bash

    function metadata_get() {
        curl -f "http://metadata.google.internal/computeMetadata/v1/$1" \
            -H "Metadata-Flavor: Google" \
            2> /dev/null
    }
    metadata_get instance/attributes/WORKERNAME

The project ID is also available through the same method:

.. code-block:: bash

    metadata_get project/project-id

One can pass these as environment variables to e.g. the `buildbot.tac` script
that exists for the docker workers.

Creating the VM's boot disk template
------------------------------------
The best way to create the VM boot disk template is to set the worker's
`resetDisk` and `stopInstanceOnStop` flags to False. This instructs buildbot to
not stop the instance when the worker is instructed to stop, and to not
destroy the boot disk at all. Both these things allow you to debug the VM
provisioning after a (failed) build - since the VM is still running - and to
incrementally build the boot disk template - since it does not get destroyed.

In this mode, Buildbot will instead reboot the VM on start, so you don't have
to do anything to try a new build.

Once you are confident that your VM image is as you wish, you can create
a disk image from it. Go to Compute Engine > Images and click "Create Image".
In the form, choose "Disk" as source and pick the VM's disk name in the
"Source disk" dropdown.

Worker Configuration
--------------------

.. code-block:: python

    from buildbot.plugins import worker
    c['workers'] = [
        worker.GCELatentWorker(
            'my-worker',
            project='GCE-PROJECT-ID',
            zone='GCE-VM-ZONE',
            instance='GCE-VM-NAME',
            image='GCE-DISK-IMAGE',
            masterFQDN='host-to-buildbot-master',
            sa_credentials="")
    ]

The `sa_credentials` are the client email and private key to a service account
able to (re)boot the VM, detach, delete, attach and create disks. It can
be provided as a secret, in which case a JSON-encoded string is the best.

