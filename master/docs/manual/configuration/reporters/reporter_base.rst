ReporterBase
++++++++++++

.. py:currentmodule:: buildbot.reporters.base

.. py:class:: ReporterBase

:class:`ReporterBase` is a base class used to implement various reporters.
It accepts a list of :ref:`report generators<Report-Generators>` which define what messages to issue on what events.
If generators decide that an event needs a report, then the ``sendMessages`` function is called.
The ``sendMessages`` function should be implemented by deriving classes.


.. py:class:: ReporterBase(generators=None)
    :noindex:

``generators``
    (optional until Buildbot 3.0 is released, then mandatory)
    (a list of report generator instances)
    A list of report generators to manage.
