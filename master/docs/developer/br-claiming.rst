..
    TODO: replace generic references here with refs to specific bb:msg's

.. _Claiming-Build-Requests:

Claiming Build Requests
=======================

At Buildbot's core, it is a distributed job (build) scheduling engine.
Future builds are represented by build requests, which are created by schedulers.

When a new build request is created, it is added to the ``buildrequests`` table and an appropriate message is sent.

Distributing
------------

Each master distributes build requests among its builders by examining the list of available build requests, available workers, and accounting for user configuration for build request priority, worker priority, and so on.
This distribution process is re-run whenever an event occurs that may allow a new build to start.

Such events can be signalled to master with

* :py:meth:`~buildbot.process.botmaster.BotMaster.maybeStartBuildsForBuilder` when a single builder is affected;
* :py:meth:`~buildbot.process.botmaster.BotMaster.maybeStartBuildsForWorker` when a single worker is affected; or
* :py:meth:`~buildbot.process.botmaster.BotMaster.maybeStartBuildsForAllBuilders` when all builders may be affected.

In particular, when a master receives a new-build-request message, it performs the equivalent of :py:meth:`~buildbot.process.botmaster.BotMaster.maybeStartBuildsForBuilder` for the affected builder.

Claiming
--------

If circumstances are right for a master to begin a build, then it attempts to "claim" the build request.
In fact, if several build requests were merged, it attempts to claim them as a group, using the :py:meth:`~buildbot.db.buildrequests.BuildRequestDistributor.claimBuildRequests` DB method.
This method uses transactions and an insert into the ``buildrequest_claims`` table to ensure that exactly one master succeeds in claiming any particular build request.

If the claim fails, then another master has claimed the affected build requests, and the attempt is abandoned.

If the claim succeeds, then the master sends a message indicating that it has claimed the request.
This message can be used by other masters to abandon their attempts to claim this request, although this is not yet implemented.

If the build request is later abandoned (as can happen if, for example, the worker has disappeared), then master will send a message indicating that the request is again unclaimed; like a new-buildrequest message, this message indicates that other masters should try to distribute it once again.

The One That Got Away
---------------------

The claiming process is complex, and things can go wrong at just about any point.
Through master failures or message/database race conditions, it's quite possible for a build request to be "missed", even when resources are available to process it.

To account for this possibility, masters periodically poll the ``buildrequests`` table for unclaimed requests and try to distribute them.
This resiliency avoids "lost" build requests, at the small cost of a polling delay before the requests are scheduled.
