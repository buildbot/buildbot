.. -*- rst -*-
.. _Workers:

.. bb:cfg:: workers

Workers
-------

The :bb:cfg:`workers` configuration key specifies a list of known workers.
In the common case, each worker is defined by an instance of the :class:`buildbot.worker.Worker` class.
It represents a standard, manually started machine that will try to connect to the Buildbot master as a worker.
Buildbot also supports "on-demand", or latent, workers, which allow Buildbot to dynamically start and stop worker instances.

.. contents::
    :depth: 1
    :local:

Defining Workers
~~~~~~~~~~~~~~~~

A :class:`Worker` instance is created with a ``workername`` and a ``workerpassword``.
These are the same two values that need to be provided to the worker administrator when they create the worker.

The ``workername`` must be unique, of course.
The password exists to prevent evildoers from interfering with the Buildbot by inserting their own (broken) workers into the system and thus displacing the real ones.

Workers with an unrecognized ``workername`` or a non-matching password will be rejected when they attempt to connect, and a message describing the problem will be written to the log file (see :ref:`Logfiles`).

A configuration for two workers would look like:

.. code-block:: python

    from buildbot.plugins import worker
    c['workers'] = [
        worker.Worker('bot-solaris', 'solarispasswd'),
        worker.Worker('bot-bsd', 'bsdpasswd'),
    ]

Worker Options
~~~~~~~~~~~~~~

Properties
++++++++++

.. index:: Properties; from worker

:class:`Worker` objects can also be created with an optional ``properties`` argument, a dictionary specifying properties that will be available to any builds performed on this worker.
For example:

.. code-block:: python

    c['workers'] = [
        worker.Worker('bot-solaris', 'solarispasswd',
                      properties={ 'os':'solaris' }),
    ]

:class:`Worker` properties have priority over other sources (:class:`Builder`, :class:`Scheduler`, etc.).
You may use the ``defaultProperties`` parameter that will only be added to :ref:`Build-Properties` if they are not already set by :ref:`another source <Properties>`:

.. code-block:: python

   c['workers'] = [
       worker.Worker('fast-bot', 'fast-passwd',
                     defaultProperties={'parallel_make': 10}),
   ]

:class:`Worker` collects and exposes ``/etc/os-release`` fields for :ref:<interpolation `Interpolate-DictStyle`>.
These can be used to determine details about the running operating system, such as distribution and version.
See https://www.linux.org/docs/man5/os-release.html for details on possible fields.
Each field is imported with ``os_`` prefix and in lower case. ``os_id``, ``os_id_like``, ``os_version_id`` and ``os_version_codename`` are always set, but can be null.

Limiting Concurrency
++++++++++++++++++++

.. index:: Workers; limiting concurrency

The :class:`Worker` constructor can also take an optional ``max_builds`` parameter to limit the number of builds that it will execute simultaneously:

.. code-block:: python

    c['workers'] = [
        worker.Worker('bot-linux', 'linuxpassword',
                      max_builds=2),
    ]

.. note::

    In :ref:`worker-for-builders` concept only one build from the same builder would run on the worker.

Master-Worker TCP Keepalive
+++++++++++++++++++++++++++

By default, the buildmaster sends a simple, non-blocking message to each worker every hour.
These keepalives ensure that traffic is flowing over the underlying TCP connection, allowing the system's network stack to detect any problems before a build is started.

The interval can be modified by specifying the interval in seconds using the ``keepalive_interval`` parameter of :class:`Worker` (defaults to 3600):

.. code-block:: python

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
This value can be a single email address, or a list of addresses:

.. code-block:: python

    c['workers'] = [
        worker.Worker('bot-solaris', 'solarispasswd',
                      notify_on_missing='bob@example.com')
    ]

By default, this will send email when the worker has been disconnected for more than one hour.
Only one email per connection-loss event will be sent.
To change the timeout, use ``missing_timeout=`` and give it a number of seconds (the default is 3600).

You can have the buildmaster send email to multiple recipients: just provide a list of addresses instead of a single one:

.. code-block:: python

    c['workers'] = [
        worker.Worker('bot-solaris', 'solarispasswd',
                      notify_on_missing=['bob@example.com',
                                         'alice@example.org'],
                      missing_timeout=300)  # notify after 5 minutes
    ]

The email sent this way will use a :class:`MailNotifier` (see :bb:reporter:`MailNotifier`) status target, if one is configured.
This provides a way for you to control the *from* address of the email, as well as the relayhost (aka *smarthost*) to use as an SMTP server.
If no :class:`MailNotifier` is configured on this buildmaster, the worker-missing emails will be sent using a default configuration.

