
.. _Change-Hooks:

Change Hooks
~~~~~~~~~~~~

The ``/change_hook`` url is a magic URL which will accept HTTP requests and translate them into changes for buildbot.
Implementations (such as a trivial json-based endpoint and a GitHub implementation) can be found in :src:`master/buildbot/www/hooks`.
The format of the url is :samp:`/change_hook/{DIALECT}` where DIALECT is a package within the hooks directory.
Change_hook is disabled by default and each DIALECT has to be enabled separately, for security reasons

An example www configuration line which enables change_hook and two DIALECTS:

.. code-block:: python

    c['www'] = dict(
        change_hook_dialects={
                              'base': True,
                              'somehook': {'option1':True,
                                           'option2':False}}))

Within the www config dictionary arguments, the ``change_hook`` key enables/disables the module and ``change_hook_dialects`` whitelists DIALECTs where the keys are the module names and the values are optional arguments which will be passed to the hooks.

The :file:`post_build_request.py` script in :file:`master/contrib` allows for the submission of an arbitrary change request.
Run :command:`post_build_request.py --help` for more information.
The ``base`` dialect must be enabled for this to work.

GitHub hook
+++++++++++

.. note::

   There is a standalone HTTP server available for receiving GitHub notifications as well: :file:`contrib/github_buildbot.py`.
   This script may be useful in cases where you cannot expose the WebStatus for public consumption.

The GitHub hook has the following parameters:

``secret`` (default `None`)
    Secret token to use to validate payloads
``strict`` (default `False`)
    If the hook must be strict regarding valid payloads.
    If the value is `False` (default), the signature will only be checked if a secret is specified and a signature was supplied with the payload.
    If the value is `True`, a secret must be provided, and payloads without signature will be ignored.
``codebase`` (default `None`)
    The codebase value to include with created changes.
    If the value is a function (or any other callable), it will be called with the GitHub event payload as argument and the function must return the codebase value to use for the event.
``class`` (default `None`)
    A class to be used for processing incoming payloads.
    If the value is `None` (default), the default class -- :py:class:`buildbot.status.web.hooks.github.GitHubEventHandler` -- will be used.
    The default class handles `ping`, `push` and `pull_request` events only.
    If you'd like to handle other events (see `Event Types & Payloads <https://developer.github.com/v3/activity/events/types/>`_ for more information), you'd need to subclass `GitHubEventHandler` and add handler methods for the corresponding events.
    For example, if you'd like to handle `blah` events, your code should look something like this::

        from buildbot.status.web.hooks.github import GitHubEventHandler

        class MyBlahHandler(GitHubEventHandler):

            def handle_blah(self, payload):
                # Do some magic here
                return [], 'git'

The simples way to use GitHub hook is as follows:

.. code-block:: python

    c['www'] = dict(...,
        change_hook_dialects={'github': { }})

Having added this line, you should add a webhook for your GitHub project (see `Creating Webhooks page at GitHub <https://developer.github.com/webhooks/creating/>`_).
The parameters are:

:guilabel:`Payload URL`
    This URL should point to ``/change_hook/github`` relative to the root of the web status.
    For example, if the grid URL is ``http://builds.example.com/bbot/grid``, then point GitHub to ``http://builds.example.com/bbot/change_hook/github``.
    To specify a project associated to the repository, append ``?project=name`` to the URL.

:guilabel:`Content Type`
    Specify ``application/x-www-form-urlencoded``.  JSON is not currently not supported.

:guilabel:`Secret`
    Any value.
    If you provide a non-empty value (recommended), make sure that your hook is configured to use it:

    .. code-block:: python

            c['www'] = dict(
                ...,
                change_hook_dialects={
                    'github': {
                        'secret': 'MY-SECRET',
                        'strict': True
                    }
                },
                ...))

:guilabel:`Which events would you like to trigger this webhook?`
    Leave the default -- ``Just the push event`` -- other kind of events are not currently supported.

And then press the ``Add Webhook`` button.

.. warning::

    The incoming HTTP requests for this hook are not authenticated by default.
    Anyone who can access the web server can "fake" a request from GitHub, potentially causing the buildmaster to run arbitrary code.

To protect URL against unauthorized access you either specify a secret, or you should use ``change_hook_auth`` option:

.. code-block:: python

    c['www'] = dict(...,
          change_hook_auth=["file:changehook.passwd"]))

create a file ``changehook.passwd``:

.. code-block:: none

    user:password

and change the the ``Payload URL`` of your GitHub webhook to ``http://user:password@builds.example.com/bbot/change_hook/github``.

See the `documentation for twisted cred <https://twistedmatrix.com/documents/current/core/howto/cred.html>`_ for more options to pass to ``change_hook_auth``.

Note that not using ``change_hook_auth`` can expose you to security risks.

Patches are welcome to implement: https://developer.github.com/webhooks/securing/

.. note::

   When using a :ref:`ChangeFilter<Change-Filters>` with a GitHub webhook ensure that your filter matches all desired requests as fields such as ``repository`` and ``project`` may differ in different events.


BitBucket hook
++++++++++++++

The BitBucket hook is as simple as GitHub one and it also takes no options.

.. code-block:: python

    c['www'] = dict(...,
        change_hook_dialects={ 'bitbucket' : True }))

When this is setup you should add a `POST` service pointing to ``/change_hook/bitbucket`` relative to the root of the web status.
For example, it the grid URL is ``http://builds.example.com/bbot/grid``, then point BitBucket to ``http://builds.example.com/change_hook/bitbucket``.
To specify a project associated to the repository, append ``?project=name`` to the URL.

