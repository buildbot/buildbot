.. bb:cfg:: reporter

.. _Reporters:

Reporters
---------


.. contents::
    :depth: 2
    :local:

The Buildmaster has a variety of ways to present build status to various users.
Each such delivery method is a `Reporter Target` object in the configuration's ``services`` list.
To add reporter targets, you just append more objects to this list::

    c['services'] = []

    m = reporters.MailNotifier(fromaddr="buildbot@localhost",
                               extraRecipients=["builds@lists.example.com"],
                               sendToInterestedUsers=False)
    c['services'].append(m)

    c['services'].append(reporters.IRC(host="irc.example.com", nick="bb",
                                      channels=[{"channel": "#example1"},
                                                {"channel": "#example2",
                                                 "password": "somesecretpassword"}]))

Most reporter objects take a ``tags=`` argument, which can contain a list of tag names: in this case, it will only show status for Builders that contains the named tags.

.. note:: Implementation Note

    Each of these objects should be a :class:`service.BuildbotService` which will be attached to the BuildMaster object when the configuration is processed.

The remainder of this section describes each built-in reporters.
A full list of reporters is available in the :bb:index:`reporter`.

.. bb:reporter:: MailNotifier

.. index:: single: email; MailNotifier

MailNotifier
~~~~~~~~~~~~

.. py:class:: buildbot.reporters.mail.MailNotifier

The Buildbot can send email when builds finish.
The most common use of this is to tell developers when their change has caused the build to fail.
It is also quite common to send a message to a mailing list (usually named `builds` or similar) about every build.

The :class:`MailNotifier` reporter is used to accomplish this.
You configure it by specifying who mail should be sent to, under what circumstances mail should be sent, and how to deliver the mail.
It can be configured to only send out mail for certain builders, and only send messages when the build fails, or when the builder transitions from success to failure.
It can also be configured to include various build logs in each message.

If a proper lookup function is configured, the message will be sent to the "interested users" list (:ref:`Doing-Things-With-Users`), which includes all developers who made changes in the build.
By default, however, Buildbot does not know how to construct an email addressed based on the information from the version control system.
See the ``lookup`` argument, below, for more information.

You can add additional, statically-configured, recipients with the ``extraRecipients`` argument.
You can also add interested users by setting the ``owners`` build property to a list of users in the scheduler constructor (:ref:`Configuring-Schedulers`).

Each :class:`MailNotifier` sends mail to a single set of recipients.
To send different kinds of mail to different recipients, use multiple :class:`MailNotifier`\s.
TODO: or subclass MailNotifier and override getRecipients()


The following simple example will send an email upon the completion of each build, to just those developers whose :class:`Change`\s were included in the build.
The email contains a description of the :class:`Build`, its results, and URLs where more information can be obtained.

::

    from buildbot.plugins import reporters
    mn = reporters.MailNotifier(fromaddr="buildbot@example.org",
                                lookup="example.org")
    c['services'].append(mn)

To get a simple one-message-per-build (say, for a mailing list), use the following form instead.
This form does not send mail to individual developers (and thus does not need the ``lookup=`` argument, explained below), instead it only ever sends mail to the `extra recipients` named in the arguments::

    mn = reporters.MailNotifier(fromaddr="buildbot@example.org",
                                sendToInterestedUsers=False,
                                extraRecipients=['listaddr@example.org'])

If your SMTP host requires authentication before it allows you to send emails, this can also be done by specifying ``smtpUser`` and ``smtpPassword``::

    mn = reporters.MailNotifier(fromaddr="myuser@example.com",
                                sendToInterestedUsers=False,
                                extraRecipients=["listaddr@example.org"],
                                relayhost="smtp.example.com", smtpPort=587,
                                smtpUser="myuser@example.com",
                                smtpPassword="mypassword")

.. note::

   If for some reasons you are not able to send a notification with TLS enabled and specified user name and password, you might want to use :contrib-src:`master/contrib/check_smtp.py` to see if it works at all.

If you want to require Transport Layer Security (TLS), then you can also set ``useTls``::

    mn = reporters.MailNotifier(fromaddr="myuser@example.com",
                                sendToInterestedUsers=False,
                                extraRecipients=["listaddr@example.org"],
                                useTls=True, relayhost="smtp.example.com",
                                smtpPort=587, smtpUser="myuser@example.com",
                                smtpPassword="mypassword")

.. note::

   If you see ``twisted.mail.smtp.TLSRequiredError`` exceptions in the log while using TLS, this can be due *either* to the server not supporting TLS or to a missing `PyOpenSSL`_ package on the BuildMaster system.

In some cases it is desirable to have different information then what is provided in a standard MailNotifier message.
For this purpose MailNotifier provides the argument ``messageFormatter`` (an instance of ``MessageFormatter``) which allows for the creation of messages with unique content.

For example, if only short emails are desired (e.g., for delivery to phones)::

    from buildbot.plugins import reporters
    mn = reporters.MailNotifier(fromaddr="buildbot@example.org",
                                sendToInterestedUsers=False,
                                mode=('problem',),
                                extraRecipients=['listaddr@example.org'],
                                messageFormatter=reporters.MessageFormatter(template="STATUS: {{ summary }}"))

Another example of a function delivering a customized html email is given below::

    from buildbot.plugins import reporters

    template=u'''\
    <h4>Build status: {{ summary }}</h4>
    <p> Worker used: {{ workername }}</p>
    {% for step in build['steps'] %}
    <p> {{ step['name'] }}: {{ step['result'] }}</p>
    {% endfor %}
    <p><b> -- The Buildbot</b></p>
    '''

    mn = reporters.MailNotifier(fromaddr="buildbot@example.org",
                                sendToInterestedUsers=False,
                                mode=('failing',),
                                extraRecipients=['listaddr@example.org'],
                                messageFormatter=reporters.MessageFormatter(
                                    template=template, template_type='html',
                                    wantProperties=True, wantSteps=True))

.. _PyOpenSSL: http://pyopenssl.sourceforge.net/

MailNotifier arguments
++++++++++++++++++++++

``fromaddr``
    The email address to be used in the 'From' header.

``sendToInterestedUsers``
    (boolean).
    If ``True`` (the default), send mail to all of the Interested Users.
    If ``False``, only send mail to the ``extraRecipients`` list.

