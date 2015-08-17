.. -*- rst -*-
.. _Buildslaves:

.. bb:cfg:: slaves

Buildslaves
-----------

The :bb:cfg:`slaves` configuration key specifies a list of known buildslaves.
In the common case, each buildslave is defined by an instance of the :class:`BuildSlave` class.
It represents a standard, manually started machine that will try to connect to the buildbot master as a slave.
Buildbot also supports "on-demand", or latent, buildslaves, which allow buildbot to dynamically start and stop buildslave instances.

.. contents::
    :depth: 1
    :local:

Defining Buildslaves
~~~~~~~~~~~~~~~~~~~~

A :class:`BuildSlave` instance is created with a ``slavename`` and a ``slavepassword``.
These are the same two values that need to be provided to the buildslave administrator when they create the buildslave.

The slavename must be unique, of course.
The password exists to prevent evildoers from interfering with the buildbot by inserting their own (broken) buildslaves into the system and thus displacing the real ones.

Buildslaves with an unrecognized slavename or a non-matching password will be rejected when they attempt to connect, and a message describing the problem will be written to the log file (see :ref:`Logfiles`).

A configuration for two slaves would look like::

    from buildbot.plugins import buildslave
    c['slaves'] = [
        buildslave.BuildSlave('bot-solaris', 'solarispasswd'),
        buildslave.BuildSlave('bot-bsd', 'bsdpasswd'),
    ]

BuildSlave Options
~~~~~~~~~~~~~~~~~~

.. index:: Properties; from buildslave

:class:`BuildSlave` objects can also be created with an optional ``properties`` argument, a dictionary specifying properties that will be available to any builds performed on this slave.
For example::

    c['slaves'] = [
        buildslave.BuildSlave('bot-solaris', 'solarispasswd',
                              properties={ 'os':'solaris' }),
    ]

.. index:: Build Slaves; limiting concurrency

The :class:`BuildSlave` constructor can also take an optional ``max_builds`` parameter to limit the number of builds that it will execute simultaneously::

    c['slaves'] = [
        buildslave.BuildSlave("bot-linux", "linuxpassword", max_builds=2)
    ]

Master-Slave TCP Keepalive
++++++++++++++++++++++++++

By default, the buildmaster sends a simple, non-blocking message to each slave every hour.
These keepalives ensure that traffic is flowing over the underlying TCP connection, allowing the system's network stack to detect any problems before a build is started.

The interval can be modified by specifying the interval in seconds using the ``keepalive_interval`` parameter of BuildSlave::

    c['slaves'] = [
        buildslave.BuildSlave('bot-linux', 'linuxpasswd',
                              keepalive_interval=3600)
    ]

The interval can be set to ``None`` to disable this functionality altogether.

.. _When-Buildslaves-Go-Missing:

When Buildslaves Go Missing
+++++++++++++++++++++++++++

Sometimes, the buildslaves go away.
One very common reason for this is when the buildslave process is started once (manually) and left running, but then later the machine reboots and the process is not automatically restarted.

If you'd like to have the administrator of the buildslave (or other people) be notified by email when the buildslave has been missing for too long, just add the ``notify_on_missing=`` argument to the :class:`BuildSlave` definition.
This value can be a single email address, or a list of addresses::

    c['slaves'] = [
        buildslave.BuildSlave('bot-solaris', 'solarispasswd',
                              notify_on_missing="bob@example.com")
    ]

By default, this will send email when the buildslave has been disconnected for more than one hour.
Only one email per connection-loss event will be sent.
To change the timeout, use ``missing_timeout=`` and give it a number of seconds (the default is 3600).

You can have the buildmaster send email to multiple recipients: just provide a list of addresses instead of a single one::

    c['slaves'] = [
        buildslave.BuildSlave('bot-solaris', 'solarispasswd',
                              notify_on_missing=["bob@example.com",
                                                 "alice@example.org"],
                              missing_timeout=300) # notify after 5 minutes
    ]

