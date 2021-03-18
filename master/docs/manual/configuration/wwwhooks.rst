
.. _Change-Hooks:

Change Hooks
~~~~~~~~~~~~

The ``/change_hook`` URL is a magic URL which will accept HTTP requests and translate them into changes for Buildbot.
Implementations (such as a trivial json-based endpoint and a GitHub implementation) can be found in :src:`master/buildbot/www/hooks`.
The format of the URL is :samp:`/change_hook/{DIALECT}` where DIALECT is a package within the hooks directory.
``change_hook`` is disabled by default and each DIALECT has to be enabled separately, for security reasons.

An example ``www`` configuration line which enables change_hook and two DIALECTS:

.. code-block:: python

    c['www'] = dict(
        change_hook_dialects={
                              'base': True,
                              'somehook': {'option1':True,
                                           'option2':False},
        },
    )

Within the ``www`` config dictionary arguments, the ``change_hook`` key enables/disables the module, and ``change_hook_dialects`` whitelists DIALECTs where the keys are the module names and the values are optional arguments which will be passed to the hooks.

The :contrib-src:`master/contrib/post_build_request.py` script allows for the submission of an arbitrary change request.
Run :command:`post_build_request.py --help` for more information.
The ``base`` dialect must be enabled for this to work.

.. _Change-Hooks-Auth:

Change Hooks Auth
+++++++++++++++++

By default, the change hook URL is not protected.
Some hooks implement their own authentication method.
Others require the generic method to be secured.

To protect URL against unauthorized access, you may use ``change_hook_auth`` option.

.. note::

    This method uses ``HTTP BasicAuth``. It implies the use of SSL via :ref:`Reverse_Proxy_Config` in order to be fully secured.

.. code-block:: python

    from twisted.cred import strcred
    c['www'] = dict(...,
          change_hook_auth=[strcred.makeChecker("file:changehook.passwd")],
    )

Create a file ``changehook.passwd`` with content:

.. code-block:: none

    user:password

``change_hook_auth`` should be a list of :py:class:`ICredentialsChecker`.
See the details of available options in `Twisted documentation <https://twistedmatrix.com/documents/current/core/howto/cred.html>`_.

.. note::

    In the case of the ``"file:changehook.passwd"`` description in makeChecker, Buildbot ``checkconfig`` might give you a warning "not a valid file: changehook.passwd". To resolve this, you need specify the full path to the file, ``f"file:{os.path.join(basedir, 'changehook.passwd')}"``.

.. bb:chsrc:: Mercurial

Mercurial hook
++++++++++++++

The Mercurial hook uses the base dialect:

.. code-block:: python

    c['www'] = dict(
        ...,
        change_hook_dialects={'base': True},
    )

Once this is configured on your buildmaster add the following hook on your server-side Mercurial repository's ``hgrc``:

.. code-block:: ini

    [hooks]
    changegroup.buildbot = python:/path/to/hgbuildbot.py:hook

You'll find :contrib-src:`master/contrib/hgbuildbot.py`, and its inline documentation, in the :contrib-src:`buildbot-contrib <../../>` repository.

.. bb:chsrc:: GitHub

GitHub hook
+++++++++++

.. note::

   There is a standalone HTTP server available for receiving GitHub notifications as well: :contrib-src:`master/contrib/github_buildbot.py`.
   This script may be useful in cases where you cannot expose the WebStatus for public consumption. Alternatively, you can setup a reverse proxy :ref:`Reverse_Proxy_Config`.

The GitHub hook has the following parameters:

``secret`` (default `None`)
    Secret token to use to validate payloads.
``strict`` (default `False`)
    If the hook must be strict regarding valid payloads.
    If the value is `False` (default), the signature will only be checked if a secret is specified and a signature was supplied with the payload.
    If the value is `True`, a secret must be provided, and payloads without signature will be ignored.
``codebase`` (default `None`)
    The codebase value to include with created changes.
    If the value is a function (or any other callable), it will be called with the GitHub event payload as argument and the function must return the codebase value to use for the event.
``github_property_whitelist`` (default `[]`)
   A list of ``fnmatch`` expressions which match against the flattened pull request information JSON prefixed with ``github``. For example ``github.number`` represents the pull request number. Available entries can be looked up in the GitHub API Documentation or by examining the data returned for a pull request by the API.
