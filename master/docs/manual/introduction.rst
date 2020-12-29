.. _Introduction:

Introduction
============

Buildbot is a framework to automate the compile and test cycle that is used to validate code changes in most software projects.

Features:

* run builds on a variety of worker platforms
* arbitrary build process: handles projects using C, Python, whatever
* minimal host requirements: Python and Twisted
* workers can be behind a firewall if they can still do checkout
* status delivery through web page, email, IRC, other protocols
* flexible configuration by subclassing generic build process classes
* debug tools to force a new build, submit fake :class:`Change`\s, query worker status
* released under the `GPL <https://opensource.org/licenses/gpl-2.0.php>`_

.. _System-Architecture:

System Architecture
-------------------

The Buildbot consists of a single *buildmaster* and one or more *workers*, connected in a star topology.
The buildmaster makes all decisions about what, when, and how to build.
It sends commands to be run on the workers, which simply execute the commands and return the results.
(certain steps involve more local decision making, where the overhead of sending a lot of commands back and forth would be inappropriate, but in general the buildmaster is responsible for everything).

The buildmaster is usually fed :class:`Change`\s by some sort of version control system (:ref:`change-sources`), which may cause builds to be run.
As the builds are performed, various status messages are produced, which are then sent to any registered :ref:`reporters`.

.. image:: _images/overview.*
   :alt: Overview Diagram

The buildmaster is configured and maintained by the *buildmaster admin*, who is generally the project team member responsible for build process issues.
Each worker is maintained by a *worker admin*, who do not need to be quite as involved.
Generally workers are run by anyone who has an interest in seeing the project work well on their favorite platform.

.. Worker-Connections:

Worker Connections
~~~~~~~~~~~~~~~~~~

The workers are typically run on a variety of separate machines, at least one per platform of interest.
These machines connect to the buildmaster over a TCP connection to a publicly-visible port.
As a result, the workers can live behind a NAT box or similar firewalls, as long as they can get to buildmaster.
The TCP connections are initiated by the worker and accepted by the buildmaster, but commands and results travel both ways within this connection.
The buildmaster is always in charge, so all commands travel exclusively from the buildmaster to the worker.

To perform builds, the workers must typically obtain source code from a CVS/SVN/etc repository.
Therefore they must also be able to reach the repository.
The buildmaster provides instructions for performing builds, but does not provide the source code itself.

.. image:: _images/workers.*
   :alt: Worker Connections

.. _Buildmaster-Architecture:

Buildmaster Architecture
~~~~~~~~~~~~~~~~~~~~~~~~

The buildmaster consists of several pieces:

.. image:: _images/master.*
   :alt: Buildmaster Architecture

Change Sources
    Which create a Change object each time something is modified in the VC repository.
    Most :class:`ChangeSource`\s listen for messages from a hook script of some sort.
    Some sources actively poll the repository on a regular basis.
    All :class:`Change`\s are fed to the schedulers.

Schedulers
    Which decide when builds should be performed.
    They collect :class:`Change`\s into :class:`BuildRequest`\s, which are then queued for delivery to :class:`Builders` until a worker is available.

Builders
    Which control exactly *how* each build is performed (with a series of :class:`BuildStep`\s, configured in a :class:`BuildFactory`).
    Each :class:`Build` is run on a single worker.

Status plugins
    Which deliver information about the build results through protocols like HTTP, mail, and IRC.

Each :class:`Builder` is configured with a list of :class:`Worker`\s that it will use for its builds.
These workers are expected to behave identically: the only reason to use multiple :class:`Worker`\s for a single :class:`Builder` is to provide a measure of load-balancing.

