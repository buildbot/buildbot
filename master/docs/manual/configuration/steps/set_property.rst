.. bb:step:: SetProperty

.. _Step-SetProperty:

SetProperty
+++++++++++

.. py:class:: buildbot.steps.master.SetProperty

:bb:step:`SetProperty` takes two arguments of ``property`` and ``value`` where the ``value`` is to be assigned to the ``property`` key.
It is usually called with the ``value`` argument being specified as an :ref:`Interpolate` object which allows the value to be built from other property values:

.. code-block:: python

    from buildbot.plugins import steps, util

    f.addStep(
        steps.SetProperty(
            property="SomeProperty",
            value=util.Interpolate("sch=%(prop:scheduler)s, worker=%(prop:workername)s")
        )
    )
