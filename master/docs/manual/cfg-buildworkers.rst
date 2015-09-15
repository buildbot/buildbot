.. -*- rst -*-
.. _Buildworkers:

.. bb:cfg:: workers

Buildworkers
------------

The :bb:cfg:`workers` configuration key specifies a list of known buildworkers.
In the common case, each buildworker is defined by an instance of the :class:`BuildWorker` class.
It represents a standard, manually started machine that will try to connect to the buildbot master as a worker.
Buildbot also supports "on-demand", or latent, buildworkers, which allow buildbot to dynamically start and stop buildworker instances.

.. contents::
    :depth: 1
    :local:

Defining Buildworkers
~~-~~~~~~~~~~~~~~~~~~

A :class:`BuildWorker` instance is created with a ``workername`` and a ``workerpassword``.
These are the same two values that need to be provided to the buildworker administrator when they create the buildworker.

The workername must be unique, of course.
The password exists to prevent evildoers from interfering with the buildbot by inserting their own (broken) buildworkers into the system and thus displacing the real ones.

Buildworkers with an unrecognized workername or a non-matching password will be rejected when they attempt to connect, and a message describing the problem will be written to the log file (see :ref:`Logfiles`).

A configuration for two workers would look like::

    from buildbot.plugins import buildworker
    c['workers'] = [
        buildworker.BuildWorker('bot-solaris', 'solarispasswd'),
        buildworker.BuildWorker('bot-bsd', 'bsdpasswd'),
    ]

BuildWorker Options
~~~-~~~~~~~~~~~~~~~

.. index:: Properties; from buildworker

:class:`BuildWorker` objects can also be created with an optional ``properties`` argument, a dictionary specifying properties that will be available to any builds performed on this worker.
For example::

    c['workers'] = [
        buildworker.BuildWorker('bot-solaris', 'solarispasswd',
                              properties={ 'os':'solaris' }),
    ]

.. index:: Build Workers; limiting concurrency

The :class:`BuildWorker` constructor can also take an optional ``max_builds`` parameter to limit the number of builds that it will execute simultaneously::

    c['workers'] = [
        buildworker.BuildWorker("bot-linux", "linuxpassword", max_builds=2)
    ]

Master-Worker TCP Keepalive
+++++++++++++++++++++++++++

By default, the buildmaster sends a simple, non-blocking message to each worker every hour.
These keepalives ensure that traffic is flowing over the underlying TCP connection, allowing the system's network stack to detect any problems before a build is started.

The interval can be modified by specifying the interval in seconds using the ``keepalive_interval`` parameter of BuildWorker::

    c['workers'] = [
        buildworker.BuildWorker('bot-linux', 'linuxpasswd',
                              keepalive_interval=3600)
    ]

The interval can be set to ``None`` to disable this functionality altogether.

.. _When-Buildworkers-Go-Missing:

When Buildworkers Go Missing
++++++++++++++++++++++++++++

Sometimes, the buildworkers go away.
One very common reason for this is when the buildworker process is started once (manually) and left running, but then later the machine reboots and the process is not automatically restarted.

If you'd like to have the administrator of the buildworker (or other people) be notified by email when the buildworker has been missing for too long, just add the ``notify_on_missing=`` argument to the :class:`BuildWorker` definition.
This value can be a single email address, or a list of addresses::

    c['workers'] = [
        buildworker.BuildWorker('bot-solaris', 'solarispasswd',
                              notify_on_missing="bob@example.com")
    ]

By default, this will send email when the buildworker has been disconnected for more than one hour.
Only one email per connection-loss event will be sent.
To change the timeout, use ``missing_timeout=`` and give it a number of seconds (the default is 3600).

You can have the buildmaster send email to multiple recipients: just provide a list of addresses instead of a single one::

    c['workers'] = [
        buildworker.BuildWorker('bot-solaris', 'solarispasswd',
                              notify_on_missing=["bob@example.com",
                                                 "alice@example.org"],
                              missing_timeout=300) # notify after 5 minutes
    ]

