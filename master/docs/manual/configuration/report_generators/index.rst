.. _Report-Generators:

Report Generators
=================

.. toctree::
    :hidden:
    :maxdepth: 2

    build
    build_start_end
    buildset
    buildset_combined
    worker
    formatter
    formatter_function
    formatter_function_raw
    formatter_renderable
    formatter_missing_worker

Report generators abstract the conditions of when a message is sent by a :ref:`Reporter <Reporters>` and the content of the message.

Multiple report generators can be registered to a reporter.

At this moment, only the following reporters support report generators:

 * :bb:reporter:`BitbucketServerPRCommentPush`
 * :bb:reporter:`BitbucketStatusPush`
 * :bb:reporter:`GitHubStatusPush`
 * :bb:reporter:`GitHubCommentPush`
 * :bb:reporter:`GitLabStatusPush`
 * :bb:reporter:`HttpStatusPush`
 * :bb:reporter:`MailNotifier`
 * :bb:reporter:`PushjetNotifier`
 * :bb:reporter:`PushoverNotifier`

Eventually, report generator support will be added to the rest of the reporters as well.

.. contents::
    :depth: 2
    :local:

The following report generators are available:

 * :ref:`Reportgen-BuildStatusGenerator`
 * :ref:`Reportgen-BuildStartEndStatusGenerator`
 * :ref:`Reportgen-BuildSetStatusGenerator`
 * :ref:`Reportgen-BuildSetCombinedStatusGenerator`
 * :ref:`Reportgen-WorkerMissingGenerator`

The report generators may customize the reports using message formatters.
The following message formatter classes are provided:

 * :ref:`MessageFormatter` (commonly used in
   ``BuildStatusGenerator``,
   ``BuildStartEndStatusGenerator``,
   ``BuildSetCombinedStatusGenerator`` and
   ``BuildSetStatusGenerator``)
 * :ref:`MessageFormatterRenderable` (commonly used in ``BuildStatusGenerator`` and
   ``BuildStartEndStatusGenerator``)
 * :ref:`MessageFormatterFunction` (commonly used in ``BuildStatusGenerator`` and
   ``BuildStartEndStatusGenerator``)
 * :ref:`MessageFormatterFunctionRaw` (commonly used in
   ``BuildStatusGenerator``,
   ``BuildStartEndStatusGenerator``,
   ``BuildSetCombinedStatusGenerator`` and
   ``BuildSetStatusGenerator``)
 * :ref:`MessageFormatterMissingWorkers` (commonly used in ``WorkerMissingGenerator``)

Message formatters produce the following information that is later used by the report generators:

 - Message type: ``plain`` (text), ``html`` or ``json``.

 - Message body: a string that describes the information about build or buildset. Other data types
   are supported too, but then the interpretation of data depends on actual reporter that is being
   used.

 - Message subject: an optional title of the message about build or buildset.

 - Extra information: optional dictionary of dictionaries with any extra information to give to
   the reporter. Interpretation of the data depends on the reporter that is being used.