``extraRecipients``
    (list of strings).
    A list of email addresses to which messages should be sent (in addition to the InterestedUsers list, which includes any developers who made :class:`Change`\s that went into this build).
    It is a good idea to create a small mailing list and deliver to that, then let subscribers come and go as they please.

``subject``
    (string).
    A string to be used as the subject line of the message.
    ``%(builder)s`` will be replaced with the name of the builder which provoked the message.

``mode``
    Mode is a list of strings; however there are two strings which can be used as shortcuts instead of the full lists.
    The possible shortcuts are:

    ``all``
        Always send mail about builds.
        Equivalent to (``change``, ``failing``, ``passing``, ``problem``, ``warnings``, ``exception``).

    ``warnings``
        Equivalent to (``warnings``, ``failing``).

    Set these shortcuts as actual strings in the configuration::

        from buildbot.plugins import reporters
        mn = reporters.MailNotifier(fromaddr="buildbot@example.org",
                                    mode="warnings")
        c['services'].append(mn)

    (list of strings).
    A combination of:

    ``cancelled``
        Send mail about builds which were cancelled.

    ``change``
        Send mail about builds which change status.

    ``failing``
        Send mail about builds which fail.

    ``passing``
        Send mail about builds which succeed.

    ``problem``
        Send mail about a build which failed when the previous build has passed.

    ``warnings``
        Send mail about builds which generate warnings.

    ``exception``
        Send mail about builds which generate exceptions.

    Defaults to (``failing``, ``passing``, ``warnings``).

``builders``
    (list of strings).
    A list of builder names for which mail should be sent.
    Defaults to ``None`` (send mail for all builds).
    Use either builders or tags, but not both.

``tags``
    (list of strings).
    A list of tag names to serve status information for.
    Defaults to ``None`` (all tags).
    Use either builders or tags, but not both.

``schedulers``
    (list of strings).
    A list of scheduler names to serve status information for.
    Defaults to ``None`` (all schedulers).

``branches``
    (list of strings).
    A list of branch names to serve status information for.
    Defaults to ``None`` (all branches).

``addLogs``
    (boolean).
    If ``True``, include all build logs as attachments to the messages.
    These can be quite large.
    This can also be set to a list of log names, to send a subset of the logs.
    Defaults to ``False``.

``addPatch``
    (boolean).
    If ``True``, include the patch content if a patch was present.
    Patches are usually used on a :class:`Try` server.
    Defaults to ``True``.

``buildSetSummary``
    (boolean).
    If ``True``, send a single summary email consisting of the concatenation of all build completion messages rather than a completion message for each build.
    Defaults to ``False``.

``relayhost``
    (string).
    The host to which the outbound SMTP connection should be made.
    Defaults to 'localhost'

``smtpPort``
    (int).
    The port that will be used on outbound SMTP connections.
    Defaults to 25.

``useTls``
    (boolean).
    When this argument is ``True`` (default is ``False``) ``MailNotifier`` requires that STARTTLS encryption is used for the connection with the ``relayhost``.
    Authentication is required for STARTTLS so the arguments ``smtpUser`` and ``smtpPassword`` must also be specified.

``useSmtps``
    (boolean).
    When this argument is ``True`` (default is ``False``) ``MailNotifier`` connects to ``relayhost`` over an encrypted SSL/TLS connection.
    This configuration is typically used over port 465.

``smtpUser``
    (string).
    The user name to use when authenticating with the ``relayhost``.
    Can be a :ref:`Secret`.

``smtpPassword``
    (string).
    The password that will be used when authenticating with the ``relayhost``.
    Can be a :ref:`Secret`.

``lookup``
    (implementer of :class:`IEmailLookup`).
    Object which provides :class:`IEmailLookup`, which is responsible for mapping User names (which come from the VC system) into valid email addresses.

    If the argument is not provided, the ``MailNotifier`` will attempt to build the ``sendToInterestedUsers`` from the authors of the Changes that led to the Build via :ref:`User-Objects`.
    If the author of one of the Build's Changes has an email address stored, it will added to the recipients list.
    With this method, ``owners`` are still added to the recipients.
    Note that, in the current implementation of user objects, email addresses are not stored; as a result, unless you have specifically added email addresses to the user database, this functionality is unlikely to actually send any emails.

    Most of the time you can use a simple Domain instance.
    As a shortcut, you can pass as string: this will be treated as if you had provided ``Domain(str)``.
    For example, ``lookup='example.com'`` will allow mail to be sent to all developers whose SVN usernames match their ``example.com`` account names.
    See :src:`master/buildbot/reporters/mail.py` for more details.

    Regardless of the setting of ``lookup``, ``MailNotifier`` will also send mail to addresses in the ``extraRecipients`` list.

``messageFormatter``
    This is an optional instance of the ``reporters.MessageFormatter`` class that can be used to generate a custom mail message.
    This class uses the Jinja2_ templating language to generate the body and optionally the subject of the mails.
    Templates can either be given inline (as string), or read from the filesystem.

``extraHeaders``
    (dictionary).
    A dictionary containing key/value pairs of extra headers to add to sent e-mails.
    Both the keys and the values may be a `Interpolate` instance.

``watchedWorkers``
    This is a list of names of workers, which should be watched. In case a worker get missing, a notification is sent.
    The value of ``watchedWorkers`` can also be set to *all* (default) or ``None``. You also need to specify email address to which the notification is sent in the worker configuration.

``messageFormatterMissingWorker``
    This is an optional instance of the ``reporters.messageFormatterMissingWorker`` class that can be used to generate a custom mail message for missing workers.
    This class uses the Jinja2_ templating language to generate the body and optionally the subject of the mails.
    Templates can either be given inline (as string), or read from the filesystem.


MessageFormatter arguments
++++++++++++++++++++++++++

The easiest way to use the ``messageFormatter`` parameter is to create a new instance of the ``reporters.MessageFormatter`` class.
The constructor to that class takes the following arguments:

``template_dir``
    This is the directory that is used to look for the various templates.

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


As a help to those writing Jinja2 templates the following table describes how to get some useful pieces of information from the various data objects:

Name of the builder that generated this event
    ``{{ buildername }}``

Title of the BuildMaster
    ``{{ projects }}``

MailNotifier mode
    ``{{ mode }}`` (a combination of ``change``, ``failing``, ``passing``, ``problem``, ``warnings``, ``exception``, ``all``)

URL to build page
    ``{{ build_url }}``

URL to buildbot main page
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


