.. _MessageFormatter:

MessageFormatter
++++++++++++++++

.. py:currentmodule:: buildbot.reporters.message

This formatter is used to format messages in :ref:`Reportgen-BuildStatusGenerator` and :ref:`Reportgen-BuildSetStatusGenerator`.

It formats a message using the Jinja2_ templating language and picks the template either from a string or from a file.

The constructor of the class takes the following arguments:

``template_dir``
    The directory that is used to look for the various templates.

``template_filename``
    This is the name of the file in the ``template_dir`` directory that will be used to generate the body of the mail.
    It defaults to ``default_mail.txt``.

``template``
    If this parameter is set, this parameter indicates the content of the template used to generate the body of the mail as string.

``template_type``
    This indicates the type of the generated template.
    Use either 'plain' (the default) or 'html'.

``subject_filename``
    This is the name of the file in the ``template_dir`` directory that contains the content of the subject of the mail.

``subject``
    Alternatively, this is the content of the subject of the mail as string.

``ctx``
    This is an extension of the standard context that will be given to the templates.
    Use this to add content to the templates that is otherwise not available.

    Alternatively, you can subclass MessageFormatter and override the :py:meth:`buildAdditionalContext` in order to grab more context from the data API.

    .. py:method:: buildAdditionalContext(master, ctx)
        :noindex:

        :param master: the master object
        :param ctx: the context dictionary to enhance
        :returns: optionally deferred

        default implementation will add ``self.ctx`` into the current template context

``wantProperties``
    This parameter (defaults to True) will extend the content of the given ``build`` object with the Properties from the build.

``wantSteps``
    This parameter (defaults to False) will extend the content of the given ``build`` object with information about the steps of the build.
    Use it only when necessary as this increases the overhead in term of CPU and memory on the master.

``wantLogs``
    This parameter (defaults to False) will extend the content of the steps of the given ``build`` object with the full Logs of each steps from the build.
    This requires ``wantSteps`` to be True.
    Use it only when mandatory as this increases the overhead in term of CPU and memory on the master greatly.

Context

The context that is given to the template consists of the following data:


The following table describes how to get some useful pieces of information from the various data objects:

Name of the builder that generated this event
    ``{{ buildername }}``

Title of the BuildMaster
    ``{{ projects }}``

MailNotifier mode
    ``{{ mode }}`` (a combination of ``change``, ``failing``, ``passing``, ``problem``, ``warnings``, ``exception``, ``all``)

URL to build page
    ``{{ build_url }}``

URL to Buildbot main page
    ``{{ buildbot_url }}``

Status of the build as string.
    This require extending the context of the Formatter via the ``ctx`` parameter with: ``ctx=dict(statuses=util.Results)``.

    ``{{ statuses[results] }}``

Build text
    ``{{ build['state_string'] }}``

Mapping of property names to (values, source)
    ``{{ build['properties'] }}``

For instance the build reason (from a forced build)
    ``{{ build['properties']['reason'][0] }}``

Worker name
    ``{{ workername }}``

List of responsible users
    ``{{ blamelist | join(', ') }}``

.. _Jinja2: http://jinja.pocoo.org/docs/dev/templates/
