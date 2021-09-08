.. bb:reporter:: TelegramBot

Telegram Bot
++++++++++++

Buildbot offers a bot, similar to the :bb:reporter:`IRC` for Telegram mobile and desktop messaging app. The bot can notify users and groups about build events, respond to status queries, or force and stop builds on request (if allowed to).

In order to use this reporter, you must first speak to BotFather_ and create a `new telegram bot <https://core.telegram.org/bots#creating-a-new-bot>`_. A quick step-by-step procedure is as follows:

1. Start a chat with BotFather_.

2. Type ``/newbot``.

3. Enter a display name for your bot. It can be any string.

4. Enter a unique username for your bot. Usernames are 5-32 characters long and are case insensitive, but may only include Latin characters, numbers, and underscores. Your bot's username must end in `bot`, e.g. `MyBuildBot` or `MyBuildbotBot`.

5. You will be presented with a token for your bot. Save it, as you will need it for :bb:reporter:`TelegramBot` configuration.

6. Optionally, you may type ``/setcommands``, select the username of your new bot and paste the following text:

    .. jinja:: telegram

        .. code-block:: text

        {% for line in commands|sort %}
            {{ line -}}
        {% endfor %}

   If you do this, Telegram will provide hints about your bot commands.

7. If you want, you can set a custom picture and description for your bot.

.. _BotFather: https://telegram.me/botfather

After setting up the bot in Telegram, you should configure it in Buildbot.

.. code-block:: python

    from buildbot.plugins import reporters
    telegram = reporters.TelegramBot(
            bot_token='bot_token_given_by_botfather',
            bot_username'username_set_in_botfather_bot',
            chat_ids=[-1234567],
            authz={('force', 'stop'): "authorizednick"}
            notify_events=[
                'exception',
                'problem',
                'recovery',
                'worker'
            ],
            usePolling=True)
    c['services'].append(telegram)

The following parameters are accepted by this class:

``bot_token``
    (mandatory)
    Bot token given by BotFather.

``bot_username``
    (optional)
    This should be set to the the bot unique username defined in BotFather. If this parameter is missing, it will be retrieved from the Telegram server. However, in case of the connection problems, configuration of the Buildbot will be interrupted. For this reason it is advised to set this parameter to the correct value.

``chat_ids``
    (optional)
    List of chats IDs to send notifications specified in the ``notify_events`` parameter. For channels it should have form ``@channelusername`` and for private chats and groups it should be a numeric ID. To get it, talk to your bot or add it to a Telegram group and issue ``/getid`` command.

.. note::

    In order to receive notification from the bot, you need to talk to it first (and hit the ``/start`` button) or add it to the group chat.

``authz``
    (optional)
    Authentication list for commands. It must be a dictionary with command names (without slashes) or tuples of command names as keys. There are two special command names: ``''`` (empty string) meaning any harmless command and ``'!'`` for dangerous commands (currently ``/force``, ``/stop``, and ``/shutdown``). The dictionary values are either ``True`` of ``False`` (which allows or deny commands for everybody) or a list of numeric IDs authorized to issue specified commands. By default, harmless commands are allowed for everybody and the dangerous ones are prohibited.

    A sample ``authz`` parameter may look as follows:

    .. code-block:: python

        authz={
          'getid': True,
          '': [123456, 789012],
          ('force', 'stop'): [123456],
        }

    Anybody will be able to run the ``getid`` command, users with IDs 123456 and 789012 will be allowed to run any safe command and the user with ID 123456 will also have the right to force and stop builds.

``tags``
    (optional)
    When set, this bot will only communicate about builders containing those tags.
    (tags functionality is not yet implemented)

``notify_events``
    (optional)
    A list or set of events to be notified on the Telegram chats.
    Telegram bot can listen to build 'start' and 'finish' events. It can also notify about missing workers and their return.
    This parameter can be changed during run-time by sending the ``/notify`` command to the bot.  Note however, that at the buildbot restart or reconfig the notifications listed here will be turned on for the specified chats. On the other hand, removing events from this parameters will not automatically stop notifications for them (you need to turn them off for every channel with the ``/notify`` command).

