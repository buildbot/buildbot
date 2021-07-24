.. bb:cfg:: services

Custom Services
---------------

.. toctree::
    :hidden:
    :maxdepth: 2

    failing_buildset_canceller
    old_build_canceller

Custom services are stateful components of Buildbot that can be added to the ``services`` key of the Buildbot config dictionary.
The following is the services that are meant to be used without advanced knowledge of Buildbot.

 * :ref:`FailingBuildsetCanceller`
 * :ref:`OldBuildCanceller`

More complex services are described in the developer section of the Buildbot manual.
They are meant to be used by advanced users of Buildbot.