Note that there is a standalone HTTP server available for receiving BitBucket notifications, as well: :file:`contrib/bitbucket_buildbot.py`.
This script may be useful in cases where you cannot expose the WebStatus for public consumption.

.. warning::

    As in the previous case, the incoming HTTP requests for this hook are not authenticated by default.
    Anyone who can access the web status can "fake" a request from BitBucket, potentially causing the buildmaster to run arbitrary code.

To protect URL against unauthorized access you should use ``change_hook_auth`` option.

.. code-block:: python

  c['www'] = dict(...,
        change_hook_auth=["file:changehook.passwd"]))

Then, create a BitBucket service hook (see https://confluence.atlassian.com/display/BITBUCKET/POST+Service+Management) with a WebHook URL like ``http://user:password@builds.example.com/bbot/change_hook/bitbucket``.

Note that as before, not using ``change_hook_auth`` can expose you to security risks.

Google Code hook
++++++++++++++++

The Google Code hook is quite similar to the GitHub Hook.
It has one option for the "Post-Commit Authentication Key" used to check if the request is legitimate::

    c['www'] = dict(...,
        change_hook_dialects={'googlecode': {'secret_key': 'FSP3p-Ghdn4T0oqX'}}
    )

This will add a "Post-Commit URL" for the project in the Google Code administrative interface, pointing to ``/change_hook/googlecode`` relative to the root of the web status.

Alternatively, you can use the :ref:`GoogleCodeAtomPoller` :class:`ChangeSource` that periodically poll the Google Code commit feed for changes.

.. note::

   Google Code doesn't send the branch on which the changes were made.
   So, the hook always returns ``'default'`` as the branch, you can override it with the ``'branch'`` option::

      change_hook_dialects={'googlecode': {'secret_key': 'FSP3p-Ghdn4T0oqX', 'branch': 'master'}}

Poller hook
+++++++++++

The poller hook allows you to use GET or POST requests to trigger polling.
One advantage of this is your buildbot instance can poll at launch (using the pollAtLaunch flag) to get changes that happened while it was down, but then you can still use a commit hook to get fast notification of new changes.

Suppose you have a poller configured like this::

    c['change_source'] = SVNPoller(
        repourl="https://amanda.svn.sourceforge.net/svnroot/amanda/amanda",
        split_file=split_file_branches,
        pollInterval=24*60*60,
        pollAtLaunch=True)

And you configure your WebStatus to enable this hook::

    c['www'] = dict(...,
        change_hook_dialects={'poller': True}
    )

Then you will be able to trigger a poll of the SVN repository by poking the ``/change_hook/poller`` URL from a commit hook like this:

.. code-block:: bash

    curl -s -F poller=https://amanda.svn.sourceforge.net/svnroot/amanda/amanda \
        http://yourbuildbot/change_hook/poller

If no ``poller`` argument is provided then the hook will trigger polling of all polling change sources.

You can restrict which pollers the webhook has access to using the ``allowed`` option::

    c['www'] = dict(...,
        change_hook_dialects={'poller': {'allowed': ['https://amanda.svn.sourceforge.net/svnroot/amanda/amanda']}}
    )

GitLab hook
+++++++++++

The GitLab hook is as simple as GitHub one and it also takes no options.

::

    c['www'] = dict(...,
        change_hook_dialects={ 'gitlab' : True }
    )

When this is setup you should add a `POST` service pointing to ``/change_hook/gitlab`` relative to the root of the web status.
For example, it the grid URL is ``http://builds.example.com/bbot/grid``, then point GitLab to ``http://builds.example.com/change_hook/gitlab``.
The project and/or codebase can also be passed in the URL by appending ``?project=name`` or ``?codebase=foo`` to the URL.
These parameters will be passed along to the scheduler.

.. note::

    Your Git step must be configured with a git@ repourl, not a https: one, else the change from the webhook will not trigger a build.

.. warning::

    As in the previous case, the incoming HTTP requests for this hook are not authenticated by default.
    Anyone who can access the web status can "fake" a request from your GitLab server, potentially causing the buildmaster to run arbitrary code.

To protect URL against unauthorized access you should use ``change_hook_auth`` option.

.. code-block:: python

    c['www'] = dict(...,
        change_hook_auth=["file:changehook.passwd"]
    )

Then, create a GitLab service hook (see https://your.gitlab.server/help/web_hooks) with a WebHook URL like ``http://user:password@builds.example.com/bbot/change_hook/gitlab``.

Note that as before, not using ``change_hook_auth`` can expose you to security risks.

Gitorious Hook
++++++++++++++

The Gitorious hook is as simple as GitHub one and it also takes no options.

::

    c['www'] = dict(...,
        change_hook_dialects={'gitorious': True}
    )

When this is setup you should add a `POST` service pointing to ``/change_hook/gitorious`` relative to the root of the web status.
For example, it the grid URL is ``http://builds.example.com/bbot/grid``, then point Gitorious to ``http://builds.example.com/change_hook/gitorious``.

.. warning::

    As in the previous case, the incoming HTTP requests for this hook are not authenticated by default.
    Anyone who can access the web status can "fake" a request from your Gitorious server, potentially causing the buildmaster to run arbitrary code.

To protect URL against unauthorized access you should use ``change_hook_auth`` option.

.. code-block:: python

    c['www'] = dict(...,
        change_hook_auth=["file:changehook.passwd"]
    )

Then, create a Gitorious web hook (see http://gitorious.org/gitorious/pages/WebHooks) with a WebHook URL like ``http://user:password@builds.example.com/bbot/change_hook/gitorious``.

Note that as before, not using ``change_hook_auth`` can expose you to security risks.

.. note::

    Web hooks are only available for local Gitorious installations, since this feature is not offered as part of Gitorious.org yet.
