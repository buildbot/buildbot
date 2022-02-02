.. _MessageFormatter:

MessageFormatter
++++++++++++++++

.. py:currentmodule:: buildbot.reporters.message

This formatter is used to format messages in :ref:`Reportgen-BuildStatusGenerator` and :ref:`Reportgen-BuildSetStatusGenerator`.

It formats a message using the Jinja2_ templating language and picks the template either from a string.

The constructor of the class takes the following arguments:

``template_type``
    This indicates the type of the generated template.
    Use either 'plain' (the default) or 'html'.

``template``
    If set, specifies the template used to generate the message body.
    If not set, a default template will be used.
    The default template is selected according to ``template_type`` so it may make sense to specify appropriate ``template_type`` even if the default template is used.

``subject``
    If set, specifies the template used to generate the message subject.
    In case of messages generated for multiple builds within a buildset (e.g. from within ``BuildSetStatusGenerator``), the subject of the first message will be used.
    The ``is_buildset`` key of the context can be used to detect such case and adjust the message appropriately.

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

``want_properties``
    This parameter (defaults to True) will extend the content of the given ``build`` object with the Properties from the build.

``wantProperties``
    Deprecated, use ``want_properties`` set to the same value.

``want_steps``
    This parameter (defaults to False) will extend the content of the given ``build`` object with information about the steps of the build.
    Use it only when necessary as this increases the overhead in terms of CPU and memory on the master.

``wantSteps``
    Deprecated, use ``want_steps`` set to the same value.

``wantLogs``
    Deprecated, use ``want_logs`` and ``want_logs_content`` set to the same value.

``want_logs``
    This parameter (defaults to False) will extend the content of the steps of the given ``build`` object with the log metadata of each steps from the build.
    This implies ``wantSteps`` to be `True`.
    Use it only when mandatory, as this greatly increases the overhead in terms of CPU and memory on the master.

``want_logs_content``
    This parameter (defaults to False) will extend the content of the logs with the log contents of each steps from the build.
    This implies ``want_logs`` and ``wantSteps`` to be `True`.
    Use it only when mandatory, as this greatly increases the overhead in terms of CPU and memory on the master.

Context
~~~~~~~

The context that is given to the template consists of the following data:

``results``
    The results of the build as an integer.
    Equivalent to ``build['results']``.

``result_names``
    A collection that allows accessing a textual identifier of build result.
    The intended usage is ``result_names[results]``.

    The following are possible values: ``success``, ``warnings``, ``failure``, ``skipped``, ``exception``, ``retry``, ``cancelled``.

``buildername``
    The name of the builder.
    Equivalent to ``build['builder']['name']``

``mode``
    The mode argument that has been passed to the report generator.

``workername``
    The name of the worker.
    Equivalent to the ``workername`` property of the build or ``<unknown>`` if it's not available.

``buildset``
    The :bb:rtype:`buildset` dictionary from data API.

``build``
    The :bb:rtype:`build` dictionary from data API.
    The ``properties`` attribute is populated only if ``want_properties`` is set to ``True``.
    It has the following extra properties:

    ``builder``
        The :bb:rtype:`builder` dictionary from the data API that describes the builder of the build.

    ``buildrequest``
        The :bb:rtype:`buildrequest` dictionary from the data API that describes the build request that the build was built for.

    ``buildset``
        The :bb:rtype:`buildset` dictionary from the data API that describes the buildset that the build was built for.

    ``parentbuild``
        The :bb:rtype:`build` dictionary from the data API that describes the parent build.
        This build is identified by the ``parent_buildid`` attribute of the buildset.

    ``parentbuilder``
        The :bb:rtype:`builder` dictionary from the data API that describes the builder of the parent build.

    ``url``
        URL to the build in the Buildbot UI.

    ``prev_build``
        The :bb:rtype:`build` dictionary from the data API that describes previous build, if any.
        This attribute is populated only if ``wantPreviousBuild`` is set to ``True``.

    ``steps``
        A list of :bb:rtype:`step` dictionaries from the data API that describe steps in the build, if any.
        This attribute is populated only if ``wantSteps`` is set to ``True``.

        Additionally, if ``want_logs`` is set to ``True`` then the step dictionaries will contain ``logs`` attribute with a list of :bb:rtype:`log` dictionaries from the data API that describe the logs of the step.
        The log dictionaries will additionally contain ``url`` key with URL to the log in the web UI as the value.

        Additionally, if ``want_logs_content`` is set to ``True`` then the log dictionaries will contain ``contents`` key with full contents of the log.

``is_buildset``
    A boolean identifying whether the current message will form a larger message that describes multiple builds in a buildset.
    This mostly concerns generation of the subject as the message bodies will be merged.

``projects``
    A string identifying the projects that the build was built for.

``previous_results``
    Results of the previous build, if available, otherwise ``None``.

``status_detected``
    String that describes the build in terms of current build results, previous build results and ``mode``.

``build_url``
    URL to the build in the Buildbot UI.

``buildbot_title``
    The title of the Buildbot instance as per ``c['title']`` from the ``master.cfg``

``buildbot_url``
    The URL of the Buildbot instance as per ``c['buildbotURL']`` from the ``master.cfg``

``blamelist``
    The list of users responsible for the build.

``summary``
    A string that summarizes the build result.

``sourcestamps``
    A string identifying the source stamps for which the build was made.

Examples
~~~~~~~~

The following examples describe how to get some useful pieces of information from the various data objects:

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
