.. bb:reportgen:: BuildStartEndStatusGenerator

.. _Reportgen-BuildStartEndStatusGenerator:

BuildStartEndStatusGenerator
++++++++++++++++++++++++++++

.. py:class:: buildbot.plugins.reporters.BuildStartEndStatusGenerator

This report generator that sends a message both when a build starts and finishes.

The following parameters are supported:

``builders``
    (list of strings, optional).
    A list of builder names to serve build status information for.
    Defaults to ``None`` (all builds).
    Use either builders or tags, but not both.

``tags``
    (list of strings, optional).
    A list of tag names to serve build status information for.
    Defaults to ``None`` (all tags).
    Use either builders or tags, but not both.

``schedulers``
    (list of strings, optional).
    A list of scheduler names to serve build status information for.
    Defaults to ``None`` (all schedulers).

``branches``
    (list of strings, optional).
    A list of branch names to serve build status information for.
    Defaults to ``None`` (all branches).

``add_logs``
    (boolean or a list of strings, optional).
    If ``True``, include all build logs as attachments to the messages.
    These can be quite large.
    This can also be set to a list of log names to send a subset of the logs.
    Defaults to ``False``.

``add_patch``
    (boolean, optional).
    If ``True``, include the patch content if a patch was present.
    Patches are usually used on a :class:`Try` server.
    Defaults to ``False``.

``start_formatter``
    (optional, instance of ``reporters.MessageFormatter`` or ``reporters.MessageFormatterRenderable``)
    This is an optional message formatter that can be used to generate a custom message at the start of the build.

``end_formatter``
    (optional, instance of ``reporters.MessageFormatter`` or ``reporters.MessageFormatterRenderable``)
    This is an optional message formatter that can be used to generate a custom message at the end of the build.
