.. _Report-Generators:

Report Generators
=================

.. toctree::
    :hidden:
    :maxdepth: 2

    build
    build_start_end
    buildset
    worker
    formatter
    formatter_function
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
 * :ref:`Reportgen-WorkerMissingGenerator`

The report generators may customize the reports using message formatters.
The following message formatter classes are provided:

 * :ref:`MessageFormatter` (used in ``BuildStatusGenerator``, ``BuildStartEndStatusGenerator`` and ``BuildSetStatusGenerator``)
 * :ref:`MessageFormatterRenderable` (used in ``BuildStatusGenerator`` and ``BuildStartEndStatusGenerator``)
 * :ref:`MessageFormatterFunction` (used in ``BuildStatusGenerator`` and ``BuildStartEndStatusGenerator``)
 * :ref:`MessageFormatterMissingWorkers` (used in ``WorkerMissingGenerator``)
