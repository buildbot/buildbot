.. _Report-Generators:

Report Generators
=================

.. toctree::
    :hidden:
    :maxdepth: 2

    build
    buildset
    worker

Report generators abstract the conditions of when a message is sent by a :ref:`Reporter <Reporters>` and the content of the message.

Multiple report generators can be registered to a reporter.

At this moment, only the following reporters support report generators:

 * :bb:reporter:`BitbucketServerPRCommentPush`
 * :bb:reporter:`MailNotifier`
 * :bb:reporter:`PushjetNotifier`
 * :bb:reporter:`PushoverNotifier`

Eventually report generator support will be added to the rest of the reporters.

.. contents::
    :depth: 2
    :local:

The following reporter generators are available:

 * :ref:`Reportgen-BuildStatusGenerator`
 * :ref:`Reportgen-BuildSetStatusGenerator`
 * :ref:`Reportgen-WorkerMissingGenerator`
