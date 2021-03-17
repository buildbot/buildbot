.. bb:cfg:: configurators

Configurators
-------------

For advanced users or plugin writers, the ``configurators`` key is available and holds a list of :py:class:`buildbot.interfaces.IConfigurator`.
The configurators will run after the ``master.cfg`` has been processed, and will modify the config dictionary.
Configurator implementers should make sure that they are interoperable with each other, which means carefully modifying the config to avoid overriding a setting already made by the user or another configurator.
Configurators are run (thus prioritized) in the order of the ``configurators`` list.

.. bb:configurator:: JanitorConfigurator

JanitorConfigurator
~~~~~~~~~~~~~~~~~~~

Buildbot stores historical information in its database.
In a large installation, these can quickly consume disk space, yet developers never consult this historical information in many cases.

:bb:configurator:`JanitorConfigurator` creates a builder and :bb:sched:`Nightly` scheduler which will regularly remove old information.
At the moment, it only supports cleaning of logs, but it will contain more features as we implement them.

::

    from buildbot.plugins import util
    from datetime import timedelta

    # configure a janitor which will delete all logs older than one month,
    # and will run on sundays at noon
    c['configurators'] = [util.JanitorConfigurator(
        logHorizon=timedelta(weeks=4),
        hour=12,
        dayOfWeek=6
    )]


Parameters for :bb:configurator:`JanitorConfigurator` are:

``logHorizon``
    A ``timedelta`` object describing the minimum time for which the log data should be maintained.

``hour``, ``dayOfWeek``, ...
    Arguments given to the :bb:sched:`Nightly` scheduler which is backing the :bb:configurator:`JanitorConfigurator`.
    Determines when the cleanup will be done.
    With this, you can configure it daily, weekly or even hourly if you wish.
    You probably want to schedule it when Buildbot is less loaded.
