.. _MessageFormatterMissingWorkers:

MessageFormatterMissingWorkers
++++++++++++++++++++++++++++++

.. py:currentmodule:: buildbot.reporters.message

This formatter is used to format messages in :ref:`Reportgen-WorkerMissingGenerator`.

It formats a message using the Jinja2_ templating language and picks the template either from a string or from a file.

The constructor to that class takes the same arguments as MessageFormatter, minus ``wantLogs``, ``want_logs``, ``want_logs_content``, ``wantProperties``, ``want_properties``, ``wantSteps``, ``want_steps``.

``template``
    The content of the template used to generate the body of the mail as string.

``template_type``
    This indicates the type of the generated template.
    Use either 'plain' (the default) or 'html'.

``subject``
    The content of the subject of the mail as string.


``ctx``
    This is an extension of the standard context that will be given to the templates.
    Use this to add content to the templates that is otherwise not available.

    Alternatively, you can subclass MessageFormatter and override the :py:meth:`buildAdditionalContext` in order to grab more context from the data API.

    .. py:method:: buildAdditionalContext(master, ctx)
        :noindex:

        :param master: the master object
        :param ctx: the context dictionary to enhance
        :returns: optionally deferred

        The default implementation will add ``self.ctx`` into the current template context


The default ``ctx`` for the missing worker email is made of:

``buildbot_title``
    The title of the Buildbot instance as per ``c['title']`` from the ``master.cfg``

``buildbot_url``
    The URL of the Buildbot instance as per ``c['buildbotURL']`` from the ``master.cfg``

``worker``
    The worker object as defined in the REST api plus two attributes:

    ``notify``
        List of emails to be notified for this worker.

    ``last_connection``
        String describing the approximate time of last connection for this worker.

.. _Jinja2: http://jinja.pocoo.org/docs/dev/templates/
