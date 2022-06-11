.. bb:reporter:: MailNotifier

MailNotifier
++++++++++++

.. py:currentmodule:: buildbot.reporters.mail

.. py:class:: MailNotifier

Buildbot can send emails when builds finish.
The most common use of this is to tell developers when their change has caused the build to fail.
It is also quite common to send a message to a mailing list (usually named `builds` or similar) about every build.

The :class:`MailNotifier` reporter is used to accomplish this.
You configure it by specifying who should receive mail, under what circumstances mail should be sent, and how to deliver the mail.
It can be configured to only send out mail for certain builders, and only send them when a build fails or when the builder transitions from success to failure.
It can also be configured to include various build logs in each message.

If a proper lookup function is configured, the message will be sent to the "interested users" list (:ref:`Doing-Things-With-Users`), which includes all developers who made changes in the build.
By default, however, Buildbot does not know how to construct an email address based on the information from the version control system.
See the ``lookup`` argument, below, for more information.

You can add additional, statically-configured, recipients with the ``extraRecipients`` argument.
You can also add interested users by setting the ``owners`` build property to a list of users in the scheduler constructor (:ref:`Configuring-Schedulers`).

Each :class:`MailNotifier` sends mail to a single set of recipients.
To send different kinds of mail to different recipients, use multiple :class:`MailNotifier`\s.
TODO: or subclass MailNotifier and override getRecipients()


The following simple example will send an email upon the completion of each build, to just those developers whose :class:`Change`\s were included in the build.
The email contains a description of the :class:`Build`, its results, and URLs where more information can be obtained.

.. code-block:: python

    from buildbot.plugins import reporters
    mn = reporters.MailNotifier(fromaddr="buildbot@example.org",
                                lookup="example.org")
    c['services'].append(mn)

To get a simple one-message-per-build (say, for a mailing list), use the following form instead.
This form does not send mail to individual developers (and thus does not need the ``lookup=`` argument, explained below); instead it only ever sends mail to the `extra recipients` named in the arguments:

.. code-block:: python

    mn = reporters.MailNotifier(fromaddr="buildbot@example.org",
                                sendToInterestedUsers=False,
                                extraRecipients=['listaddr@example.org'])

If your SMTP host requires authentication before it allows you to send emails, this can also be done by specifying ``smtpUser`` and ``smtpPassword``:

.. code-block:: python

    mn = reporters.MailNotifier(fromaddr="myuser@example.com",
                                sendToInterestedUsers=False,
                                extraRecipients=["listaddr@example.org"],
                                relayhost="smtp.example.com", smtpPort=587,
                                smtpUser="myuser@example.com",
                                smtpPassword="mypassword")

.. note::

   If for some reasons you are not able to send a notification with TLS enabled and specified user name and password, you might want to use :contrib-src:`master/contrib/check_smtp.py` to see if it works at all.

If you want to require Transport Layer Security (TLS), then you can also set ``useTls``:

.. code-block:: python

    mn = reporters.MailNotifier(fromaddr="myuser@example.com",
                                sendToInterestedUsers=False,
                                extraRecipients=["listaddr@example.org"],
                                useTls=True, relayhost="smtp.example.com",
                                smtpPort=587, smtpUser="myuser@example.com",
                                smtpPassword="mypassword")

.. note::

   If you see ``twisted.mail.smtp.TLSRequiredError`` exceptions in the log while using TLS, this can be due *either* to the server not supporting TLS or a missing `PyOpenSSL`_ package on the BuildMaster system.

In some cases, it is desirable to have different information than what is provided in a standard MailNotifier message.
For this purpose, MailNotifier provides the argument ``messageFormatter`` (an instance of ``MessageFormatter``), which allows for creating messages with unique content.

For example, if only short emails are desired (e.g., for delivery to phones):

.. code-block:: python

    from buildbot.plugins import reporters

    generator = reporters.BuildStatusGenerator(
        mode=('problem',),
        message_formatter=reporters.MessageFormatter(template="STATUS: {{ summary }}"))

    mn = reporters.MailNotifier(fromaddr="buildbot@example.org",
                                sendToInterestedUsers=False,
                                extraRecipients=['listaddr@example.org'],
                                generators=[generator])

Another example of a function delivering a customized HTML email is given below:

.. code-block:: python

    from buildbot.plugins import reporters

    template=u'''\
    <h4>Build status: {{ summary }}</h4>
    <p> Worker used: {{ workername }}</p>
    {% for step in build['steps'] %}
    <p> {{ step['name'] }}: {{ step['results'] }}</p>
    {% endfor %}
    <p><b> -- Buildbot</b></p>
    '''

    generator = reporters.BuildStatusGenerator(
        mode=('failing',),
        message_formatter=reporters.MessageFormatter(
            template=template, template_type='html',
            want_properties=True, want_steps=True))

    mn = reporters.MailNotifier(fromaddr="buildbot@example.org",
                                sendToInterestedUsers=False,
                                mode=('failing',),
                                extraRecipients=['listaddr@example.org'],
                                generators=[generator])

.. _PyOpenSSL: http://pyopenssl.sourceforge.net/

MailNotifier arguments
~~~~~~~~~~~~~~~~~~~~~~

``fromaddr``
    The email address to be used in the 'From' header.

``sendToInterestedUsers``
    (boolean).
    If ``True`` (the default), send mail to all of the Interested Users.
    Interested Users are authors of changes and users from the ``owners`` build property.
    Override ``MailNotifier`` ``getResponsibleUsersForBuild`` method to change that.
    If ``False``, only send mail to the ``extraRecipients`` list.

``extraRecipients``
    (list of strings).
    A list of email addresses to which messages should be sent (in addition to the InterestedUsers list, which includes any developers who made :class:`Change`\s that went into this build).
    It is a good idea to create a small mailing list and deliver to that, then let subscribers come and go as they please.

``generators``
    (list).
    A list of instances of ``IReportGenerator`` which defines the conditions of when the messages will be sent and contents of them.
    See :ref:`Report-Generators` for more information.

``relayhost``
    (string, deprecated).
    The host to which the outbound SMTP connection should be made.
    Defaults to 'localhost'

``smtpPort``
    (int).
    The port that will be used on outbound SMTP connections.
    Defaults to 25.

``useTls``
    (boolean).
    When this argument is ``True`` (default is ``False``), ``MailNotifier`` requires that STARTTLS encryption is used for the connection with the ``relayhost``.
    Authentication is required for STARTTLS so the arguments ``smtpUser`` and ``smtpPassword`` must also be specified.

``useSmtps``
    (boolean).
    When this argument is ``True`` (default is ``False``), ``MailNotifier`` connects to ``relayhost`` over an encrypted SSL/TLS connection.
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

``extraHeaders``
    (dictionary).
    A dictionary containing key/value pairs of extra headers to add to sent e-mails.
    Both the keys and the values may be an `Interpolate` instance.

``watchedWorkers``
    This is a list of names of workers, which should be watched. In case a worker goes missing, a notification is sent.
    The value of ``watchedWorkers`` can also be set to *all* (default) or ``None``. You also need to specify an email address to which the notification is sent in the worker configuration.

``dumpMailsToLog``
    If set to ``True``, all completely formatted mails will be dumped to the log before being sent. This can be useful to debug problems with your mail provider.
    Be sure to only turn this on if you really need it, especially if you attach logs to emails. This can dump sensitive information to logs and make them very large.
