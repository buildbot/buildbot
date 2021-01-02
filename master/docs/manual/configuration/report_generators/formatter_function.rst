.. _MessageFormatterFunction:

MessageFormatterFunction
++++++++++++++++++++++++

.. py:currentmodule:: buildbot.reporters.message

This formatter can be used to generate arbitrary messages according to arbitrary calculations.
As opposed to :ref:`MessageFormatterRenderable`, more information is made available to this reporter.

.. py:class:: MessageFormatterFunction(function, template_type, wantProperties=True, wantSteps=False, wantLogs=False)

    :param callable function: A callable that will be called with a dictionary that contains ``build`` key with the value that contains the build dictionary as received from the data API.
    :param string template_type: either ``plain``, ``html`` or ``json`` depending on the output of the formatter.
        JSON output must not be encoded.
    :param boolean wantProperties: include 'properties' in the build dictionary
    :param boolean wantSteps: include 'steps' in the build dictionary
    :param boolean wantLogs: include 'logs' in the steps dictionaries.
        This needs wantSteps=True.
        This dumps the *full* content of logs and may consume lots of memory and CPU depending on the log size.
