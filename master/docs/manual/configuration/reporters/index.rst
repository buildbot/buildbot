.. bb:cfg:: reporter

.. _Reporters:

Reporters
=========

.. toctree::
    :hidden:
    :maxdepth: 2

    reporter_base
    bitbucket_server_core_api_status
    bitbucket_server_pr_comment_push
    bitbucket_server_status
    bitbucket_status
    gerrit_status
    gerrit_verify_status
    github_comment
    github_status
    gitlab_status
    http_status
    irc
    mail_notifier
    pushjet_notifier
    pushover_notifier
    telegram
    zulip_status

The Buildmaster has a variety of ways to present build status to various users.
Each such delivery method is a `Reporter Target` object in the configuration's ``services`` list.
To add reporter targets, you just append more objects to this list:

.. code-block:: python

    c['services'] = []

    m = reporters.MailNotifier(fromaddr="buildbot@localhost",
                               extraRecipients=["builds@lists.example.com"],
                               sendToInterestedUsers=False)
    c['services'].append(m)

    c['services'].append(reporters.irc.IRC(host="irc.example.com", nick="bb",
                                           channels=[{"channel": "#example1"},
                                                     {"channel": "#example2",
                                                      "password": "somesecretpassword"}]))

Most reporter objects take a ``tags=`` argument, which can contain a list of tag names.
In this case, the reporters will only show status for Builders that contain the named tags.

.. note:: Implementation Note

    Each of these objects should be a :class:`service.BuildbotService` which will be attached to the BuildMaster object when the configuration is processed.

The following reporters are available:

 * :bb:reporter:`BitbucketServerCoreAPIStatusPush`
 * :bb:reporter:`BitbucketServerPRCommentPush`
 * :bb:reporter:`BitbucketServerStatusPush`
 * :bb:reporter:`BitbucketStatusPush`
 * :bb:reporter:`GerritStatusPush`
 * :bb:reporter:`GerritVerifyStatusPush`
 * :bb:reporter:`GitHubCommentPush`
 * :bb:reporter:`GitHubStatusPush`
 * :bb:reporter:`GitLabStatusPush`
 * :bb:reporter:`HttpStatusPush`
 * :bb:reporter:`IRC`
 * :bb:reporter:`MailNotifier`
 * :bb:reporter:`PushjetNotifier`
 * :bb:reporter:`PushoverNotifier`
 * :bb:reporter:`TelegramBot`
 * :bb:reporter:`ZulipStatusPush`

Most of the report generators derive from :class:`ReporterBase` which implements basic reporter management functionality.
