.. _MessageFormatterFunctionRaw:

MessageFormatterFunctionRaw
+++++++++++++++++++++++++++

.. py:currentmodule:: buildbot.reporters.message

This formatter can be used to generate arbitrary messages according to arbitrary calculations.

As opposed to :ref:`MessageFormatterFunction`, full message information can be customized.

The return value of the provided function must be a dictionary and is interpreted as follows:

 - ``body``. Body of the message. Most reporters require this to be a string. If not provided,
   ``None`` is used.

 - ``type``. Type of the message. Must be either ``plain``, ``html`` or ``json``. If not provided,
   ``"plain"`` is used.

 - ``subject``. Subject of the message. Must be a string. If not provided, ``None`` is used.

 - ``extra_info``. Extra information of the message. Must be either ``None`` or a dictionary
   of dictionaries with string keys in both root and child dictionaries. If not provided, ``None``
   is used.

.. py:class:: MessageFormatterFunctionRaw(function, want_properties=True, want_steps=False, want_logs=False, want_logs_content=False)

    :param callable function: A callable that will be called with a two arguments.

         - ``master``: An instance of ``BuildMaster``

         - ``ctx``: dictionary that contains the same context dictionary as :ref:`MessageFormatter`.

    :param boolean want_properties: include 'properties' in the build dictionary
    :param boolean want_steps: include 'steps' in the build dictionary
    :param boolean want_logs: include 'logs' in the steps dictionaries.
        This implies `want_steps=True`.
        This includes only log metadata, for content use ``want_logs_content``.
    :param want_logs_content: include logs content in the logs dictionaries.
        `False` disables log content inclusion. `True` enables log content inclusion for all logs.
        A list of strings specifies which logs to include. The logs can be included by name; or
        by step name and log name separated by dot character. If log name is specified, logs with
        that name will be included regardless of the step it is in. If both step and log names
        are specified, then logs with that name will be included only from the specific step.
        `want_logs_content` being not `False` implies `want_logs=True` and `want_steps=True`.
        Enabling `want_logs_content` dumps the *full* content of logs and may consume lots of
        memory and CPU depending on the log size.
    :type want_logs_content: boolean or list[str]