MessageFormatterMissingWorkers arguments
++++++++++++++++++++++++++++++++++++++++
The easiest way to use the ``messageFormatterMissingWorkers`` parameter is to create a new instance of the ``reporters.MessageFormatterMissingWorkers`` class.

The constructor to that class takes the same arguments as MessageFormatter, minus ``wantLogs``, ``wantProperties``, ``wantSteps``.

The default ``ctx`` for the missing worker email is made of:

``buildbot_title``
    The buildbot title as per ``c['title']`` from the ``master.cfg``

``buildbot_url``
    The buildbot title as per ``c['title']`` from the ``master.cfg``

``worker``
    The worker object as defined in the REST api plus two attributes:

    ``notify``
        List of emails to be notified for this worker.

    ``last_connection``
        String describing the approximate the time of last connection for this worker.

.. _Jinja2: http://jinja.pocoo.org/docs/dev/templates/


.. bb:reporter:: PushoverNotifier

.. index:: Pushover

Pushover Notifications
~~~~~~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.reporters.pushover.PushoverNotifier

Apart of sending mail, Buildbot can send Pushover_ notifications. It can be used by administrators to receive an instant message to an iPhone or an Android device if a build fails. The :class:`PushoverNotifier` reporter is used to accomplish this. Its configuration is very similar to the mail notifications, however—due to the notification size constrains—the logs and patches cannot be attached.

To use this reporter, you need to generate and application on the Pushover website https://pushover.net/apps/ and provide your user key and the API token.

The following simple example will send a Pushover notification upon the completion of each build.
The notification contains a description of the :class:`Build`, its results, and URLs where more information can be obtained. The ``user_key`` and ``api_token`` values should be replaced with proper ones obtained from the Pushover website for your application.

::

    from buildbot.plugins import reporters
    pn = reporters.PushoverNotifier(user_key="1234", api_token='abcd')
    c['services'].append(pn)


This notifier supports parameters ``subject``, ``mode``, ``builders``, ``tags``, ``schedulers``, ``branches``, ``buildSetSummary``, ``messageFormatter``, ``watchedWorkers``, and ``messageFormatterMissingWorker`` from the :bb:reporter:`mail notifier <MailNotifier>`. See above for their explanation.
However, ``watchedWorkers`` defaults to *None*.

The following additional parameters are accepted by this class:

``user_key``
    The user key from the Pushover website. It is used to identify the notification recipient.
    Can be a :ref:`Secret`.

``api_token``
    API token for a custom application from the Pushover website.
    Can be a :ref:`Secret`.

``priorities``
    Dictionary of Pushover notification priorities. The keys of the dictionary can be ``change``, ``failing``, ``passing``, ``warnings``, ``exception`` and are equivalent to the ``mode`` strings. The values are integers between -2...2, specifying notification priority. In case a mode is missing from this dictionary, the default value of 0 is used.

``otherParams``
    Other parameters send to Pushover API. Check https://pushover.net/api/ for their list.

.. _Pushover: https://pushover.net/


.. bb:reporter:: PushjetNotifier

.. index:: Pushjet

Pushjet Notifications
~~~~~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.reporters.pushover.PushjetNotifier

Pushjet_ is another instant notification service, similar to :bb:reporter:`Pushover <PushoverNotifier>`.
To use this reporter, you need to generate a Pushjet service and provide its secret.

The parameters ``subject``, ``mode``, ``builders``, ``tags``, ``schedulers``, ``branches``, ``buildSetSummary``, ``messageFormatter``, ``watchedWorkers``, and ``messageFormatterMissingWorker`` are common with :bb:reporter:`mail <MailNotifier>` and :bb:reporter:`Pushover <PushoverNotifier>` notifier.

The Pushjet specific parameters are:

``secret``
    This is a secret token for your Pushjet service. See http://docs.pushjet.io/docs/creating-a-new-service to learn how to create a new Pushjet service and get its secret token.
    Can be a :ref:`Secret`.

``levels``
    Dictionary of Pushjet notification levels. The keys of the dictionary can be ``change``, ``failing``, ``passing``, ``warnings``, ``exception`` and are equivalent to the ``mode`` strings. The values are integers between 0...5, specifying notification priority. In case a mode is missing from this dictionary, the default value set by Pushover is used.

``base_url``
    Base URL for custom Pushjet instances. Defaults to https://api.pushjet.io.

.. _Pushjet: https://pushjet.io/


.. bb:reporter:: IRC

.. index:: IRC

IRC Bot
~~~~~~~


The :bb:reporter:`IRC` reporter creates an IRC bot which will attach to certain channels and be available for status queries.
It can also be asked to announce builds as they occur, or be told to shut up.

The IRC Bot in buildbot nine, is mostly a rewrite, and not all functionality has been ported yet.
Patches are very welcome for restoring the full functionality.

.. note:: Security Note

    Please note that any user having access to your irc channel or can PM the bot will be able to create or stop builds :bug:`3377`.



::

    from buildbot.plugins import reporters
    irc = reporters.IRC("irc.example.org", "botnickname",
                     useColors=False,
                     channels=[{"channel": "#example1"},
                               {"channel": "#example2",
                                "password": "somesecretpassword"}],
                     password="mysecretnickservpassword",
                     notify_events={
                       'exception': 1,
                       'successToFailure': 1,
                       'failureToSuccess': 1,
                     })
    c['services'].append(irc)

The following parameters are accepted by this class:

``host``
    (mandatory)
    The IRC server address to connect to.

``nick``
    (mandatory)
    The name this bot will use on the IRC server.

