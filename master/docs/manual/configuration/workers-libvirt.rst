.. -*- rst -*-

.. index::
   libvirt
   Workers; libvirt

.. bb:worker:: LibVirtWorker

Libvirt
=======

.. @cindex LibVirtWorker
.. py:class:: buildbot.worker.libvirt.LibVirtWorker

`libvirt <http://www.libvirt.org/>`_ is a virtualization API for interacting with the virtualization capabilities of recent versions of Linux and other OSes.
It is LGPL and comes with a stable C API, and Python bindings.

This means we now have an API which when tied to buildbot allows us to have workers that run under Xen, QEMU, KVM, LXC, OpenVZ, User Mode Linux, VirtualBox and VMWare.

The libvirt code in Buildbot was developed against libvirt 0.7.5 on Ubuntu Lucid.
It is used with KVM to test Python code on VMs, but obviously isn't limited to that.
Each build is run on a new VM, images are temporary and thrown away after each build.

This document will guide you through setup of a libvirt latent worker:

.. contents::
   :depth: 1
   :local:

Setting up libvirt
------------------

We won't show you how to set up libvirt as it is quite different on each platform, but there are a few things you should keep in mind.

* If you are using the system libvirt (libvirt and buildbot master are on same server), your buildbot master user will need to be in the libvirtd group.
* If libvirt and buildbot master are on different servers, the user connecting to libvirt over ssh will need to be in the libvirtd group. Also need to setup authorization via ssh-keys (without password prompt).   
* If you are using KVM, your buildbot master user will need to be in the KVM group.
* You need to think carefully about your virtual network *first*.
  Will NAT be enough?
  What IP will my VMs need to connect to for connecting to the master?

Configuring your base image
---------------------------

You need to create a base image for your builds that has everything needed to build your software.
You need to configure the base image with a buildbot worker that is configured to connect to the master on boot.

Because this image may need updating a lot, we strongly suggest scripting its creation.

If you want to have multiple workers using the same base image it can be annoying to duplicate the image just to change the buildbot credentials.
One option is to use libvirt's DHCP server to allocate an identity to the worker: DHCP sets a hostname, and the worker takes its identity from that.

Doing all this is really beyond the scope of the manual, but there is a :contrib-src:`vmbuilder <master/contrib/libvirt/vmbuilder>` script and a :contrib-src:`network.xml <master/contrib/libvirt/network.xml>` file to create such a DHCP server in :contrib-src:`master/contrib/` (:ref:`Contrib-Scripts`) that should get you started:

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

.. code-block:: python

    from buildbot.plugins import worker, util
    c['workers'] = [
        worker.LibVirtWorker('minion1', 'sekrit',
                             uri="qemu:///session",
                             hd_image='/home/buildbot/images/minion1',
                             base_image='/home/buildbot/images/base_image')
    ]

You can use virt-manager to define ``minion1`` with the correct hardware.
If you don't, buildbot won't be able to find a VM to start.

:class:`LibVirtWorker` accepts the following arguments:

``name``
    Both a buildbot username and the name of the virtual machine.

``password``
    A password for the buildbot to login to the master with.

``connection``
    :class:`Connection` instance wrapping connection to libvirt. (deprecated, use ``uri``).

``hd_image``
    The path to a libvirt disk image, normally in qcow2 format when using KVM.

``base_image``
    If given a base image, buildbot will clone it every time it starts a VM.
    This means you always have a clean environment to do your build in.

``uri``
    The URI of the connection to libvirt.

``masterFQDN``
    (optional, defaults to ``socket.getfqdn()``)
    Address of the master the worker should connect to.
    Use if you master machine does not have proper fqdn.
    This value is passed to the libvirt image via domain metadata.

``xml``
    If a VM isn't predefined in virt-manager, then you can instead provide XML like that used with ``virsh define``.
    The VM will be created automatically when needed, and destroyed when not needed any longer.
    
.. note:: The ``hd_image`` and ``base_image`` must be on same machine with buildbot master.

Connection to master
--------------------

If ``xml`` configuration key is not provided, then Buildbot will set libvirt metadata for the domain.
It will contain the following XML element: ``<auth username="..." password="..." master="..."/>``.
Here ``username``, ``password`` and ``master`` are the name of the worker, password to use for connection and the FQDN of the master.
The libvirt metadata will be placed in the XML namespace ``buildbot=http://buildbot.net/``.

Configuring Master to use libvirt on remote server
---------------------------------------------------

If you want to use libvirt on remote server configure remote libvirt server and buildbot server following way.

1. Define user to connect to remote machine using ssh. Configure connection of such user to remote libvirt server (see https://wiki.libvirt.org/page/SSHSetup) without password prompt.
2. Add user to libvirtd group on remote libvirt server ``sudo usermod -G libvirtd -a <user>``.

Configure remote libvirt server:

1. Create virtual machine for buildbot and configure it. 
2. Change virtual machine image file to new name, which will be used as temporary image and deleted after virtual machine stops. Execute command ``sudo virsh edit <VM name>``. In xml file locate ``devices/disk/source`` and change file path to new name. The file must not be exists, it will create via hook script.
3. Add hook script to ``/etc/libvirt/hooks/qemu`` to recreate VM image each start:

.. code-block:: python

   #!/usr/bin/python

   # Script /etc/libvirt/hooks/qemu
   # Don't forget to execute service libvirt-bin restart
   # Also see https://www.libvirt.org/hooks.html

   # This script make clean VM for each start using base image

   import os
   import subprocess
   import sys

   images_path = '/var/lib/libvirt/images/'
   
   # build-vm - VM name in virsh list --all
   # vm_base_image.qcow2 - base image file name, must exist in path /var/lib/libvirt/images/
   # vm_temp_image.qcow2 - temporary image. Must not exist in path /var/lib/libvirt/images/, but
   # defined in VM config file
   domains = {
       'build-vm' : ['vm_base_image.qcow2', 'vm_temp_image.qcow2'],
   }

   def delete_image_clone(vir_domain):
       if vir_domain in domains:
           domain = domains[vir_domain]
           os.remove(images_path + domain[1])

   def create_image_clone(vir_domain):
       if vir_domain in domains:
           domain = domains[vir_domain]
           cmd = ['/usr/bin/qemu-img', 'create', '-b', images_path + domain[0],
                  '-f', 'qcow2', images_path + domain[1]]
           subprocess.call(cmd)

   if __name__ == "__main__":
       vir_domain, action = sys.argv[1:3]

       if action in ["prepare"]:
           create_image_clone(vir_domain)

       if action in ["release"]:
           delete_image_clone(vir_domain)

Configure buildbot server:

1. On buildbot server in virtual environment install libvirt-python package: ``pip install libvirt-python``
2. Create worker using remote ssh connection.

.. code-block:: python

    from buildbot.plugins import worker, util
    c['workers'] = [
        worker.LibVirtWorker(
            'minion1', 'sekrit',
            util.Connection("qemu+ssh://<user>@<ip address or DNS name>:<port>/session"),
            '/home/buildbot/images/minion1')
    ]

