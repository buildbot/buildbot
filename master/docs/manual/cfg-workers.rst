.. -*- rst -*-
.. _Workers:

.. bb:cfg:: workers

Workers
-------

The :bb:cfg:`workers` configuration key specifies a list of known workers.
In the common case, each worker is defined by an instance of the :class:`Worker` class.
It represents a standard, manually started machine that will try to connect to the buildbot master as a worker.
Buildbot also supports "on-demand", or latent, workers, which allow buildbot to dynamically start and stop worker instances.

.. contents::
    :depth: 1
    :local:

Defining Workers
~~~~~~~~~~~~~~~~

A :class:`Worker` instance is created with a ``workername`` and a ``workerpassword``.
These are the same two values that need to be provided to the worker administrator when they create the worker.

The workername must be unique, of course.
The password exists to prevent evildoers from interfering with the buildbot by inserting their own (broken) workers into the system and thus displacing the real ones.

Workers with an unrecognized workername or a non-matching password will be rejected when they attempt to connect, and a message describing the problem will be written to the log file (see :ref:`Logfiles`).

A configuration for two workers would look like::

    from buildbot.plugins import worker
    c['workers'] = [
        worker.Worker('bot-solaris', 'solarispasswd'),
        worker.Worker('bot-bsd', 'bsdpasswd'),
    ]

Worker Options
~~~~~~~~~~~~~~

.. index:: Properties; from worker

:class:`Worker` objects can also be created with an optional ``properties`` argument, a dictionary specifying properties that will be available to any builds performed on this worker.
For example::

    c['workers'] = [
        worker.Worker('bot-solaris', 'solarispasswd',
                      properties={ 'os':'solaris' }),
    ]

.. index:: Workers; limiting concurrency

The :class:`Worker` constructor can also take an optional ``max_builds`` parameter to limit the number of builds that it will execute simultaneously::

    c['workers'] = [
        worker.Worker("bot-linux", "linuxpassword", max_builds=2)
    ]

Master-Worker TCP Keepalive
+++++++++++++++++++++++++++

By default, the buildmaster sends a simple, non-blocking message to each worker every hour.
These keepalives ensure that traffic is flowing over the underlying TCP connection, allowing the system's network stack to detect any problems before a build is started.

The interval can be modified by specifying the interval in seconds using the ``keepalive_interval`` parameter of :class:`Worker`::

    c['workers'] = [
        worker.Worker('bot-linux', 'linuxpasswd',
                      keepalive_interval=3600)
    ]

The interval can be set to ``None`` to disable this functionality altogether.

.. _When-Workers-Go-Missing:

When Workers Go Missing
+++++++++++++++++++++++

Sometimes, the workers go away.
One very common reason for this is when the worker process is started once (manually) and left running, but then later the machine reboots and the process is not automatically restarted.

If you'd like to have the administrator of the worker (or other people) be notified by email when the worker has been missing for too long, just add the ``notify_on_missing=`` argument to the :class:`Worker` definition.
This value can be a single email address, or a list of addresses::

    c['workers'] = [
        worker.Worker('bot-solaris', 'solarispasswd',
                      notify_on_missing="bob@example.com")
    ]

By default, this will send email when the worker has been disconnected for more than one hour.
Only one email per connection-loss event will be sent.
To change the timeout, use ``missing_timeout=`` and give it a number of seconds (the default is 3600).

You can have the buildmaster send email to multiple recipients: just provide a list of addresses instead of a single one::

    c['workers'] = [
        worker.Worker('bot-solaris', 'solarispasswd',
                      notify_on_missing=["bob@example.com",
                                         "alice@example.org"],
                      missing_timeout=300)  # notify after 5 minutes
    ]

The email sent this way will use a :class:`MailNotifier` (see :bb:reporter:`MailNotifier`) status target, if one is configured.
This provides a way for you to control the *from* address of the email, as well as the relayhost (aka *smarthost*) to use as an SMTP server.
If no :class:`MailNotifier` is configured on this buildmaster, the worker-missing emails will be sent using a default configuration.

Note that if you want to have a :class:`MailNotifier` for worker-missing emails but not for regular build emails, just create one with ``builders=[]``, as follows::

    from buildbot.plugins import status, worker
    m = status.MailNotifier(fromaddr="buildbot@localhost", builders=[],
                            relayhost="smtp.example.org")
    c['status'].append(m)

    c['workers'] = [
            worker.Worker('bot-solaris', 'solarispasswd',
                          notify_on_missing="bob@example.com")
    ]

.. index:: Workers; local

.. _Local-Workers:

Local Workers
~~~~~~~~~~~~~
For smaller setups, you may want to just run the workers on the same machine as the master.
To simplify the maintainance, you may even want to run them in the same process.

This is what LocalWorker is for.
Instead of configuring a ``worker.Worker``, you have to configure a ``worker.LocalWorker``.
As the worker is running on the same process, password is not necessary.
You can run as many local workers as long as your machine CPU and memory is allowing.

A configuration for two workers would look like::

    from buildbot.plugins import worker
    c['workers'] = [
        worker.LocalWorker('bot1'),
        worker.LocalWorker('bot2'),
    ]

In order to use local workers you need to have ``buildbot-worker`` package installed.

.. index:: Workers; latent

.. _Latent-Workers:

Latent Workers
~~~~~~~~~~~~~~

The standard buildbot model has workers started manually.
The previous section described how to configure the master for this approach.

Another approach is to let the buildbot master start workers when builds are ready, on-demand.
Thanks to services such as Amazon Web Services' Elastic Compute Cloud ("AWS EC2"), this is relatively easy to set up, and can be very useful for some situations.

The workers that are started on-demand are called "latent" workers.
As of this writing, buildbot ships with an abstract base class for building latent workers, and a concrete implementation for AWS EC2 and for libvirt.

.. _Common-Latent-Workers-Options:

Common Options
++++++++++++++

The following options are available for all latent workers.

``build_wait_timeout``
    This option allows you to specify how long a latent worker should wait after a build for another build before it shuts down.
    It defaults to 10 minutes.
    If this is set to 0 then the worker will be shut down immediately.
    If it is less than 0 it will never automatically shutdown.

Supported Latent Workers
++++++++++++++++++++++++

As of time of writing, Buildbot supports the following latent workers:

.. toctree::
   :maxdepth: 1

   cfg-workers-ec2.rst
   cfg-workers-libvirt.rst
   cfg-workers-openstack.rst
   cfg-workers-docker.rst

Dangers with Latent Workers
+++++++++++++++++++++++++++

Any latent worker that interacts with a for-fee service, such as the :class:`~buildbot.worker.ec2.EC2LatentWorker`, brings significant risks.
As already identified, the configuration will need access to account information that, if obtained by a criminal, can be used to charge services to your account.
Also, bugs in the buildbot software may lead to unnecessary charges.
In particular, if the master neglects to shut down an instance for some reason, a virtual machine may be running unnecessarily, charging against your account.
Manual and/or automatic (e.g. nagios with a plugin using a library like boto) double-checking may be appropriate.

A comparatively trivial note is that currently if two instances try to attach to the same latent worker, it is likely that the system will become confused.
This should not occur, unless, for instance, you configure a normal worker to connect with the authentication of a latent buildbot.
If this situation does occurs, stop all attached instances and restart the master.
