.. _MessageFormatterFunction:

MessageFormatterFunction
++++++++++++++++++++++++

.. py:currentmodule:: buildbot.reporters.message

This formatter can be used to generate arbitrary messages according to arbitrary calculations.
As opposed to :ref:`MessageFormatterRenderable`, more information is made available to this reporter.

.. py:class:: MessageFormatterFunction(function, template_type, want_properties=True, wantProperties=None, want_steps=False, wantSteps=None, wantLogs=None, want_logs=False, want_logs_content=False)

    :param callable function: A callable that will be called with a dictionary that contains ``build`` key with the value that contains the build dictionary as received from the data API.
    :param string template_type: either ``plain``, ``html`` or ``json`` depending on the output of the formatter.
        JSON output must not be encoded.
    :param boolean want_properties: include 'properties' in the build dictionary
    :param boolean wantProperties: deprecated, use ``want_properties`` instead
    :param boolean want_steps: include 'steps' in the build dictionary
    :param boolean wantSteps: deprecated, use ``want_steps`` instead
    :param boolean wantLogs: deprecated, use ``want_logs`` and ``want_logs_content`` set to the same value.
    :param boolean want_logs: include 'logs' in the steps dictionaries.
        This implies `wantSteps=True`.
        This includes only log metadata, for content use ``want_logs_content``.
    :param boolean want_logs_content: include logs content in the logs dictionaries.
        This implies `want_logs=True` and `wantSteps=True`.
        This dumps the *full* content of logs and may consume lots of memory and CPU depending on the log size.