``showBlameList``
    (optional, disabled by default)
    Whether or not to display the blame list for failed builds.
    (blame list functionality is not yet implemented)

``useRevisions``
    (optional, disabled by default)
    Whether or not to display the revision leading to the build the messages are about.
    (useRevisions functionality is not yet implemented)

``useWebhook``
    (optional, disabled by default)
    By default this bot receives messages from Telegram through polling. You can configure it to use a  web-hook, which may be more efficient. However, this requires the web frontend of the Buildbot to be configured and accessible through HTTPS (not HTTP) on a public IP and port number 443, 80, 88, or 8443. Furthermore, the Buildbot configuration option :bb:cfg:`buildbotURL` must be correctly set. If you are using HTTP authentication, please ensure that the location *buildbotURL*\ ``/telegram``\ *bot_token* (e.g. ``https://buildbot.example.com/telegram123456:secret``) is accessible by everybody.

``certificate``
    (optional)
    A content of your server SSL certificate. This is necessary if the access to the Buildbot web interface is through HTTPS protocol with self-signed certificate and ``userWebhook`` is set to ``True``.

``pollTimeout``
    (optional)
    The time the bot should wait for Telegram to respond to polling using `long polling <https://en.wikipedia.org/wiki/Push_technology#Long_polling>`_.

``retryDelay``
    (optional)
    The delay the bot should wait before attempting to retry communication in case of no connection.

To use the service, you sent Telegram commands (messages starting with a slash) to the bot. In most cases you do not need to add any parameters; the bot will ask you about the details.

Some of the commands currently available:

``/getid``
    Get ID of the user and group. This is useful to find the numeric IDs, which should be put in ``authz`` and ``chat_ids`` configuration parameters.

``/list``
    Emit a list of all configured builders, workers or recent changes.

``/status``
    Announce the status of all builders.

``/watch``
    You will be presented with a list of builders that are currently running. You can select any of them to be notified when the build finishes..

``/last``
    Return the results of the last builds on every builder.

``/notify``
    Report events relating to builds.
    If the command is issued as a private message, then the report will be sent back as a private message to the user who issued the command.
    Otherwise, the report will be sent to the group chat.
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

    By default this command can be executed by anybody. However, consider limiting it with ``authz``, as enabling notifications in huge number of chats (of any kind) can cause some problems with your buildbot efficiency.

``/help``
    Show short help for the commands.

``/commands``
    List all available commands.
    If you explicitly type ``/commands botfather``, the bot will respond with a list of commands with short descriptions, to be provided to BotFather.

``/source``
    Announce the URL of the Buildbot's home page.

``/version``
    Announce the version of this Buildbot.

If explicitly allowed in the ``authz`` config, some additional commands will be available:

.. index:: Forced Builds, from Telegram

``/force``
    Force a build. The bot will read configuration from every configured :bb:sched:`ForceScheduler` and present you with the build parameters you can change. If you set all the required parameters, you will be given an option to start the build.

``/stop``
    Stop a build. If there are any active builds, you will be presented with options to stop them.

``/shutdown``
    Control the shutdown process of the Buildbot master.
    You will be presented with options to start a graceful shutdown, stop it or to shutdown immediately.

If you are in the middle of the conversation with the bot (e.g. it has just asked you a question), you can always stop the current command with a command ``/nay``.

If the `tags` is set (see the tags option in :ref:`Builder-Configuration`) changes related to only builders belonging to those tags of builders will be sent to the channel.

If the `useRevisions` option is set to `True`, the IRC bot will send status messages that replace the build number with a list of revisions that are contained in that build.
So instead of seeing `build #253 of ...`, you would see something like `build containing revisions a87b2c4`.
Revisions that are stored as hashes are shortened to 7 characters in length, as multiple revisions can be contained in one build and may result in too long messages.
