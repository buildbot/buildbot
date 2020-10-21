.. bb:reporter:: GitHubStatusPush

GitHubStatusPush
++++++++++++++++

.. py:currentmodule:: buildbot.reporters.github

.. code-block:: python

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

You can create a token from your own `GitHub - Profile - Applications - Register new application <https://github.com/settings/applications>`_ or use an external tool to generate one.

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

.. _txrequests: https://pypi.python.org/pypi/txrequests
