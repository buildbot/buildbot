.. -*- rst -*-

.. index::
   libvirt
   Workers; libvirt

Libvirt
=======

`libvirt <http://www.libvirt.org/>`_ is a virtualization API for interacting with the virtualization capabilities of recent versions of Linux and other OSes.
It is LGPL and comes with a stable C API, and Python bindings.

This means we know have an API which when tied to buildbot allows us to have workers that run under Xen, QEMU, KVM, LXC, OpenVZ, User Mode Linux, VirtualBox and VMWare.

The libvirt code in Buildbot was developed against libvirt 0.7.5 on Ubuntu Lucid.
It is used with KVM to test Python code on Karmic VM's, but obviously isn't limited to that.
Each build is run on a new VM, images are temporary and thrown away after each build.

This document will guide you through setup of a libvirt latent worker:

.. contents::
   :depth: 1
   :local:

Setting up libvirt
------------------

We won't show you how to set up libvirt as it is quite different on each platform, but there are a few things you should keep in mind.

* If you are running on Ubuntu, your master should run Lucid.
  Libvirt and apparmor are buggy on Karmic.
* If you are using the system libvirt, your buildbot master user will need to be in the libvirtd group.
* If you are using KVM, your buildbot master user will need to be in the KVM group.
* You need to think carefully about your virtual network *first*.
  Will NAT be enough?
  What IP will my VM's need to connect to for connecting to the master?

Configuring your base image
---------------------------

You need to create a base image for your builds that has everything needed to build your software.
You need to configure the base image with a buildbot worker that is configured to connect to the master on boot.

Because this image may need updating a lot, we strongly suggest scripting its creation.

If you want to have multiple workers using the same base image it can be annoying to duplicate the image just to change the buildbot credentials.
One option is to use libvirt's DHCP server to allocate an identity to the worker: DHCP sets a hostname, and the worker takes its identity from that.

Doing all this is really beyond the scope of the manual, but there is a :file:`vmbuilder` script and a :file:`network.xml` file to create such a DHCP server in :file:`contrib/` (:ref:`Contrib-Scripts`) that should get you started:

.. code-block:: bash

    sudo apt-get install ubuntu-vm-builder
    sudo contrib/libvirt/vmbuilder

Should create an :file:`ubuntu/` folder with a suitable image in it.

.. code-block:: none

    virsh net-define contrib/libvirt/network.xml
    virsh net-start buildbot-network

Should set up a KVM compatible libvirt network for your buildbot VM's to run on.

Configuring your Master
-----------------------

If you want to add a simple on demand VM to your setup, you only need the following.
We set the username to ``minion1``, the password to ``sekrit``.
The base image is called ``base_image`` and a copy of it will be made for the duration of the VM's life.
That copy will be thrown away every time a build is complete.

::

    from buildbot.plugins import worker, util
    c['workers'] = [
        worker.LibVirtWorker('minion1', 'sekrit',
                             util.Connection("qemu:///session"),
                             '/home/buildbot/images/minion1',
                             '/home/buildbot/images/base_image')
    ]

You can use virt-manager to define ``minion1`` with the correct hardware.
If you don't, buildbot won't be able to find a VM to start.

:class:`LibVirtWorker` accepts the following arguments:

``name``
    Both a buildbot username and the name of the virtual machine.

``password``
    A password for the buildbot to login to the master with.

``connection``
    :class:`Connection` instance wrapping connection to libvirt.

``hd_image``
    The path to a libvirt disk image, normally in qcow2 format when using KVM.

``base_image``
    If given a base image, buildbot will clone it every time it starts a VM.
    This means you always have a clean environment to do your build in.

``xml``
    If a VM isn't predefined in virt-manager, then you can instead provide XML like that used with ``virsh define``.
    The VM will be created automatically when needed, and destroyed when not needed any longer.