The email sent this way will use a :class:`MailNotifier` (see :bb:reporter:`MailNotifier`) status target, if one is configured.
This provides a way for you to control the *from* address of the email, as well as the relayhost (aka *smarthost*) to use as an SMTP server.
If no :class:`MailNotifier` is configured on this buildmaster, the buildslave-missing emails will be sent using a default configuration.

Note that if you want to have a :class:`MailNotifier` for buildslave-missing emails but not for regular build emails, just create one with ``builders=[]``, as follows::

    from buildbot.plugins import status, buildslave
    m = status.MailNotifier(fromaddr="buildbot@localhost", builders=[],
                            relayhost="smtp.example.org")
    c['status'].append(m)

    c['slaves'] = [
            buildslave.BuildSlave('bot-solaris', 'solarispasswd',
                                  notify_on_missing="bob@example.com")
    ]

.. index:: BuildSlaves; latent

.. _Local-Buildslaves:

Local Buildslaves
~~~~~~~~~~~~~~~~~
For smaller setups, you may want to just run the slaves on the same machine as the master.
To simplify the maintainance, you may even want to run them in the same process.

This is what LocalBuildSlave is for.
Instead of configuring a ``buildslave.BuildSlave``, you have to configure a ``buildslave.LocalBuildSlave``.
As the slave is running on the same process, password is not necessary.
You can run as many local slaves as long as your machine CPU and memory is allowing.

A configuration for two slaves would look like::

    from buildbot.plugins import buildslave
    c['slaves'] = [
        buildslave.LocalBuildSlave('bot1'),
        buildslave.LocalBuildSlave('bot2'),
    ]


.. index:: BuildSlaves; latent

.. _Latent-Buildslaves:

Latent Buildslaves
~~~~~~~~~~~~~~~~~~

The standard buildbot model has slaves started manually.
The previous section described how to configure the master for this approach.

Another approach is to let the buildbot master start slaves when builds are ready, on-demand.
Thanks to services such as Amazon Web Services' Elastic Compute Cloud ("AWS EC2"), this is relatively easy to set up, and can be very useful for some situations.

The buildslaves that are started on-demand are called "latent" buildslaves.
As of this writing, buildbot ships with an abstract base class for building latent buildslaves, and a concrete implementation for AWS EC2 and for libvirt.

.. _Common-Latent-Buildslaves-Options:

Common Options
++++++++++++++

The following options are available for all latent buildslaves.

``build_wait_timeout``
    This option allows you to specify how long a latent slave should wait after a build for another build before it shuts down.
    It defaults to 10 minutes.
    If this is set to 0 then the slave will be shut down immediately.
    If it is less than 0 it will never automatically shutdown.

Supported Latent Buildslaves
++++++++++++++++++++++++++++

As of time of writing, Buildbot supports the following latent buildslaves:

.. toctree::
   :maxdepth: 1

   cfg-buildslaves-ec2.rst
   cfg-buildslaves-libvirt.rst
   cfg-buildslaves-openstack.rst
   cfg-buildslaves-docker.rst

Dangers with Latent Buildslaves
+++++++++++++++++++++++++++++++

Any latent build slave that interacts with a for-fee service, such as the EC2LatentBuildSlave, brings significant risks.
As already identified, the configuration will need access to account information that, if obtained by a criminal, can be used to charge services to your account.
Also, bugs in the buildbot software may lead to unnecessary charges.
In particular, if the master neglects to shut down an instance for some reason, a virtual machine may be running unnecessarily, charging against your account.
Manual and/or automatic (e.g. nagios with a plugin using a library like boto) double-checking may be appropriate.

A comparatively trivial note is that currently if two instances try to attach to the same latent buildslave, it is likely that the system will become confused.
This should not occur, unless, for instance, you configure a normal build slave to connect with the authentication of a latent buildbot.
If this situation does occurs, stop all attached instances and restart the master.