``channels``
    (mandatory)
    This is a list of channels to join on the IRC server.
    Each channel can be a string (e.g. ``#buildbot``), or a dictionary ``{'channel': '#buildbot', 'password': 'secret'}`` if each channel requires a different password.
    A global password can be set with the ``password`` parameter.

``pm_to_nicks``
    (optional)
    This is a list of person to contact on the IRC server.

``port``
    (optional, default to 6667)
    The port to connect to on the IRC server.

``allowForce``
    (optional, disabled by default)
    This allow user to force builds via this bot.

``tags``
    (optional)
    When set, this bot will only communicate about builders containing those tags.
    (tags functionality is not yet ported)

``password``
    (optional)
    The global password used to register the bot to the IRC server.
    If provided, it will be sent to Nickserv to claim the nickname: some IRC servers will not allow clients to send private messages until they have logged in with a password.
    Can be a :ref:`Secret`.

``notify_events``
    (optional)
    A dictionary of events to be notified on the IRC channels.
    At the moment, irc bot can listen to build 'start' and 'finish' events.
    This parameter can be changed during run-time by sending the ``notify`` command to the bot.

``noticeOnChannel``
   (optional, disabled by default)
   Whether to send notices rather than messages when communicating with a channel.

``showBlameList``
    (optional, disabled by default)
    Whether or not to display the blame list for failed builds.
    (blame list functionality is not ported yet)

``useRevisions``
    (optional, disabled by default)
    Whether or not to display the revision leading to the build the messages are about.
    (useRevisions functionality is not ported yet)

``useSSL``
    (optional, disabled by default)
    Whether or not to use SSL when connecting to the IRC server.
    Note that this option requires `PyOpenSSL`_.

``lostDelay``
    (optional)
    Delay to wait before reconnecting to the server when the connection has been lost.

``failedDelay``
    (optional)
    Delay to wait before reconnecting to the IRC server when the connection failed.

``useColors``
    (optional, enabled by default)
    The bot can add color to some of its messages.
    You might turn it off by setting this parameter to ``False``.

``allowShutdown``
    (optional, disabled by default)
    This allow users to shutdown the master.


To use the service, you address messages at the Buildbot, either normally (``botnickname: status``) or with private messages (``/msg botnickname status``).
The Buildbot will respond in kind.

If you issue a command that is currently not available, the Buildbot will respond with an error message.
If the ``noticeOnChannel=True`` option was used, error messages will be sent as channel notices instead of messaging.

Some of the commands currently available:

``list builders``
    Emit a list of all configured builders

:samp:`status {BUILDER}`
    Announce the status of a specific Builder: what it is doing right now.

``status all``
    Announce the status of all Builders

:samp:`watch {BUILDER}`
    If the given :class:`Builder` is currently running, wait until the :class:`Build` is finished and then announce the results.

:samp:`last {BUILDER}`
    Return the results of the last build to run on the given :class:`Builder`.

:samp:`join {CHANNEL}`
    Join the given IRC channel

:samp:`leave {CHANNEL}`
    Leave the given IRC channel

:samp:`notify on|off|list {EVENT}`
    Report events relating to builds.
    If the command is issued as a private message, then the report will be sent back as a private message to the user who issued the command.
    Otherwise, the report will be sent to the channel.
    Available events to be notified are:

    ``started``
        A build has started

    ``finished``
        A build has finished

    ``success``
        A build finished successfully

    ``failure``
        A build failed

    ``exception``
        A build generated and exception

    ``xToY``
        The previous build was x, but this one is Y, where x and Y are each one of success, warnings, failure, exception (except Y is capitalized).
        For example: ``successToFailure`` will notify if the previous build was successful, but this one failed

:samp:`help {COMMAND}`
    Describe a command.
    Use :command:`help commands` to get a list of known commands.

:samp:`shutdown {ARG}`
    Control the shutdown process of the Buildbot master.
    Available arguments are:

    ``check``
        Check if the Buildbot master is running or shutting down

    ``start``
        Start clean shutdown

    ``stop``
        Stop clean shutdown

    ``now``
        Shutdown immediately without waiting for the builders to finish

``source``
    Announce the URL of the Buildbot's home page.

``version``
    Announce the version of this Buildbot.

Additionally, the config file may specify default notification options as shown in the example earlier.

If the ``allowForce=True`` option was used, some additional commands will be available:

.. index:: Properties; from forced build

:samp:`force build [--codebase={CODEBASE}] [--branch={BRANCH}] [--revision={REVISION}] [--props=PROP1=VAL1,PROP2=VAL2...] {BUILDER} {REASON}`
    Tell the given :class:`Builder` to start a build of the latest code.
    The user requesting the build and *REASON* are recorded in the :class:`Build` status.
    The Buildbot will announce the build's status when it finishes.The user can specify a branch and/or revision with the optional parameters :samp:`--branch={BRANCH}` and :samp:`--revision={REVISION}`.
    The user can also give a list of properties with :samp:`--props={PROP1=VAL1,PROP2=VAL2..}`.

:samp:`stop build {BUILDER} {REASON}`
    Terminate any running build in the given :class:`Builder`.
    *REASON* will be added to the build status to explain why it was stopped.
    You might use this if you committed a bug, corrected it right away, and don't want to wait for the first build (which is destined to fail) to complete before starting the second (hopefully fixed) build.

If the `tags` is set (see the tags option in :ref:`Builder-Configuration`) changes related to only builders belonging to those tags of builders will be sent to the channel.

If the `useRevisions` option is set to `True`, the IRC bot will send status messages that replace the build number with a list of revisions that are contained in that build.
So instead of seeing `build #253 of ...`, you would see something like `build containing revisions [a87b2c4]`.
Revisions that are stored as hashes are shortened to 7 characters in length, as multiple revisions can be contained in one build and may exceed the IRC message length limit.

Two additional arguments can be set to control how fast the IRC bot tries to reconnect when it encounters connection issues.
``lostDelay`` is the number of seconds the bot will wait to reconnect when the connection is lost, where as ``failedDelay`` is the number of seconds until the bot tries to reconnect when the connection failed.
``lostDelay`` defaults to a random number between 1 and 5, while ``failedDelay`` defaults to a random one between 45 and 60.
Setting random defaults like this means multiple IRC bots are less likely to deny each other by flooding the server.


.. bb:reporter:: GerritStatusPush

GerritStatusPush
~~~~~~~~~~~~~~~~

.. py:class:: buildbot.status.status_gerrit.GerritStatusPush

:class:`GerritStatusPush` sends review of the :class:`Change` back to the Gerrit server, optionally also sending a message when a build is started.
GerritStatusPush can send a separate review for each build that completes, or a single review summarizing the results for all of the builds.

.. py:class:: GerritStatusPush(server, username, reviewCB, startCB, port, reviewArg, startArg, summaryCB, summaryArg, identity_file, builders, notify...)

   :param string server: Gerrit SSH server's address to use for push event notifications.
   :param string username: Gerrit SSH server's username.
   :param identity_file: (optional) Gerrit SSH identity file.
   :param int port: (optional) Gerrit SSH server's port (default: 29418)
   :param reviewCB: (optional) Called each time a build finishes. Build properties are available. Can be a deferred.
   :param reviewArg: (optional) argument passed to the review callback.

                    If :py:func:`reviewCB` callback is specified, it must return a message and optionally labels. If no message is specified, nothing will be sent to Gerrit.
                    It should return a dictionary:

                    .. code-block:: python

                        {'message': message,
                         'labels': {label-name: label-score,
                                    ...}
                        }

                    For example:

                    .. literalinclude:: /examples/git_gerrit.cfg
                       :pyobject: gerritReviewCB
                       :language: python

                    Which require an extra import in the config:

                    .. code-block:: python

                       from buildbot.plugins import util

   :param startCB: (optional) Called each time a build is started. Build properties are available. Can be a deferred.
   :param startArg: (optional) argument passed to the start callback.

                    If :py:func:`startCB` is specified, it must return a message and optionally labels. If no message is specified, nothing will be sent to Gerrit.
                    It should return a dictionary:

                    .. code-block:: python

                        {'message': message,
                         'labels': {label-name: label-score,
                                    ...}
                        }

                    For example:

                    .. literalinclude:: /examples/git_gerrit.cfg
                       :pyobject: gerritStartCB
                       :language: python

   :param summaryCB: (optional) Called each time a buildset finishes. Each build in the buildset has properties available. Can be a deferred.
   :param summaryArg: (optional) argument passed to the summary callback.

                      If :py:func:`summaryCB` callback is specified, it must return a message and optionally labels. If no message is specified, nothing will be sent to Gerrit.
                      The message and labels should be a summary of all the builds within the buildset.
                      It should return a dictionary:

                      .. code-block:: python

                          {'message': message,
                           'labels': {label-name: label-score,
                                      ...}
                          }

                      For example:

                      .. literalinclude:: /examples/git_gerrit.cfg
                         :pyobject: gerritSummaryCB
                         :language: python

   :param builders: (optional) list of builders to send results for.
                    This method allows to filter results for a specific set of builder.
                    By default, or if builders is None, then no filtering is performed.
   :param notify: (optional) control who gets notified by Gerrit once the status is posted.
                  The possible values for `notify` can be found in your version of the
                  Gerrit documentation for the `gerrit review` command.

   :param wantSteps: (optional, defaults to False) Extends the given ``build`` object with information about steps of the build.
                     Use it only when necessary as this increases the overhead in term of CPU and memory on the master.

   :param wantLogs: (optional, default to False) Extends the steps of the given ``build`` object with the full logs of the build.
                    This requires ``wantSteps`` to be True.
                    Use it only when mandatory as this increases the overhead in term of CPU and memory on the master greatly.

.. note::

   By default, a single summary review is sent; that is, a default :py:func:`summaryCB` is provided, but no :py:func:`reviewCB` or :py:func:`startCB`.

.. note::

   If :py:func:`reviewCB` or :py:func:`summaryCB` do not return any labels, only a message will be pushed to the Gerrit server.

.. seealso::

   :src:`master/docs/examples/git_gerrit.cfg` and :src:`master/docs/examples/repo_gerrit.cfg` in the Buildbot distribution provide a full example setup of Git+Gerrit or Repo+Gerrit of :bb:reporter:`GerritStatusPush`.


.. bb:reporter:: HttpStatusPush

HttpStatusPush
~~~~~~~~~~~~~~

.. @cindex HttpStatusPush
.. @stindex buildbot.reporters.HttpStatusPush

::

    from buildbot.plugins import reporters
    sp = reporters.HttpStatusPush(serverUrl="http://example.com/submit")
    c['services'].append(sp)

:class:`HttpStatusPush` builds on :class:`StatusPush` and sends HTTP requests to ``serverUrl``, with all the items json-encoded.
It is useful to create a status front end outside of Buildbot for better scalability.

It requires either `txrequests`_ or `treq`_ to be installed to allow interaction with http server.

.. note::

   The json data object sent is completely different from the one that was generated by 0.8.x buildbot.
   It is indeed generated using data api.

.. py:class:: HttpStatusPush(serverUrl, user=None, password=None, auth=None, format_fn=None, builders=None, wantProperties=False, wantSteps=False, wantPreviousBuild=False, wantLogs=False)

    :param string serverUrl: the url where to do the http post
    :param string user: the BasicAuth user to post as
    :param string password: the BasicAuth user's password (can be a :ref:`Secret`).
    :param auth: the authentication method to use.
        Refer to the documentation of the requests library for more information.
    :param function format_fn: a function that takes the build as parameter and returns a dictionary to be pushed to the server (as json).
    :param list builders: only send update for specified builders
    :param boolean wantProperties: include 'properties' in the build dictionary
    :param boolean wantSteps: include 'steps' in the build dictionary
    :param boolean wantLogs: include 'logs' in the steps dictionaries.
        This needs wantSteps=True.
        This dumps the *full* content of logs and may consume lots of memory and CPU depending on the log size.
    :param boolean wantPreviousBuild: include 'prev_build' in the build dictionary

Json object spec
++++++++++++++++

The default json object sent is a build object augmented with some more data as follow.

.. code-block:: json

    {
        "url": "http://yourbot/path/to/build",
        "<build data api values>": "[...]",
        "buildset": "<buildset data api values>",
        "builder": "<builder data api values>",
        "buildrequest": "<buildrequest data api values>"
    }


If you want another format, don't hesitate to use the ``format_fn`` parameter to customize the payload.
The ``build`` parameter given to that function is of type :bb:rtype:`build`, optionally enhanced with properties, steps, and logs information.

.. _txrequests: https://pypi.python.org/pypi/txrequests
.. _treq: https://pypi.python.org/pypi/treq

.. bb:reporter:: GitHubStatusPush

GitHubStatusPush
~~~~~~~~~~~~~~~~


.. @cindex GitHubStatusPush
.. py:class:: buildbot.reporters.github.GitHubStatusPush

::

    from buildbot.plugins import reporters, util

    context = Interpolate("buildbot/%(prop:buildername)s")
    gs = reporters.GitHubStatusPush(token='githubAPIToken',
                                    context=context,
                                    startDescription='Build started.',
                                    endDescription='Build done.')
    factory = util.BuildFactory()
    buildbot_bbtools = util.BuilderConfig(
        name='builder-name',
        workernames=['worker1'],
        factory=factory)
    c['builders'].append(buildbot_bbtools)
    c['services'].append(gs)

:class:`GitHubStatusPush` publishes a build status using `GitHub Status API <http://developer.github.com/v3/repos/statuses>`_.

It requires `txrequests`_ package to allow interaction with GitHub REST API.

It is configured with at least a GitHub API token.

You can create a token from you own `GitHub - Profile - Applications - Register new application <https://github.com/settings/applications>`_ or use an external tool to generate one.

.. py:class:: GitHubStatusPush(token, startDescription=None, endDescription=None, context=None, baseURL=None, verbose=False, builders=None)

    :param string token: token used for authentication. (can be a :ref:`Secret`)
    :param rendereable string startDescription: Custom start message (default: 'Build started.')
    :param rendereable string endDescription: Custom end message (default: 'Build done.')
    :param rendereable string context: Passed to GitHub to differentiate between statuses.
        A static string can be passed or :class:`Interpolate` for dynamic substitution.
        The default context is `buildbot/%(prop:buildername)s`.
    :param string baseURL: specify the github api endpoint if you work with GitHub Enterprise
    :param boolean verbose: if True, logs a message for each successful status push
    :param list builders: only send update for specified builders

.. bb:reporter:: GitHubCommentPush

GitHubCommentPush
~~~~~~~~~~~~~~~~~


.. @cindex GitHubCommentPush
.. py:class:: buildbot.reporters.github.GitHubCommentPush

::

    from buildbot.plugins import reporters, util

    gc = reporters.GitHubCommentPush(token='githubAPIToken',
                                     startDescription='Build started.',
                                     endDescription='Build done.')
    factory = util.BuildFactory()
    buildbot_bbtools = util.BuilderConfig(
        name='builder-name',
        workernames=['worker1'],
        factory=factory)
    c['builders'].append(buildbot_bbtools)
    c['services'].append(gc)

:class:`GitHubCommentPush` publishes a comment on a PR using `GitHub Review Comments API <https://developer.github.com/v3/pulls/comments/>`_.

It requires `txrequests`_ package to allow interaction with GitHub REST API.

It is configured with at least a GitHub API token. By default, it will only comment at the end of a build unless a ``startDescription`` is provided.

You can create a token from you own `GitHub - Profile - Applications - Register new application <https://github.com/settings/applications>`_ or use an external tool to generate one.

.. py:class:: GitHubCommentPush(token, startDescription=None, endDescription=None, baseURL=None, verbose=False, builders=None)

    :param string token: token used for authentication. (can be a :ref:`Secret`)
    :param rendereable string startDescription: Custom start message (default: None)
    :param rendereable string endDescription: Custom end message (default: 'Build done.')
    :param string baseURL: specify the github api endpoint if you work with GitHub Enterprise
    :param boolean verbose: if True, logs a message for each successful status push
    :param list builders: only send update for specified builders
    :param boolean verify: disable ssl verification for the case you use temporary self signed certificates
    :param boolean debug: logs every requests and their response
    :returns: string for comment, must be less than 65536 bytes.

Here's a complete example of posting build results as a github comment:

.. code-block:: python

    @util.renderer
    @defer.inlineCallbacks
    def getresults(props):
        all_logs=[]
        master = props.master
        steps = yield props.master.data.get(('builders', props.getProperty('buildername'), 'builds', props.getProperty('buildnumber'), 'steps'))
        for step in steps:
            if step['results'] == util.Results.index('failure'):
                logs = yield master.data.get(("steps", step['stepid'], 'logs'))
                for l in logs:
                    all_logs.append('Step : {0} Result : {1}'.format(step['name'], util.Results[step['results']]))
                    all_logs.append('```')
                    l['stepname'] = step['name']
                    l['content'] = yield master.data.get(("logs", l['logid'], 'contents'))
                    step_logs = l['content']['content'].split('\n')
                    include = False
                    for i, sl in enumerate(step_logs):
                        all_logs.append(sl[1:])
                    all_logs.append('```')
        defer.returnValue('\n'.join(all_logs))

    gc = GitHubCommentPush(token='githubAPIToken',
                           endDescription=getresults,
                           context=Interpolate('buildbot/%(prop:buildername)s'))
    c['services'].append(gc)

.. bb:reporter:: BitbucketServerStatusPush

BitbucketServerStatusPush
~~~~~~~~~~~~~~~~~~~~~~~~~

.. @cindex BitbucketServerStatusPush
.. py:class:: buildbot.reporters.BitbucketServer.BitbucketServerStatusPush

::

    from buildbot.plugins import reporters

    ss = reporters.BitbucketServerStatusPush('https://bitbucketserver.example.com:8080/',
                                   'bitbucketserver_username',
                                   'secret_password')
    c['services'].append(ss)

:class:`BitbucketServerStatusPush` publishes build status using `BitbucketServer Build Integration REST API <https://developer.atlassian.com/static/rest/bitbucket-server/5.1.0/bitbucket-build-rest.html#idm46185565214672>`_.
The build status is published to a specific commit SHA in Bitbucket Server.
It tracks the last build for each builderName for each commit built.

Specifically, it follows the `Updating build status for commits <https://developer.atlassian.com/stash/docs/latest/how-tos/updating-build-status-for-commits.html>`_ document.

It requires `txrequests`_ package to allow interaction with Bitbucket Server REST API.

It uses HTTP Basic AUTH.
As a result, we recommend you use https in your base_url rather than http.

.. py:class:: BitbucketServerStatusPush(base_url, user, password, key=None, statusName=None, startDescription=None, endDescription=None, verbose=False, builders=None)

    :param string base_url: The base url of the Bitbucket Server host, up to and optionally including the first `/` of the path.
    :param string user: The Bitbucket Server user to post as. (can be a :ref:`Secret`)
    :param string password: The Bitbucket Server user's password. (can be a :ref:`Secret`)
    :param renderable string key: Passed to Bitbucket Server to differentiate between statuses.
        A static string can be passed or :class:`Interpolate` for dynamic substitution.
        The default key is `%(prop:buildername)s`.
    :param renderable string statusName: The name that is displayed for this status.
        The default name is nothing, so Bitbucket Server will use the ``key`` parameter.
    :param renderable string startDescription: Custom start message (default: 'Build started.')
    :param renderable string endDescription: Custom end message (default: 'Build done.')
    :param boolean verbose: If True, logs a message for each successful status push.
    :param list builders: Only send update for specified builders.
    :param boolean verify: disable ssl verification for the case you use temporary self signed certificates
    :param boolean debug: logs every requests and their response

.. bb:reporter:: BitbucketServerPRCommentPush

BitbucketServerPRCommentPush
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. @cindex BitbucketServerPRCommentPush
.. py:class:: buildbot.reporters.BitbucketServer.BitbucketServerPRCommentPush

::

    from buildbot.plugins import reporters

    ss = reporters.BitbucketServerPRCommentPush('https://bitbucket-server.example.com:8080/',
                                   'bitbucket_server__username',
                                   'secret_password')
    c['services'].append(ss)


:class:`BitbucketServerPRCommentPush`  publishes a comment on a PR using `Bitbucket Server REST API <https://developer.atlassian.com/static/rest/bitbucket-server/5.0.1/bitbucket-rest.html#idm45993793481168>`_.


.. py:class:: BitBucketServerPRCommentPush(base_url, user, password, messageFormatter=None, verbose=False, debug=None, verify=None, mode=('failing', 'passing', 'warnings'), tags=None, builders=None, schedulers=None, branches=None, buildSetSummary=False):

    :param string base_url: The base url of the Bitbucket server host
    :param string user: The Bitbucket server user to post as. (can be a :ref:`Secret`)
    :param string password: The Bitbucket server user's password. (can be a :ref:`Secret`)
    :param messageFormatter: This is an optional instance of :class:`MessageFormatter` that can be used to generate a custom comment.
    :param boolean verbose: If True, logs a message for each successful status push.
    :param boolean debug: logs every requests and their response
    :param boolean verify: disable ssl verification for the case you use temporary self signed certificates
    :param list mode: A list of strings which will determine the build status that will be reported.
        The values could be ``change``, ``failing``, ``passing``, ``problem``, ``warnings`` or ``exception``.
        There are two shortcuts:

            ``all``
                Equivalent to (``change``, ``failing``, ``passing``, ``problem``, ``warnings``, ``exception``)

            ``warnings``
                Equivalent to (``warnings``, ``failing``).

    :param list tags: A list of tag names to serve status information for.
        Defaults to ``None`` (all tags).
        Use either builders or tags, but not both.
    :param list builders: Only send update for specified builders.
        Defaults to ``None`` (all builders).
        Use either builders or tags, but not both
    :param list schedulers: A list of scheduler names to serve status information for.
        Defaults to ``None`` (all schedulers).
    :param list branches: A list of branch names to serve status information for.
        Defaults to ``None`` (all branches).
    :param boolean buildSetSummary: If true, post a comment when a build set is finished with all build completion messages in it, instead of doing it for each separate build.

.. Note::
    This reporter depends on the Bitbucket server hook to get the pull request url.

.. bb:reporter:: BitbucketStatusPush

BitbucketStatusPush
~~~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.reporters.bitbucket.BitbucketStatusPush

::

    from buildbot.plugins import reporters
    bs = reporters.BitbucketStatusPush('oauth_key', 'oauth_secret')
    c['services'].append(bs)

:class:`BitbucketStatusPush` publishes build status using `Bitbucket Build Status API <https://confluence.atlassian.com/bitbucket/buildstatus-resource-779295267.html>`_.
The build status is published to a specific commit SHA in Bitbucket.
It tracks the last build for each builderName for each commit built.

It requires `txrequests`_ package to allow interaction with the Bitbucket REST and OAuth APIs.

It uses OAuth 2.x to authenticate with Bitbucket.
To enable this, you need to go to your Bitbucket Settings -> OAuth page.
Click "Add consumer".
Give the new consumer a name, eg 'buildbot', and put in any URL as the callback (this is needed for Oauth 2.x but is not used by this reporter, eg 'http://localhost:8010/callback').
Give the consumer Repositories:Write access.
After creating the consumer, you will then be able to see the OAuth key and secret.

.. py:class:: BitbucketStatusPush(oauth_key, oauth_secret, base_url='https://api.bitbucket.org/2.0/repositories', oauth_url='https://bitbucket.org/site/oauth2/access_token', builders=None)

    :param string oauth_key: The OAuth consumer key. (can be a :ref:`Secret`)
    :param string oauth_secret: The OAuth consumer secret. (can be a :ref:`Secret`)
    :param string base_url: Bitbucket's Build Status API URL
    :param string oauth_url: Bitbucket's OAuth API URL
    :param list builders: only send update for specified builders
    :param boolean verify: disable ssl verification for the case you use temporary self signed certificates
    :param boolean debug: logs every requests and their response

.. bb:reporter:: GitLabStatusPush

GitLabStatusPush
~~~~~~~~~~~~~~~~

.. @cindex GitLabStatusPush
.. py:class:: buildbot.reporters.gitlab.GitLabStatusPush

::

    from buildbot.plugins import reporters

    gl = reporters.GitLabStatusPush('private-token', context='continuous-integration/buildbot', baseURL='https://git.yourcompany.com')
    c['services'].append(gl)

:class:`GitLabStatusPush` publishes build status using `GitLab Commit Status API <http://doc.gitlab.com/ce/api/commits.html#commit-status>`_.
The build status is published to a specific commit SHA in GitLab.

It requires `txrequests`_ package to allow interaction with GitLab Commit Status API.

It uses private token auth, and the token owner is required to have at least developer access to each repository. As a result, we recommend you use https in your base_url rather than http.


.. py:class:: GitLabStatusPush(token, startDescription=None, endDescription=None, context=None, baseURL=None, verbose=False)

    :param string token: Private token of user permitted to update status for commits. (can be a :ref:`Secret`)
    :param string startDescription: Description used when build starts
    :param string endDescription: Description used when build ends
    :param string context: Name of your build system, eg. continuous-integration/buildbot
    :param string baseURL: the base url of the GitLab host, up to and optionally including the first `/` of the path. Do not include /api/
    :param string verbose: Be more verbose
    :param boolean verify: disable ssl verification for the case you use temporary self signed certificates
    :param boolean debug: logs every requests and their response


.. bb:reporter:: HipchatStatusPush

HipchatStatusPush
~~~~~~~~~~~~~~~~~

.. @cindex HipchatStatusPush
.. py:class:: buildbot.reporters.hipchat.HipchatStatusPush

::

    from buildbot.plugins import reporters

    hs = reporters.HipchatStatusPush('private-token', endpoint='https://chat.yourcompany.com')
    c['services'].append(hs)

:class:`HipchatStatusPush` publishes a custom message using `Hipchat API v2 <https://www.hipchat.com/docs/apiv2>`_.
The message is published to a user and/or room in Hipchat,

It requires `txrequests`_ package to allow interaction with Hipchat API.

It uses API token auth, and the token owner is required to have at least message/notification access to each destination.


.. py:class:: HipchatStatusPush(auth_token, endpoint="https://api.hipchat.com",
                                builder_room_map=None, builder_user_map=None,
                                wantProperties=False, wantSteps=False, wantPreviousBuild=False, wantLogs=False)

    :param string auth_token: Private API token with access to the "Send Message" and "Send Notification" scopes. (can be a :ref:`Secret`)
    :param string endpoint: (optional) URL of your Hipchat server. Defaults to https://api.hipchat.com
    :param dictionary builder_room_map: (optional) If specified, will forward events about a builder (based on name) to the corresponding room ID.
    :param dictionary builder_user_map: (optional) If specified, will forward events about a builder (based on name) to the corresponding user ID.
    :param boolean wantProperties: (optional) include 'properties' in the build dictionary
    :param boolean wantSteps: (optional) include 'steps' in the build dictionary
    :param boolean wantLogs: (optional) include 'logs' in the steps dictionaries.
        This needs wantSteps=True.
        This dumps the *full* content of logs.
    :param boolean wantPreviousBuild: (optional) include 'prev_build' in the build dictionary
    :param boolean verify: disable ssl verification for the case you use temporary self signed certificates
    :param boolean debug: logs every requests and their response


.. note::

   No message will be sent if the message is empty or there is no destination found.

.. note::

   If a builder name appears in both the room and user map, the same message will be sent to both destinations.


Json object spec
++++++++++++++++

The default json object contains the minimal required parameters to send a message to Hipchat.

.. code-block:: json

    {
        "message": "Buildbot started/finished build MyBuilderName (with result success) here: http://mybuildbot.com/#/builders/23",
        "id_or_email": "12"
    }


If you require different parameters, the Hipchat reporter utilizes the template design pattern and will call :py:func:`getRecipientList` :py:func:`getMessage` :py:func:`getExtraParams`
before sending a message. This allows you to easily override the default implementation for those methods. All of those methods can be deferred.

Method signatures:

.. py:method:: getRecipientList(self, build, event_name)

     :param build: A :class:`Build` object
     :param string event_name: the name of the event trigger for this invocation. either 'new' or 'finished'
     :returns: Deferred

     The deferred should return a dictionary containing the key(s) 'id_or_email' for a private user message and/or
     'room_id_or_name' for room notifications.

.. py:method:: getMessage(self, build, event_name)

     :param build: A :class:`Build` object
     :param string event_name: the name of the event trigger for this invocation. either 'new' or 'finished'
     :returns: Deferred

     The deferred should return a string to send to Hipchat.

.. py:method:: getExtraParams(self, build, event_name)

     :param build: A :class:`Build` object
     :param string event_name: the name of the event trigger for this invocation. either 'new' or 'finished'
     :returns: Deferred

     The deferred should return a dictionary containing any extra parameters you wish to include in your JSON POST
     request that the Hipchat API can consume.

Here's a complete example:

.. code-block:: python

    class MyHipchatStatusPush(HipChatStatusPush):
        name = "MyHipchatStatusPush"

        # send all messages to the same room
        def getRecipientList(self, build, event_name):
            return {
                'room_id_or_name': 'AllBuildNotifications'
            }

        # only send notifications on finished events
        def getMessage(self, build, event_name):
            event_messages = {
                'finished': 'Build finished.'
            }
            return event_messages.get(event_name, '')

        # color notifications based on the build result
        # and alert room on build failure
        def getExtraParams(self, build, event_name):
            result = {}
            if event_name == 'finished':
                result['color'] = 'green' if build['results'] == 0 else 'red'
                result['notify'] = (build['results'] != 0)
            return result

.. bb:reporter:: GerritVerifyStatusPush

GerritVerifyStatusPush
~~~~~~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.status.status_gerrit_verify_status.GerritVerifyStatusPush

:class:`GerritVerifyStatusPush` sends a verify status to Gerrit using the verify-status_ Gerrit plugin.

It is an alternate method to :bb:reporter:`GerritStatusPush`, which uses the SSH API to send reviews.

The verify-status_ plugin allows several CI statuses to be sent for the same change, and display them separately in the Gerrit UI.

Most parameters are :index:`renderables <renderable>`

.. py:class:: GerritVerifyStatusPush(
    baseURL, auth,
    startDescription="Build started.", endDescription="Build done.",
    verification_name=Interpolate("%(prop:buildername)s"), abstain=False, category=None, reporter=None,
    verbose=False, **kwargs)

    :param string baseURL: Gerrit HTTP base URL
    :param string auth: a requests authentication configuration. (can be a :ref:`Secret`)
       if Gerrit is configured with ``BasicAuth``, then it shall be ``('login', 'password')``
       if Gerrit is configured with ``DigestAuth``, then it shall be ``requests.auth.HTTPDigestAuth('login', 'password')`` from the requests module.
    :param renderable string startDescription: the comment sent when the build is starting.
    :param renderable string endDescription: the comment sent when the build is finishing.
    :param renderable string verification_name: the name of the job displayed in the Gerrit UI.
    :param renderable boolean abstain: whether this results should be counted as voting.
    :param renderable boolean category: Category of the build.
    :param renderable boolean reporter: The user that verified this build
    :param boolean verbose: Whether to log every requests.
    :param list builders: only send update for specified builders
    :param boolean verify: disable ssl verification for the case you use temporary self signed certificates
    :param boolean debug: logs every requests and their response

This reporter is integrated with :class:`GerritChangeSource`, and will update changes detected by this change source.

This reporter can also send reports for changes triggered manually provided that there is a property in the build named ``gerrit_changes``, containing the list of changes that were tested.
This property must be a list of dictionaries, containing ``change_id`` and ``revision_id`` keys, as defined in the revision endpoints of the `Gerrit documentation`_

.. _txrequests: https://pypi.python.org/pypi/txrequests
.. _verify-status: https://gerrit.googlesource.com/plugins/verify-status
.. _Gerrit documentation: https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#revision-endpoints