``class`` (default `None`)
    A class to be used for processing incoming payloads.
    If the value is `None` (default), the default class -- :py:class:`buildbot.www.hooks.github.GitHubEventHandler` -- will be used.
    The default class handles `ping`, `push` and `pull_request` events only.
    If you'd like to handle other events (see `Event Types & Payloads <https://developer.github.com/v3/activity/events/types/>`_ for more information), you'd need to subclass ``GitHubEventHandler`` and add handler methods for the corresponding events.
    For example, if you'd like to handle `blah` events, your code should look something like this:

    .. code-block:: python

        from buildbot.www.hooks.github import GitHubEventHandler

        class MyBlahHandler(GitHubEventHandler):

            def handle_blah(self, payload):
                # Do some magic here
                return [], 'git'

``skips`` (default ``[r'\[ *skip *ci *\]', r'\[ *ci *skip *\]']``)
    A list of regex pattern makes buildbot ignore the push event.
    For instance, if user push 3 commits and the commit message of branch head
    contains a key string ``[ci skip]``, buildbot will ignore this push event.

    If you want to disable the skip checking, please set it to ``[]``.

``github_api_endpoint`` (default ``https://api.github.com``)
    If you have a self-host GitHub Enterprise installation, please set this URL properly.

``token``
    If your GitHub or GitHub Enterprise instance does not allow anonymous communication, you need to provide an access token.
    Instructions can be found here <https://help.github.com/articles/creating-a-personal-access-token-for-the-command-line/>

``pullrequest_ref`` (default ``merge``)
    Remote ref to test if a pull request is sent to the endpoint.
    See the GitHub developer manual for possible values for pull requests. (e.g. ``head``)


The simplest way to use GitHub hook is as follows:

.. code-block:: python

    c['www'] = dict(
        change_hook_dialects={'github': {}},
    )

Having added this line, you should add a webhook for your GitHub project (see `Creating Webhooks page at GitHub <https://developer.github.com/webhooks/creating/>`_).
The parameters are:

:guilabel:`Payload URL`
    This URL should point to ``/change_hook/github`` relative to the root of the web status.
    For example, if the base URL is ``http://builds.example.com/buildbot``, then point GitHub to ``http://builds.example.com/buildbot/change_hook/github``.
    To specify a project associated to the repository, append ``?project=name`` to the URL.

:guilabel:`Content Type`
    Specify ``application/x-www-form-urlencoded`` or ``application/json``.

:guilabel:`Secret`
    Any value.
    If you provide a non-empty value (recommended), make sure that your hook is configured to use it:

    .. code-block:: python

            c['www'] = dict(
                ...,
                change_hook_dialects={
                    'github': {
                        'secret': 'MY-SECRET',
                    },
                },
            )

:guilabel:`Which events would you like to trigger this webhook?`
    Click -- ``Let me select individual events``, then select ``Push`` and ``Pull request`` -- other kind of events are not currently supported.

And then press the ``Add Webhook`` button.


Github hook creates 3 kinds of changes, distinguishable by their ``category`` field:

- ``None``: This change is a push to a branch.
    Use ``util.ChangeFilter(category=None, repository="http://github.com/<org>/<project>")``

- ``'tag'``: This change is a push to a tag.
    Use ``util.ChangeFilter(category='tag', repository="http://github.com/<org>/<project>")``

- ``'pull'``: This change is from a pull-request creation or update.
    Use ``util.ChangeFilter(category='pull', repository="http://github.com/<org>/<project>")``.
    In this case, the :bb:step:`GitHub` step must be used instead of the standard :bb:step:`Git` in order to be able to pull GitHub's magic refs.
    With this method, the :bb:step:`GitHub` step will always checkout the branch merged with latest master.
    This allows to test the result of the merge instead of just the source branch.
    Note that you can use the :bb:step:`GitHub` for all categories of event.

.. warning::

    Pull requests against every branch will trigger the webhook; the base branch name will be in the ``basename`` property of the build.

.. warning::

    The incoming HTTP requests for this hook are not authenticated by default.
    Anyone who can access the web server can "fake" a request from GitHub, potentially causing the buildmaster to run arbitrary code.

To protect URL against unauthorized access you should use :ref:`Change-Hooks-Auth` option.
Then change the the ``Payload URL`` of your GitHub webhook to ``https://user:password@builds.example.com/bbot/change_hook/github``.


.. bb:chsrc:: BitBucket

BitBucket hook
++++++++++++++

The BitBucket hook is as simple as the GitHub one and takes no options.

.. code-block:: python

    c['www'] = dict(...,
        change_hook_dialects={'bitbucket': True},
    )

When this is set up, you should add a `POST` service pointing to ``/change_hook/bitbucket`` relative to the root of the web status.
For example, if the grid URL is ``http://builds.example.com/bbot/grid``, then point BitBucket to ``http://builds.example.com/change_hook/bitbucket``.
To specify a project associated to the repository, append ``?project=name`` to the URL.

Note that there is a standalone HTTP server available for receiving BitBucket notifications, as well: :contrib-src:`master/contrib/bitbucket_buildbot.py`.
This script may be useful in cases where you cannot expose the WebStatus for public consumption.

.. warning::

    As in the previous case, the incoming HTTP requests for this hook are not authenticated by default.
    Anyone who can access the web status can "fake" a request from BitBucket, potentially causing the buildmaster to run arbitrary code.

To protect URL against unauthorized access you should use :ref:`Change-Hooks-Auth` option.
Then, create a BitBucket service hook (see https://confluence.atlassian.com/display/BITBUCKET/POST+Service+Management) with a WebHook URL like ``https://user:password@builds.example.com/bbot/change_hook/bitbucket``.

Note that as before, not using ``change_hook_auth`` can expose you to security risks.

Bitbucket Cloud hook
+++++++++++++++++++++

.. code-block:: python

    c['www'] = dict(
        ...,
        change_hook_dialects={'bitbucketcloud': {}},
    )

When this is set up, you should add a webhook pointing to ``/change_hook/bitbucketcloud`` relative to the root of the web status.

According to the type of the event, the change category is set to ``push``, ``pull-created``, ``pull-rejected``, ``pull-updated``, ``pull-fulfilled`` or ``ref-deleted``.

The Bitbucket Cloud hook may have the following optional parameters:

``codebase`` (default `None`)
    The codebase value to include with changes or a callable object that will be passed the payload in order to get it.

``bitbucket_property_whitelist`` (default `[]`)
   A list of ``fnmatch`` expressions which match against the flattened pull request information JSON prefixed with ``bitbucket``. For example ``bitbucket.id`` represents the pull request ID. Available entries can be looked up in the BitBucket API Documentation or by examining the data returned for a pull request by the API.

.. Warning::
    The incoming HTTP requests for this hook are not authenticated by default.
    Anyone who can access the web server can "fake" a request from Bitbucket Cloud, potentially causing the buildmaster to run arbitrary code.


Bitbucket Server hook
+++++++++++++++++++++

.. code-block:: python

    c['www'] = dict(
        ...,
        change_hook_dialects={'bitbucketserver': {}},
    )

When this is set up, you should add a webhook pointing to ``/change_hook/bitbucketserver`` relative to the root of the web status.

According to the type of the event, the change category is set to ``push``, ``pull-created``, ``pull-rejected``, ``pull-updated``, ``pull-fulfilled`` or ``ref-deleted``.

The Bitbucket Server hook may have the following optional parameters:

``codebase`` (default `None`)
    The codebase value to include with changes or a callable object that will be passed the payload in order to get it.

``bitbucket_property_whitelist`` (default `[]`)
   A list of ``fnmatch`` expressions which match against the flattened pull request information JSON prefixed with ``bitbucket``. For example ``bitbucket.id`` represents the pull request ID. Available entries can be looked up in the BitBucket API Documentation or by examining the data returned for a pull request by the API.

.. Warning::
    The incoming HTTP requests for this hook are not authenticated by default.
    Anyone who can access the web server can "fake" a request from Bitbucket Server, potentially causing the buildmaster to run arbitrary code.

.. Note::
    This hook requires the `bitbucket-webhooks` plugin (see https://marketplace.atlassian.com/plugins/nl.topicus.bitbucket.bitbucket-webhooks/server/overview).


Poller hook
+++++++++++

The poller hook allows you to use GET or POST requests to trigger polling.
One advantage of this is your buildbot instance can poll at launch (using the pollAtLaunch flag) to get changes that happened while it was down, but then you can still use a commit hook to get fast notification of new changes.

Suppose you have a poller configured like this:

.. code-block:: python

    c['change_source'] = SVNPoller(
        repourl="https://amanda.svn.sourceforge.net/svnroot/amanda/amanda",
        split_file=split_file_branches,
        pollInterval=24*60*60,
        pollAtLaunch=True,
    )

And you configure your WebStatus to enable this hook:

.. code-block:: python

    c['www'] = dict(...,
        change_hook_dialects={'poller': True},
    )

Then you will be able to trigger a poll of the SVN repository by poking the ``/change_hook/poller`` URL from a commit hook like this:

.. code-block:: bash

    curl -s -F poller=https://amanda.svn.sourceforge.net/svnroot/amanda/amanda \
        http://yourbuildbot/change_hook/poller

If no ``poller`` argument is provided then the hook will trigger polling of all polling change sources.

You can restrict which pollers the webhook has access to using the ``allowed`` option:

.. code-block:: python

    c['www'] = {
        ...,
        'change_hook_dialects': {
            'poller': {
                'allowed': ['https://amanda.svn.sourceforge.net/svnroot/amanda/amanda']
            }
        }
    }

.. bb:chsrc:: GitLab

GitLab hook
+++++++++++

.. code-block:: python

    c['www'] = dict(...,
        change_hook_dialects={
            'gitlab' : {
                'secret': '...',
            },
        },
    )


The GitLab hook has the following parameters:

``secret`` (default `None`)
    Secret token to use to validate payloads.

When this is set up, you should add a `POST` service pointing to ``/change_hook/gitlab`` relative to the root of the web status.
For example, if the grid URL is ``http://builds.example.com/bbot/grid``, then point GitLab to ``http://builds.example.com/change_hook/gitlab``.
The project and/or codebase can also be passed in the URL by appending ``?project=name`` or ``?codebase=foo`` to the URL.
These parameters will be passed along to the scheduler.

.. note::

    To handle merge requests from forks properly, it's easiest to use a GitLab source step rather than a Git source step.

.. note::

    Your Git or GitLab step must be configured with a git@ repourl, not a https: one, else the change from the webhook will not trigger a build.

.. warning::

    As in the previous case, the incoming HTTP requests for this hook are not authenticated by default.
    Anyone who can access the web status can "fake" a request from your GitLab server, potentially causing the buildmaster to run arbitrary code.

.. warning::
    When applicable, you need to permit access to internal/local networks.
    See ``https://docs.gitlab.com/ee/security/webhooks.html`` for details.

To protect URL against unauthorized access you should either

  * set secret token in the configuration above, then set it in the GitLab service hook declaration, or
  * use the :ref:`Change-Hooks-Auth` option. Then, create a GitLab service hook (see ``https://your.gitlab.server/help/web_hooks``) with a WebHook URL like ``https://user:password@builds.example.com/bbot/change_hook/gitlab``.

Note that as before, not using ``change_hook_auth`` can expose you to security risks.

.. bb:chsrc:: Gitorious

Gitorious Hook
++++++++++++++

The Gitorious hook is as simple as GitHub one and it also takes no options.

.. code-block:: python

    c['www'] = dict(...,
        change_hook_dialects={'gitorious': True},
    )

When this is set up, you should add a `POST` service pointing to ``/change_hook/gitorious`` relative to the root of the web status.
For example, if the grid URL is ``http://builds.example.com/bbot/grid``, then point Gitorious to ``http://builds.example.com/change_hook/gitorious``.

.. warning::

    As in the previous case, the incoming HTTP requests for this hook are not authenticated by default.
    Anyone who can access the web status can "fake" a request from your Gitorious server, potentially causing the buildmaster to run arbitrary code.

To protect URL against unauthorized access you should use :ref:`Change-Hooks-Auth` option.
Then, create a Gitorious web hook with a WebHook URL like ``https://user:password@builds.example.com/bbot/change_hook/gitorious``.

Note that as before, not using ``change_hook_auth`` can expose you to security risks.

.. note::

    Web hooks are only available for local Gitorious installations, since this feature is not offered as part of Gitorious.org yet.


Custom Hooks
++++++++++++

Custom hooks are supported via the :ref:`Plugins` mechanism.
You can subclass any of the available hook handler classes available in :py:mod:`buildbot.www.hooks` and register it in the plugin system via a custom python module.
For convenience, you can also use the generic option ``custom_class``, e.g.:

.. code-block:: python

    from buildbot.plugins import webhooks
    class CustomBase(webhooks.base):
        def getChanges(self, request):
            args = request.args
            chdict = dict(
                          revision=args.get(b'revision'),
                          repository=args.get(b'repository'),
                          project=args.get(b'project'),
                          codebase=args.get(b'codebase'))
            return ([chdict], None)

    c['www'] = dict(...,
        change_hook_dialects={
            'base' : {
                'custom_class': CustomBase,
            },
        },
    )