Within a single :class:`Worker`, each :class:`Builder` creates its own :class:`WorkerForBuilder` instance.
These :class:`WorkerForBuilder`\s operate independently from each other.
Each gets its own base directory to work in.
It is quite common to have many :class:`Builder`\s sharing the same worker.
For example, there might be two workers: one for i386, and a second for PowerPC.
There may then be a pair of :class:`Builder`\s that do a full compile/test run, one for each architecture, and a lone :class:`Builder` that creates snapshot source tarballs if the full builders complete successfully.
The full builders would each run on a single worker, whereas the tarball creation step might run on either worker (since the platform doesn't matter when creating source tarballs).
In this case, the mapping would look like:

.. code-block:: none

    Builder(full-i386)  ->  Workers(worker-i386)
    Builder(full-ppc)   ->  Workers(worker-ppc)
    Builder(source-tarball) -> Workers(worker-i386, worker-ppc)

and each :class:`Worker` would have two :class:`WorkerForBuilder`\s inside it, one for a full builder, and a second for the source-tarball builder.

Once a :class:`WorkerForBuilder` is available, the :class:`Builder` pulls one or more :class:`BuildRequest`\s off its incoming queue.
(It may pull more than one if it determines that it can merge the requests together; for example, there may be multiple requests to build the current *HEAD* revision).
These requests are merged into a single :class:`Build` instance, which includes the :class:`SourceStamp` that describes what exact version of the source code should be used for the build.
The :class:`Build` is then randomly assigned to a free :class:`WorkerForBuilder` and the build begins.

The behaviour when :class:`BuildRequest`\s are merged can be customized, :ref:`Collapsing-Build-Requests`.

.. _Status-Delivery-Architecture:

Status Delivery Architecture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The buildmaster maintains a central :class:`Status` object, to which various status plugins are connected.
Through this :class:`Status` object, a full hierarchy of build status objects can be obtained.

.. image:: _images/status.*
   :alt: Status Delivery

The configuration file controls which status plugins are active.
Each status plugin gets a reference to the top-level :class:`Status` object.
From there they can request information on each :class:`Builder`, :class:`Build`, :class:`Step`, and :class:`LogFile`.
This query-on-demand interface is used by the ``html.Waterfall`` plugin to create the main status page each time a web browser hits the main URL.

The status plugins can also subscribe to hear about new :class:`Build`\s as they occur: this is used by the :class:`MailNotifier` to create new email messages for each recently-completed :class:`Build`.

The :class:`Status` object records the status of old builds on disk in the buildmaster's base directory.
This allows it to return information about historical builds.

There are also status objects that correspond to :class:`Scheduler`\s and :class:`Worker`\s.
These allow status plugins to report information about upcoming builds, and the online/offline status of each worker.

.. _Control-Flow:

Control Flow
------------

A day in the life of the Buildbot:

* A developer commits some source code changes to the repository.
  A hook script or commit trigger of some sort sends information about this change to the buildmaster through one of its configured Change Sources.
  This notification might arrive via email, or over a network connection (either initiated by the buildmaster as it *subscribes* to changes, or by the commit trigger as it pushes :class:`Change`\s towards the buildmaster).
  The :class:`Change` contains information about who made the change, what files were modified, which revision contains the change, and any checkin comments.

* The buildmaster distributes this change to all of its configured schedulers.
  Any ``important`` changes cause the ``tree-stable-timer`` to be started, and the :class:`Change` is added to a list of those that will go into a new :class:`Build`.
  When the timer expires, a :class:`Build` is started on each of a set of configured Builders, all compiling/testing the same source code.
  Unless configured otherwise, all :class:`Build`\s run in parallel on the various workers.

* The :class:`Build` consists of a series of :class:`Step`\s.
  Each :class:`Step` causes some number of commands to be invoked on the remote worker associated with that :class:`Builder`.
  The first step is almost always to perform a checkout of the appropriate revision from the same VC system that produced the :class:`Change`.
  The rest generally perform a compile and run unit tests.
  As each :class:`Step` runs, the worker reports back command output and return status to the buildmaster.

* As the :class:`Build` runs, status messages like "Build Started", "Step Started", "Build Finished", etc, are published to a collection of Status Targets.
  One of these targets is usually the HTML ``Waterfall`` display, which shows a chronological list of events, and summarizes the results of the most recent build at the top of each column.
  Developers can periodically check this page to see how their changes have fared.
  If they see red, they know that they've made a mistake and need to fix it.
  If they see green, they know that they've done their duty and don't need to worry about their change breaking anything.

* If a :class:`MailNotifier` status target is active, the completion of a build will cause email to be sent to any developers whose :class:`Change`\s were incorporated into this :class:`Build`.
  The :class:`MailNotifier` can be configured to only send mail upon failing builds, or for builds which have just transitioned from passing to failing.
  Other status targets can provide similar real-time notification via different communication channels, like IRC.
