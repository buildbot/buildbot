.. bb:reporter:: IRC

IRC Bot
+++++++

.. py:currentmodule:: buildbot.reporters.irc

.. py:class:: IRC

The :bb:reporter:`IRC` reporter creates an IRC bot which will attach to certain channels and be available for status queries.
It can also be asked to announce builds as they occur, or be told to shut up.

The IRC Bot in buildbot nine, is mostly a rewrite, and not all functionality has been ported yet.
Patches are very welcome for restoring the full functionality.

.. code-block:: python

    from buildbot.plugins import reporters
    irc = reporters.IRC("irc.example.org", "botnickname",
                     useColors=False,
                     channels=[{"channel": "#example1"},
                               {"channel": "#example2",
                                "password": "somesecretpassword"}],
                     password="mysecretnickservpassword",
                     authz={('force', 'stop'): "authorizednick"}
                     notify_events=[
                       'exception',
                       'problem',
                       'recovery',
                       'worker'
                     ])
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

``authz``
    (optional)
    Authentication list for commands. It must be a dictionary with command names or tuples of command names as keys. There are two special command names: ``''`` (empty string) meaning any harmless command and ``'!'`` for dangerous commands (currently ``force``, ``stop``, and ``shutdown``). The dictionary values are either ``True`` of ``False`` (which allows or deny commands for everybody) or a list of nicknames authorized to issue specified commands. By default, harmless commands are allowed for everybody and the dangerous ones are prohibited.

    A sample ``authz`` parameter may look as follows:

    .. code-block:: python

        authz={
          'version': True,
          '': ['alice', 'bob'],
          ('force', 'stop'): ['alice'],
        }

    Anybody will be able to run the ``version`` command, *alice* and *bob* will be allowed to run any safe command and *alice* will also have the right to force and stop builds.

    This parameter replaces older ``allowForce`` and ``allowShutdown``, which are deprecated as they were considered a security risk.

    .. note::

        The authorization is purely nick-based, so it only makes sense if the specified nicks are registered to the IRC server.

``port``
    (optional, default to 6667)
    The port to connect to on the IRC server.

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
    A list or set of events to be notified on the IRC channels.
    Available events to be notified are:

    ``started``
        A build has started.

    ``finished``
        A build has finished.

    ``success``
        A build finished successfully.

    ``failure``
        A build failed.

    ``exception``
        A build generated and exception.

    ``cancelled``
        A build was cancelled.

    ``problem``
        The previous build result was success or warnings, but this one ended with failure or exception.

    ``recovery``
        This is the opposite of ``problem``: the previous build result was failure or exception and this one ended with success or warnings.

    ``worse``
        A build state was worse than the previous one (so e.g. it ended with warnings and the previous one was successful).

    ``better``
        A build state was better than the previous one.

    ``worker``
        A worker is missing. A notification is also send when the previously reported missing worker connects again.

This parameter can be changed during run-time by sending the ``notify`` command to the bot. Note however, that at the buildbot restart or reconfig the notifications listed here will be turned on for the specified channel and nicks. On the other hand, removing events from this parameters will not automatically stop notifications for them (you need to turn them off for every channel with the ``notify`` command).

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

The following parameters are deprecated. You must not use them if you use the new ``authz`` parameter.

.. note:: Security Note

    Please note that any user having access to your irc channel or can PM the bot will be able to create or stop builds :bug:`3377`.
    Use ``authz`` to give explicit list of nicks who are allowed to do this.

``allowForce``
    (deprecated, disabled by default)
    This allow all users to force and stop builds via this bot.

``allowShutdown``
    (deprecated, disabled by default)
    This allow all users to shutdown the master.

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

:samp:`notify on|off|list {EVENT}`
    Report events relating to builds.
    If the command is issued as a private message, then the report will be sent back as a private message to the user who issued the command.
    Otherwise, the report will be sent to the channel.
    Available events to be notified are:

    ``started``
        A build has started.

    ``finished``
        A build has finished.

    ``success``
        A build finished successfully.

    ``failure``
        A build failed.

    ``exception``
        A build generated and exception.

    ``cancelled``
        A build was cancelled.

    ``problem``
        The previous build result was success or warnings, but this one ended with failure or exception.

    ``recovery``
        This is the opposite of ``problem``: the previous build result was failure or exception and this one ended with success or warnings.

    ``worse``
        A build state was worse than the previous one (so e.g. it ended with warnings and the previous one was successful).

    ``better``
        A build state was better than the previous one.

    ``worker``
        A worker is missing. A notification is also send when the previously reported missing worker connects again.

    By default, this command can be executed by anybody. However, consider limiting it with ``authz``, as enabling notifications in huge number of channels or private chats can cause some problems with your buildbot efficiency.

:samp:`help {COMMAND}`
    Describe a command.
    Use :command:`help commands` to get a list of known commands.

``source``
    Announce the URL of the Buildbot's home page.

``version``
    Announce the version of this Buildbot.

Additionally, the config file may specify default notification options as shown in the example earlier.

If explicitly allowed in the ``authz`` config, some additional commands will be available:

:samp:`join {CHANNEL}`
    Join the given IRC channel

:samp:`leave {CHANNEL}`
    Leave the given IRC channel

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

If the `tags` is set (see the tags option in :ref:`Builder-Configuration`) changes related to only builders belonging to those tags of builders will be sent to the channel.

If the `useRevisions` option is set to `True`, the IRC bot will send status messages that replace the build number with a list of revisions that are contained in that build.
So instead of seeing `build #253 of ...`, you would see something like `build containing revisions [a87b2c4]`.
Revisions that are stored as hashes are shortened to 7 characters in length, as multiple revisions can be contained in one build and may exceed the IRC message length limit.

Two additional arguments can be set to control how fast the IRC bot tries to reconnect when it encounters connection issues.
``lostDelay`` is the number of seconds the bot will wait to reconnect when the connection is lost, where as ``failedDelay`` is the number of seconds until the bot tries to reconnect when the connection failed.
``lostDelay`` defaults to a random number between 1 and 5, while ``failedDelay`` defaults to a random one between 45 and 60.
Setting random defaults like this means multiple IRC bots are less likely to deny each other by flooding the server.

.. _PyOpenSSL: http://pyopenssl.sourceforge.net/