The email sent this way will use a :class:`MailNotifier` (see :bb:reporter:`MailNotifier`) status target, if one is configured.
This provides a way for you to control the *from* address of the email, as well as the relayhost (aka *smarthost*) to use as an SMTP server.
If no :class:`MailNotifier` is configured on this buildmaster, the buildworker-missing emails will be sent using a default configuration.

Note that if you want to have a :class:`MailNotifier` for buildworker-missing emails but not for regular build emails, just create one with ``builders=[]``, as follows::

    from buildbot.plugins import status, buildworker
    m = status.MailNotifier(fromaddr="buildbot@localhost", builders=[],
                            relayhost="smtp.example.org")
    c['status'].append(m)

    c['workers'] = [
            buildworker.BuildWorker('bot-solaris', 'solarispasswd',
                                  notify_on_missing="bob@example.com")
    ]

.. index:: BuildWorkers; latent

.. _Local-Buildworkers:

Local Buildworkers
~~~~~~~~~~~~~~~~~~
For smaller setups, you may want to just run the workers on the same machine as the master.
To simplify the maintainance, you may even want to run them in the same process.

This is what LocalBuildWorker is for.
Instead of configuring a ``buildworker.BuildWorker``, you have to configure a ``buildworker.LocalBuildWorker``.
As the worker is running on the same process, password is not necessary.
You can run as many local workers as long as your machine CPU and memory is allowing.

A configuration for two workers would look like::

    from buildbot.plugins import buildworker
    c['workers'] = [
        buildworker.LocalBuildWorker('bot1'),
        buildworker.LocalBuildWorker('bot2'),
    ]


.. index:: BuildWorkers; latent

.. _Latent-Buildworkers:

Latent Buildworkers
~~~~~~~~~~~~~~~~~~~

The standard buildbot model has workers started manually.
The previous section described how to configure the master for this approach.

Another approach is to let the buildbot master start workers when builds are ready, on-demand.
Thanks to services such as Amazon Web Services' Elastic Compute Cloud ("AWS EC2"), this is relatively easy to set up, and can be very useful for some situations.

The buildworkers that are started on-demand are called "latent" buildworkers.
As of this writing, buildbot ships with an abstract base class for building latent buildworkers, and a concrete implementation for AWS EC2 and for libvirt.

.. _Common-Latent-Buildworkers-Options:

Common Options
++++++++++++++

The following options are available for all latent buildworkers.

``build_wait_timeout``
    This option allows you to specify how long a latent worker should wait after a build for another build before it shuts down.
    It defaults to 10 minutes.
    If this is set to 0 then the worker will be shut down immediately.
    If it is less than 0 it will never automatically shutdown.

Supported Latent Buildworkers
+++++++++++++++++++++++++++++

As of time of writing, Buildbot supports the following latent buildworkers:

.. toctree::
   :maxdepth: 1

   cfg-buildworkers-ec2.rst
   cfg-buildworkers-libvirt.rst
   cfg-buildworkers-openstack.rst
   cfg-buildworkers-docker.rst

Dangers with Latent Buildworkers
++++++++++++++++++++++++++++++++

Any latent build worker that interacts with a for-fee service, such as the EC2LatentBuildWorker, brings significant risks.
As already identified, the configuration will need access to account information that, if obtained by a criminal, can be used to charge services to your account.
Also, bugs in the buildbot software may lead to unnecessary charges.
In particular, if the master neglects to shut down an instance for some reason, a virtual machine may be running unnecessarily, charging against your account.
Manual and/or automatic (e.g. nagios with a plugin using a library like boto) double-checking may be appropriate.

A comparatively trivial note is that currently if two instances try to attach to the same latent buildworker, it is likely that the system will become confused.
This should not occur, unless, for instance, you configure a normal build worker to connect with the authentication of a latent buildbot.
If this situation does occurs, stop all attached instances and restart the master.
