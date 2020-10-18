.. bb:reporter:: GitHubCommentPush

GitHubCommentPush
+++++++++++++++++

.. py:currentmodule:: buildbot.reporters.github

.. code-block:: python

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

You can create a token from your own `GitHub - Profile - Applications - Register new application <https://github.com/settings/applications>`_ or use an external tool to generate one.

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
        steps = yield props.master.data.get(
            ('builders', props.getProperty('buildername'), 'builds',
            props.getProperty('buildnumber'), 'steps'))
        for step in steps:
            if step['results'] == util.Results.index('failure'):
                logs = yield master.data.get(("steps", step['stepid'], 'logs'))
                for l in logs:
                    all_logs.append('Step : {0} Result : {1}'.format(
                                        step['name'], util.Results[step['results']]))
                    all_logs.append('```')
                    l['stepname'] = step['name']
                    l['content'] = yield master.data.get(("logs", l['logid'], 'contents'))
                    step_logs = l['content']['content'].split('\n')
                    include = False
                    for i, sl in enumerate(step_logs):
                        all_logs.append(sl[1:])
                    all_logs.append('```')
        return '\n'.join(all_logs)

    gc = GitHubCommentPush(token='githubAPIToken',
                           endDescription=getresults,
                           context=Interpolate('buildbot/%(prop:buildername)s'))
    c['services'].append(gc)

.. _txrequests: https://pypi.python.org/pypi/txrequests
