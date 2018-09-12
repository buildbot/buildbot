GitHub teams added to a user's ``groups`` by
:py:class:`~buildbot.www.oauth2.GitHubAuth`'s ``getTeamsMembership`` option are
now added by slug as well as by name.
This means a team named "Bot Builders" in the organization "buildbot" will be
added as both ``buildbot/Bot Builders`` and ``buildbot/bot-builders``.
