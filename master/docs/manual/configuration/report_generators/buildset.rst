.. bb:reportgen:: BuildSetStatusGenerator

.. _Reportgen-BuildSetStatusGenerator:

BuildSetStatusGenerator
+++++++++++++++++++++++

.. py:class:: buildbot.reporters.BuildSetStatusGenerator

This report generator sends a message about builds in a buildset.
It is very similar to :bb:reportgen:`BuildStatusGenerator` but sends single message about all builds in a buildset, not individual builds.

The following parameters are supported:

``subject``
    (string, optional).

    Deprecated since Buildbot 3.5.
    Please use the ``subject`` argument of the ``message_formatter`` passed to the generator.

    A string to be used as the subject line of the message.
    ``%(builder)s`` will be replaced with the name of the builder which provoked the message.
    ``%(result)s`` will be replaced with the name of the result of the build.
    ``%(title)s`` and ``%(projectName)s`` will be replaced with the title of the Buildbot instance.

``mode``
    (list of strings or a string, optional).
    Defines the cases when a message should be sent.
    Only information about builds that matched the ``mode`` will be included.
    There are two strings which can be used as shortcuts instead of the full lists.

    The possible shortcuts are:

    ``all``
        Send message for all cases.
        Equivalent to ``('change', 'failing', 'passing', 'problem', 'warnings', 'exception')``.

    ``warnings``
        Equivalent to ``('warnings', 'failing')``.

    If the argument is list of strings, it must be a combination of:

    ``cancelled``
        Include builds which were cancelled.

    ``change``
        Include builds which change status.

    ``failing``
        Include builds which fail.

    ``passing``
        Include builds which succeed.

    ``problem``
        Include a build which failed when the previous build has passed.

    ``warnings``
        Include builds which generate warnings.

    ``exception``
        Include builds which generate exceptions.

    Defaults to ``('failing', 'passing', 'warnings')``.

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

``message_formatter``
    (optional, instance of ``reporters.MessageFormatter``)
    This is an optional instance of the ``reporters.MessageFormatter`` class that can be used to generate a custom message.