Note that if you want to have a :class:`MailNotifier` for worker-missing emails but not for regular build emails, just create one with ``builders=[]``, as follows:

.. code-block:: python

    from buildbot.plugins import status, worker
    m = status.MailNotifier(fromaddr='buildbot@localhost', builders=[],
                            relayhost='smtp.example.org')
    c['reporters'].append(m)

    c['workers'] = [
            worker.Worker('bot-solaris', 'solarispasswd',
                          notify_on_missing='bob@example.com')
    ]


.. _Worker-states:

Workers States
++++++++++++++

There are some times when a worker misbehaves because of issues with its configuration.
In those cases, you may want to pause the worker, or maybe completely shut it down.

There are three actions that you may take (in the worker's web page *Actions* dialog)

- *Pause*: If a worker is paused, it won't accept new builds. The action of pausing a worker will not affect any build ongoing.

- *Graceful Shutdown*: If a worker is in graceful shutdown mode, it won't accept new builds, but will finish the current builds.
  When all of its build are finished, the :command:`buildbot-worker` process will terminate.

- *Force Shutdown*: If a worker is in force shutdown mode, it will terminate immediately, and the build he was currently doing will be put to retry state.

Those actions will put the worker in two states

- *paused*: the worker is paused if it is connected but doesn't accept new builds.
- *graceful*: the worker is graceful if it doesn't accept new builds, and will shutdown when builds are finished.


A worker might be put to ``paused`` state automatically if buildbot detects a misbehavior.
This is called the *quarantine timer*.

Quarantine timer is an exponential back-off mechanism for workers.
This avoids a misbehaving worker to eat the build queue by quickly finishing builds in ``EXCEPTION`` state.
When misbehavior is detected, the timer will pause the worker for 10 second, and then that time will double at each misbehavior detection, until the worker finishes a build.

The first case of misbehavior is for a latent worker to not start properly.
The second case of misbehavior is for a build to end with an ``EXCEPTION`` status.

Worker states are stored in the database, can be queried via :ref:`REST_API` and visible in the UI's workers page.


.. index:: Workers; local

.. _Local-Workers:

Local Workers
~~~~~~~~~~~~~
For smaller setups, you may want to just run the workers on the same machine as the master.
To simplify the maintenance, you may even want to run them in the same process.

This is what LocalWorker is for.
Instead of configuring a ``worker.Worker``, you have to configure a ``worker.LocalWorker``.
As the worker is running on the same process, password is not necessary.
You can run as many local workers as long as your machine CPU and memory is allowing.

A configuration for two workers would look like:

.. code-block:: python

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

The standard Buildbot model has workers started manually.
The previous section described how to configure the master for this approach.

Another approach is to let the Buildbot master start workers when builds are ready, on-demand.
Thanks to services such as Amazon Web Services' Elastic Compute Cloud ("AWS EC2"), this is relatively easy to set up, and can be very useful for some situations.

The workers that are started on-demand are called "latent" workers.
You can find the list of :ref:`Supported-Latent-Workers` below.

.. _Common-Latent-Workers-Options:

Common Options
++++++++++++++

The following options are available for all latent workers.

``build_wait_timeout``
    This option allows you to specify how long a latent worker should wait after a build for another build before it shuts down.
    It defaults to 10 minutes.
    If this is set to 0 then the worker will be shut down immediately.
    If it is less than 0 it will be shut down only when shutting down master.

.. _Supported-Latent-Workers:

Supported Latent Workers
++++++++++++++++++++++++

As of time of writing, Buildbot supports the following latent workers:

.. toctree::
   :maxdepth: 1

   workers-ec2.rst
   workers-libvirt.rst
   workers-openstack.rst
   workers-docker.rst

Dangers with Latent Workers
+++++++++++++++++++++++++++

Any latent worker that interacts with a for-fee service, such as the :class:`~buildbot.worker.ec2.EC2LatentWorker`, brings significant risks.
As already identified, the configuration will need access to account information that, if obtained by a criminal, can be used to charge services to your account.
Also, bugs in the Buildbot software may lead to unnecessary charges.
In particular, if the master neglects to shut down an instance for some reason, a virtual machine may be running unnecessarily, charging against your account.
Manual and/or automatic (e.g. Nagios with a plugin using a library like boto) double-checking may be appropriate.

A comparatively trivial note is that currently if two instances try to attach to the same latent worker, it is likely that the system will become confused.
This should not occur, unless, for instance, you configure a normal worker to connect with the authentication of a latent buildbot.
If this situation does occurs, stop all attached instances and restart the master.
