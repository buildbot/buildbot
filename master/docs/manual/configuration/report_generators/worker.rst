.. bb:reportgen:: WorkerMissingGenerator

.. _Reportgen-WorkerMissingGenerator:

WorkerMissingGenerator
++++++++++++++++++++++

.. py:class:: buildbot.reporters.WorkerMissingGenerator

This report generator sends a message when a worker goes missing.

The following parameters are supported:

``workers``
    (``"all"`` or a list of strings, optional).
    Identifies the workers for which to send a message.
    ``"all"`` (the default) means that a message will be sent when any worker goes missing.
    The list version of the parameter specifies the names of the workers.

``message_formatter``
    (optional, instance of ``reporters.MessageFormatterMissingWorker``)
    This is an optional instance of the ``reporters.MessageFormatterMissingWorker`` class that can be used to generate a custom message.

