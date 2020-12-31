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

Buildbot consists of a single *buildmaster* and one or more *workers* that connect to the master.
The buildmaster makes all decisions about what, when, and how to build.
The workers only connect to master and execute whatever commands they are instructed to execute.

The usual flow of information is as follows:

 - the buildmaster fetches new code changes from version control systems

 - the buildmaster decides what builds (if any) to start

 - the builds are performed by executing commands on the workers (e.g. ``git clone``, ``make``, ``make check``).

 - the workers send back the results of the commands back to the buildmaster

 - buildmaster interprets the results of the commands and marks the builds as successful or failing

 - buildmaster sends success or failure reports to external services to e.g. inform the developers.

.. image:: _images/overview.*
   :alt: Overview Diagram

.. Worker-Connections:

Worker Connections
~~~~~~~~~~~~~~~~~~

The workers connect to the buildmaster over a TCP connection to a publicly-visible port.
This allows workers to live behind a NAT or similar firewalls as long as they can get to buildmaster.
After the connection is established, the connection is bidirectional: commands flow from the buildmaster to the worker and results flow from the worker to the buildmaster.

The buildmaster does not provide the workers with the source code itself, only with commands necessary to perform the source code checkout.
As a result, the workers need to be able to reach the source code repositories that they are supposed to build.

.. image:: _images/workers.*
   :alt: Worker Connections

.. _Buildmaster-Architecture:

Buildmaster Architecture
~~~~~~~~~~~~~~~~~~~~~~~~

The following is rough overview of the data flow within the buildmaster.

.. image:: _images/master.*
   :alt: Buildmaster Architecture

The following provides a short overview of the core components of Buildbot master.
For a more detailed description see the :ref:`Concepts` page.

The core components of Buildbot master are as follows:

Builders
    A :ref:`builder <Concepts-Builder>` is a user-configurable description of how to perform a build.
    It defines what steps a new build will have, what workers it may run on and a couple of other properties.
    A builder takes a :ref:`build request <Concepts-Build-Request>` which specifies the intention to create a build for specific versions of code and produces a :ref:`build<Concepts-Build>` which is a concrete description of a build including a list of :ref:`steps <Concepts-Step>` to perform, the worker this needs to be performed on and so on.

Schedulers:
    A :ref:`scheduler<Concepts-Scheduler>` is a user-configurable component that decides when to start a build.
    The decision could be based on time, on new code being committed or on similar events.

Change Sources:
    :ref:`Change sources<Concepts-Change-Source>` are user-configurable components that interact with external version control systems and retrieve new code.
    Internally new code is represented as :ref:`Changes <Concept-Change>` which roughly correspond to single commit or changeset.
    The design of Buildbot requires the workers to have their own copies of the source code, thus change sources is an optional component as long as there are no schedulers that create new builds based on new code commit events.

Reporters
    Reporters are user-configurable components that send information about started or completed builds to external sources.
    Buildbot provides its own web application to observe this data, so reporters are optional.
    However they can be used to provide up to date build status on platforms such as GitHub or sending emails.
