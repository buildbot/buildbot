.. _Change-Sources:

Change Sources and Changes
--------------------------

.. contents::
   :depth: 2
   :local:

A *change source* is the mechanism which is used by Buildbot to get information about new changes in a repository maintained by a Version Control System.

These change sources fall broadly into two categories: pollers which periodically check the repository for updates; and hooks, where the repository is configured to notify Buildbot whenever an update occurs.

A :class:`Change` is an abstract way that Buildbot uses to represent changes in any of the Version Control Systems it supports. It contains just enough information needed to acquire specific version of the tree when needed. This usually happens as one of the first steps in a :class:`Build`.

This concept does not map perfectly to every version control system.
For example, for CVS, Buildbot must guess that version updates made to multiple files within a short time represent a single change.

:class:`Change`\s can be provided by a variety of :class:`ChangeSource` types, although any given project will typically have only a single :class:`ChangeSource` active.

.. _How-Different-VC-Systems-Specify-Sources:

How Different VC Systems Specify Sources
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For CVS, the static specifications are *repository* and *module*.
In addition to those, each build uses a timestamp (or omits the timestamp to mean *the latest*) and *branch tag* (which defaults to ``HEAD``).
These parameters collectively specify a set of sources from which a build may be performed.

`Subversion <https://subversion.apache.org>`_ combines the repository, module, and branch into a single *Subversion URL* parameter.
Within that scope, source checkouts can be specified by a numeric *revision number* (a repository-wide monotonically-increasing marker, such that each transaction that changes the repository is indexed by a different revision number), or a revision timestamp.
When branches are used, the repository and module form a static ``baseURL``, while each build has a *revision number* and a *branch* (which defaults to a statically-specified ``defaultBranch``).
The ``baseURL`` and ``branch`` are simply concatenated together to derive the ``repourl`` to use for the checkout.

`Perforce <http://www.perforce.com/>`_ is similar.
The server is specified through a ``P4PORT`` parameter.
Module and branch are specified in a single depot path, and revisions are depot-wide.
When branches are used, the ``p4base`` and ``defaultBranch`` are concatenated together to produce the depot path.

`Bzr <http://bazaar-vcs.org>`_ (which is a descendant of Arch/Bazaar, and is frequently referred to as "Bazaar") has the same sort of repository-vs-workspace model as Arch, but the repository data can either be stored inside the working directory or kept elsewhere (either on the same machine or on an entirely different machine).
For the purposes of Buildbot (which never commits changes), the repository is specified with a URL and a revision number.

The most common way to obtain read-only access to a bzr tree is via HTTP, simply by making the repository visible through a web server like Apache.
Bzr can also use FTP and SFTP servers, if the worker process has sufficient privileges to access them.
Higher performance can be obtained by running a special Bazaar-specific server.
None of these matter to the buildbot: the repository URL just has to match the kind of server being used.
The ``repoURL`` argument provides the location of the repository.

Branches are expressed as subdirectories of the main central repository, which means that if branches are being used, the BZR step is given a ``baseURL`` and ``defaultBranch`` instead of getting the ``repoURL`` argument.

`Darcs <http://darcs.net/>`_ doesn't really have the notion of a single master repository.
Nor does it really have branches.
In Darcs, each working directory is also a repository, and there are operations to push and pull patches from one of these ``repositories`` to another.
For the Buildbot's purposes, all you need to do is specify the URL of a repository that you want to build from.
The worker will then pull the latest patches from that repository and build them.
Multiple branches are implemented by using multiple repositories (possibly living on the same server).

Builders which use Darcs therefore have a static ``repourl`` which specifies the location of the repository.
If branches are being used, the source Step is instead configured with a ``baseURL`` and a ``defaultBranch``, and the two strings are simply concatenated together to obtain the repository's URL.
Each build then has a specific branch which replaces ``defaultBranch``, or just uses the default one.
Instead of a revision number, each build can have a ``context``, which is a string that records all the patches that are present in a given tree (this is the output of ``darcs changes --context``, and is considerably less concise than, e.g. Subversion's revision number, but the patch-reordering flexibility of Darcs makes it impossible to provide a shorter useful specification).

`Mercurial <https://www.mercurial-scm.org/>`_ follows a decentralized model, and each repository can have several branches and tags.
The source Step is configured with a static ``repourl`` which specifies the location of the repository.
Branches are configured with the ``defaultBranch`` argument.
The *revision* is the hash identifier returned by ``hg identify``.

`Git <http://git.or.cz/>`_ also follows a decentralized model, and each repository can have several branches and tags.
The source Step is configured with a static ``repourl`` which specifies the location of the repository.
In addition, an optional ``branch`` parameter can be specified to check out code from a specific branch instead of the default *master* branch.
The *revision* is specified as a SHA1 hash as returned by e.g. ``git rev-parse``.
No attempt is made to ensure that the specified revision is actually a subset of the specified branch.

`Monotone <http://www.monotone.ca/>`_ is another that follows a decentralized model where each repository can have several branches and tags.
The source Step is configured with static ``repourl`` and ``branch`` parameters, which specifies the location of the repository and the branch to use.
The *revision* is specified as a SHA1 hash as returned by e.g. ``mtn automate select w:``.
No attempt is made to ensure that the specified revision is actually a subset of the specified branch.

Comparison
++++++++++

=========== =========== =========== ===================
Name        Change      Revision    Branches
=========== =========== =========== ===================
CVS         patch [1]   timestamp   unnamed
Subversion  revision    integer     directories
Git         commit      sha1 hash   named refs
Mercurial   changeset   sha1 hash   different repos
                                    or (permanently)
                                    named commits
Darcs       ?           none [2]    different repos
Bazaar      ?           ?           ?
Perforce    ?           ?           ?
BitKeeper   changeset   ?           different repos
=========== =========== =========== ===================

* [1] note that CVS only tracks patches to individual files.  Buildbot tries to
  recognize coordinated changes to multiple files by correlating change times.

* [2] Darcs does not have a concise way of representing a particular revision
  of the source.


Tree Stability
++++++++++++++

Changes tend to arrive at a buildmaster in bursts.
In many cases, these bursts of changes are meant to be taken together.
For example, a developer may have pushed multiple commits to a DVCS that comprise the same new feature or bugfix.
To avoid trying to build every change, Buildbot supports the notion of *tree stability*, by waiting for a burst of changes to finish before starting to schedule builds.
This is implemented as a timer, with builds not scheduled until no changes have occurred for the duration of the timer.

.. _Choosing-a-Change-Source:

Choosing a Change Source
~~~~~~~~~~~~~~~~~~~~~~~~

There are a variety of :class:`ChangeSource` classes available, some of which are meant to be used in conjunction with other tools to deliver :class:`Change` events from the VC repository to the buildmaster.

As a quick guide, here is a list of VC systems and the :class:`ChangeSource`\s that might be useful with them.
Note that some of these modules are in Buildbot's :contrib-src:`master/contrib` directory, meaning that they have been offered by other users in hopes they may be useful, and might require some additional work to make them functional.

CVS

* :bb:chsrc:`CVSMaildirSource` (watching mail sent by :contrib-src:`master/contrib/buildbot_cvs_mail.py` script)
* :bb:chsrc:`PBChangeSource` (listening for connections from ``buildbot sendchange`` run in a loginfo script)
* :bb:chsrc:`PBChangeSource` (listening for connections from a long-running :contrib-src:`master/contrib/viewcvspoll.py` polling process which examines the ViewCVS database directly)
* :bb:chsrc:`Change Hooks` in WebStatus

SVN

* :bb:chsrc:`PBChangeSource` (listening for connections from :contrib-src:`master/contrib/svn_buildbot.py` run in a postcommit script)
* :bb:chsrc:`PBChangeSource` (listening for connections from a long-running :contrib-src:`master/contrib/svn_watcher.py` or :contrib-src:`master/contrib/svnpoller.py` polling process
* :bb:chsrc:`SVNCommitEmailMaildirSource` (watching for email sent by :file:`commit-email.pl`)
* :bb:chsrc:`SVNPoller` (polling the SVN repository)
* :bb:chsrc:`Change Hooks` in WebStatus

Darcs

* :bb:chsrc:`PBChangeSource` (listening for connections from :contrib-src:`master/contrib/darcs_buildbot.py` in a commit script)
* :bb:chsrc:`Change Hooks` in WebStatus

Mercurial

* :bb:chsrc:`Change Hooks` in WebStatus (including :contrib-src:`master/contrib/hgbuildbot.py`, configurable in a ``changegroup`` hook)
* `BitBucket change hook <BitBucket hook>`_ (specifically designed for BitBucket notifications, but requiring a publicly-accessible WebStatus)
* :bb:chsrc:`HgPoller` (polling a remote Mercurial repository)
* :bb:chsrc:`BitbucketPullrequestPoller` (polling Bitbucket for pull requests)
* :ref:`Mail-parsing-ChangeSources`, though there are no ready-to-use recipes

Bzr (the newer Bazaar)

* :bb:chsrc:`PBChangeSource` (listening for connections from :contrib-src:`master/contrib/bzr_buildbot.py` run in a post-change-branch-tip or commit hook)
* :bb:chsrc:`BzrPoller` (polling the Bzr repository)
* :bb:chsrc:`Change Hooks` in WebStatus

Git

* :bb:chsrc:`PBChangeSource` (listening for connections from :contrib-src:`master/contrib/git_buildbot.py` run in the post-receive hook)
* :bb:chsrc:`PBChangeSource` (listening for connections from :contrib-src:`master/contrib/github_buildbot.py`, which listens for notifications from GitHub)
* :bb:chsrc:`Change Hooks` in WebStatus
* :bb:chsrc:`GitHub` change hook (specifically designed for GitHub notifications, but requiring a publicly-accessible WebStatus)
* :bb:chsrc:`BitBucket` change hook (specifically designed for BitBucket notifications, but requiring a publicly-accessible WebStatus)
* :bb:chsrc:`GitPoller` (polling a remote Git repository)
* :bb:chsrc:`GitHubPullrequestPoller` (polling GitHub API for pull requests)
* :bb:chsrc:`BitbucketPullrequestPoller` (polling Bitbucket for pull requests)

Repo/Gerrit

* :bb:chsrc:`GerritChangeSource` connects to Gerrit via SSH to get a live stream of changes
* :bb:chsrc:`GerritEventLogPoller` connects to Gerrit via HTTP with the help of the plugin events-log_

Monotone

* :bb:chsrc:`PBChangeSource` (listening for connections from :file:`monotone-buildbot.lua`, which is available with Monotone)

All VC systems can be driven by a :bb:chsrc:`PBChangeSource` and the ``buildbot sendchange`` tool run from some form of commit script.
If you write an email parsing function, they can also all be driven by a suitable :ref:`mail-parsing source <Mail-parsing-ChangeSources>`.
Additionally, handlers for web-based notification (i.e. from GitHub) can be used with WebStatus' change_hook module.
The interface is simple, so adding your own handlers (and sharing!) should be a breeze.

See :bb:index:`chsrc` for a full list of change sources.

.. index:: Change Sources

.. bb:cfg:: change_source

Configuring Change Sources
~~~~~~~~~~~~~~~~~~~~~~~~~~

The :bb:cfg:`change_source` configuration key holds all active change sources for the configuration.

Most configurations have a single :class:`ChangeSource`, watching only a single tree, e.g.,

.. code-block:: python

    from buildbot.plugins import changes

    c['change_source'] = changes.PBChangeSource()

For more advanced configurations, the parameter can be a list of change sources:

.. code-block:: python

    source1 = ...
    source2 = ...
    c['change_source'] = [
        source1, source2
    ]

Repository and Project
++++++++++++++++++++++

:class:`ChangeSource`\s will, in general, automatically provide the proper :attr:`repository` attribute for any changes they produce.
For systems which operate on URL-like specifiers, this is a repository URL.
Other :class:`ChangeSource`\s adapt the concept as necessary.

Many :class:`ChangeSource`\s allow you to specify a project, as well.
This attribute is useful when building from several distinct codebases in the same buildmaster: the project string can serve to differentiate the different codebases.
Schedulers can filter on project, so you can configure different builders to run for each project.

.. _Mail-parsing-ChangeSources:

Mail-parsing ChangeSources
~~~~~~~~~~~~~~~~~~~~~~~~~~

Many projects publish information about changes to their source tree by sending an email message out to a mailing list, frequently named :samp:`{PROJECT}-commits` or :samp:`{PROJECT}-changes`.
Each message usually contains a description of the change (who made the change, which files were affected) and sometimes a copy of the diff.
Humans can subscribe to this list to stay informed about what's happening to the source tree.

Buildbot can also subscribe to a `-commits` mailing list, and can trigger builds in response to Changes that it hears about.
The buildmaster admin needs to arrange for these email messages to arrive in a place where the buildmaster can find them, and configure the buildmaster to parse the messages correctly.
Once that is in place, the email parser will create Change objects and deliver them to the schedulers (see :ref:`Schedulers`) just like any other ChangeSource.

There are two components to setting up an email-based ChangeSource.
The first is to route the email messages to the buildmaster, which is done by dropping them into a `maildir`.
The second is to actually parse the messages, which is highly dependent upon the tool that was used to create them.
Each VC system has a collection of favorite change-emailing tools with a slightly different format and its own parsing function.
Buildbot has a separate ChangeSource variant for each of these parsing functions.

Once you've chosen a maildir location and a parsing function, create the change source and put it in :bb:cfg:`change_source`:

.. code-block:: python

    from buildbot.plugins import changes

    c['change_source'] = changes.CVSMaildirSource("~/maildir-buildbot",
                                                  prefix="/trunk/")

.. _Subscribing-the-Buildmaster:

Subscribing the Buildmaster
+++++++++++++++++++++++++++

The recommended way to install Buildbot is to create a dedicated account for the buildmaster.
If you do this, the account will probably have a distinct email address (perhaps `buildmaster@example.org`).
Then just arrange for this account's email to be delivered to a suitable maildir (described in the next section).

If Buildbot does not have its own account, `extension addresses` can be used to distinguish between emails intended for the buildmaster and emails intended for the rest of the account.
In most modern MTAs, the e.g. `foo@example.org` account has control over every email address at example.org which begins with "foo", such that emails addressed to `account-foo@example.org` can be delivered to a different destination than `account-bar@example.org`.
qmail does this by using separate :file:`.qmail` files for the two destinations (:file:`.qmail-foo` and :file:`.qmail-bar`, with :file:`.qmail` controlling the base address and :file:`.qmail-default` controlling all other extensions).
Other MTAs have similar mechanisms.

Thus you can assign an extension address like `foo-buildmaster@example.org` to the buildmaster and retain `foo@example.org` for your own use.

.. _Using-Maildirs:

Using Maildirs
++++++++++++++

A `maildir` is a simple directory structure originally developed for qmail that allows safe atomic update without locking.
Create a base directory with three subdirectories: :file:`new`, :file:`tmp`, and :file:`cur`.
When messages arrive, they are put into a uniquely-named file (using pids, timestamps, and random numbers) in :file:`tmp`. When the file is complete, it is atomically renamed into :file:`new`. Eventually the buildmaster notices the file in :file:`new`, reads and parses the contents, then moves it into :file:`cur`. A cronjob can be used to delete files in :file:`cur` at leisure.

Maildirs are frequently created with the :command:`maildirmake` tool, but a simple :samp:`mkdir -p ~/{MAILDIR}/\{cur,new,tmp\}` is pretty much equivalent.

Many modern MTAs can deliver directly to maildirs.
The usual :file:`.forward` or :file:`.procmailrc` syntax is to name the base directory with a trailing slash, so something like :samp:`~/{MAILDIR}/`\.
qmail and postfix are maildir-capable MTAs, and procmail is a maildir-capable MDA (Mail Delivery Agent).

Here is an example procmail config, located in :file:`~/.procmailrc`:

.. code-block:: none

    # .procmailrc
    # routes incoming mail to appropriate mailboxes
    PATH=/usr/bin:/usr/local/bin
    MAILDIR=$HOME/Mail
    LOGFILE=.procmail_log
    SHELL=/bin/sh

    :0
    *
    new

If procmail is not setup on a system wide basis, then the following one-line :file:`.forward` file will invoke it.

.. code-block:: none

    !/usr/bin/procmail

For MTAs which cannot put files into maildirs directly, the `safecat` tool can be executed from a :file:`.forward` file to accomplish the same thing.

The Buildmaster uses the linux DNotify facility to receive immediate notification when the maildir's :file:`new` directory has changed.
When this facility is not available, it polls the directory for new messages, every 10 seconds by default.

.. _Parsing-Email-Change-Messages:

Parsing Email Change Messages
+++++++++++++++++++++++++++++

The second component to setting up an email-based :class:`ChangeSource` is to parse the actual notices.
This is highly dependent upon the VC system and commit script in use.

A couple of common tools used to create these change emails, along with the Buildbot tools to parse them, are:

CVS
    Buildbot CVS MailNotifier
        :bb:chsrc:`CVSMaildirSource`

SVN
    svnmailer
        http://opensource.perlig.de/en/svnmailer/

    :file:`commit-email.pl`
        :bb:chsrc:`SVNCommitEmailMaildirSource`

Bzr
    Launchpad
        :bb:chsrc:`BzrLaunchpadEmailMaildirSource`

Mercurial
    NotifyExtension
        https://www.mercurial-scm.org/wiki/NotifyExtension

Git
    post-receive-email
        http://git.kernel.org/?p=git/git.git;a=blob;f=contrib/hooks/post-receive-email;hb=HEAD


The following sections describe the parsers available for each of these tools.

Most of these parsers accept a ``prefix=`` argument, which is used to limit the set of files that the buildmaster pays attention to.
This is most useful for systems like CVS and SVN which put multiple projects in a single repository (or use repository names to indicate branches).
Each filename that appears in the email is tested against the prefix: if the filename does not start with the prefix, the file is ignored.
If the filename *does* start with the prefix, that prefix is stripped from the filename before any further processing is done.
Thus the prefix usually ends with a slash.

.. bb:chsrc:: CVSMaildirSource

.. _CVSMaildirSource:

CVSMaildirSource
++++++++++++++++

.. py:class:: buildbot.changes.mail.CVSMaildirSource

This parser works with the :contrib-src:`master/contrib/buildbot_cvs_mail.py` script.

The script sends an email containing all the files submitted in one directory.
It is invoked by using the :file:`CVSROOT/loginfo` facility.

The Buildbot's :bb:chsrc:`CVSMaildirSource` knows how to parse these messages and turn them into Change objects.
It takes the directory name of the maildir root.
For example:

.. code-block:: python

    from buildbot.plugins import changes

    c['change_source'] = changes.CVSMaildirSource("/home/buildbot/Mail")

Configuration of CVS and :contrib-src:`buildbot_cvs_mail.py <master/contrib/buildbot_cvs_mail.py>`
::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

CVS must be configured to invoke the :contrib-src:`buildbot_cvs_mail.py <master/contrib/buildbot_cvs_mail.py>` script when files are checked in.
This is done via the CVS loginfo configuration file.

To update this, first do:

.. code-block:: bash

    cvs checkout CVSROOT

cd to the CVSROOT directory and edit the file loginfo, adding a line like:

.. code-block:: none

    SomeModule /cvsroot/CVSROOT/buildbot_cvs_mail.py --cvsroot :ext:example.com:/cvsroot -e buildbot -P SomeModule %@{sVv@}

.. note::

   For cvs version 1.12.x, the ``--path %p`` option is required.
   Version 1.11.x and 1.12.x report the directory path differently.

The above example you put the :contrib-src:`buildbot_cvs_mail.py <master/contrib/buildbot_cvs_mail.py>` script under /cvsroot/CVSROOT.
It can be anywhere.
Run the script with ``--help`` to see all the options.
At the very least, the options ``-e`` (email) and ``-P`` (project) should be specified.
The line must end with ``%{sVv}``.
This is expanded to the files that were modified.

Additional entries can be added to support more modules.

See :command:`buildbot_cvs_mail.py --help` for more information on the available options.

.. bb:chsrc:: SVNCommitEmailMaildirSource

.. _SVNCommitEmailMaildirSource:

SVNCommitEmailMaildirSource
++++++++++++++++++++++++++++

.. py:class:: buildbot.changes.mail.SVNCommitEmailMaildirSource

:bb:chsrc:`SVNCommitEmailMaildirSource` parses message sent out by the :file:`commit-email.pl` script, which is included in the Subversion distribution.

It does not currently handle branches: all of the Change objects that it creates will be associated with the default (i.e. trunk) branch.

.. code-block:: python

    from buildbot.plugins import changes

    c['change_source'] = changes.SVNCommitEmailMaildirSource("~/maildir-buildbot")

.. bb:chsrc:: BzrLaunchpadEmailMaildirSource

.. _BzrLaunchpadEmailMaildirSource:

BzrLaunchpadEmailMaildirSource
+++++++++++++++++++++++++++++++

.. py:class:: buildbot.changes.mail.BzrLaunchpadEmailMaildirSource

:bb:chsrc:`BzrLaunchpadEmailMaildirSource` parses the mails that are sent to addresses that subscribe to branch revision notifications for a bzr branch hosted on Launchpad.

The branch name defaults to :samp:`lp:{Launchpad path}`.
For example ``lp:~maria-captains/maria/5.1``.

If only a single branch is used, the default branch name can be changed by setting ``defaultBranch``.

For multiple branches, pass a dictionary as the value of the ``branchMap`` option to map specific repository paths to specific branch names (see example below).
The leading ``lp:`` prefix of the path is optional.

The ``prefix`` option is not supported (it is silently ignored).
Use the ``branchMap`` and ``defaultBranch`` instead to assign changes to branches (and just do not subscribe the Buildbot to branches that are not of interest).

The revision number is obtained from the email text.
The bzr revision id is not available in the mails sent by Launchpad.
However, it is possible to set the bzr `append_revisions_only` option for public shared repositories to avoid new pushes of merges changing the meaning of old revision numbers.

.. code-block:: python

    from buildbot.plugins import changes

    bm = {
        'lp:~maria-captains/maria/5.1': '5.1',
        'lp:~maria-captains/maria/6.0': '6.0'
    }
    c['change_source'] = changes.BzrLaunchpadEmailMaildirSource("~/maildir-buildbot",
                                                                branchMap=bm)

.. bb:chsrc:: PBChangeSource

.. _PBChangeSource:

PBChangeSource
~~~~~~~~~~~~~~

.. py:class:: buildbot.changes.pb.PBChangeSource

:bb:chsrc:`PBChangeSource` actually listens on a TCP port for clients to connect and push change notices *into* the Buildmaster.
This is used by the built-in ``buildbot sendchange`` notification tool, as well as several version-control hook scripts.
This change is also useful for creating new kinds of change sources that work on a `push` model instead of some kind of subscription scheme, for example a script which is run out of an email :file:`.forward` file.
This ChangeSource always runs on the same TCP port as the workers.
It shares the same protocol, and in fact shares the same space of "usernames", so you cannot configure a :bb:chsrc:`PBChangeSource` with the same name as a worker.

If you have a publicly accessible worker port and are using :bb:chsrc:`PBChangeSource`, *you must establish a secure username and password for the change source*.
If your sendchange credentials are known (e.g., the defaults), then your buildmaster is susceptible to injection of arbitrary changes, which (depending on the build factories) could lead to arbitrary code execution on workers.

The :bb:chsrc:`PBChangeSource` is created with the following arguments.

``port``
    Which port to listen on.
    If ``None`` (which is the default), it shares the port used for worker connections.

``user``
    The user account that the client program must use to connect.
    Defaults to ``change``

``passwd``
    The password for the connection - defaults to ``changepw``.
    Can be a :ref:`Secret`.
    Do not use this default on a publicly exposed port!

``prefix``
    The prefix to be found and stripped from filenames delivered over the connection, defaulting to ``None``.
    Any filenames which do not start with this prefix will be removed.
    If all the filenames in a given Change are removed, then that whole Change will be dropped.
    This string should probably end with a directory separator.

    This is useful for changes coming from version control systems that represent branches as parent directories within the repository (like SVN and Perforce).
    Use a prefix of ``trunk/`` or ``project/branches/foobranch/`` to only follow one branch and to get correct tree-relative filenames.
    Without a prefix, the :bb:chsrc:`PBChangeSource` will probably deliver Changes with filenames like :file:`trunk/foo.c` instead of just :file:`foo.c`.
    Of course this also depends upon the tool sending the Changes in (like :bb:cmdline:`buildbot sendchange <sendchange>`) and what filenames it is delivering: that tool may be filtering and stripping prefixes at the sending end.

For example:

.. code-block:: python

    from buildbot.plugins import changes

    c['change_source'] = changes.PBChangeSource(port=9999, user='laura', passwd='fpga')

The following hooks are useful for sending changes to a :bb:chsrc:`PBChangeSource`\:

.. _Bzr-Hook:

Bzr Hook
++++++++

Bzr is also written in Python, and the Bzr hook depends on Twisted to send the changes.

To install, put :contrib-src:`master/contrib/bzr_buildbot.py` in one of your plugins locations a bzr plugins directory (e.g., :file:`~/.bazaar/plugins`).
Then, in one of your bazaar conf files (e.g., :file:`~/.bazaar/locations.conf`), set the location you want to connect with Buildbot with these keys:

  * ``buildbot_on``
    one of 'commit', 'push, or 'change'.
    Turns the plugin on to report changes via commit, changes via push, or any changes to the trunk.
    'change' is recommended.

  * ``buildbot_server``
    (required to send to a Buildbot master) the URL of the Buildbot master to which you will connect (as of this writing, the same server and port to which workers connect).

  * ``buildbot_port``
    (optional, defaults to 9989) the port of the Buildbot master to which you will connect (as of this writing, the same server and port to which workers connect)

  * ``buildbot_pqm``
    (optional, defaults to not pqm) Normally, the user that commits the revision is the user that is responsible for the change.
    When run in a pqm (Patch Queue Manager, see https://launchpad.net/pqm) environment, the user that commits is the Patch Queue Manager, and the user that committed the *parent* revision is responsible for the change.
    To turn on the pqm mode, set this value to any of (case-insensitive) "Yes", "Y", "True", or "T".

  * ``buildbot_dry_run``
    (optional, defaults to not a dry run) Normally, the post-commit hook will attempt to communicate with the configured Buildbot server and port.
    If this parameter is included and any of (case-insensitive) "Yes", "Y", "True", or "T", then the hook will simply print what it would have sent, but not attempt to contact the Buildbot master.

  * ``buildbot_send_branch_name``
    (optional, defaults to not sending the branch name) If your Buildbot's bzr source build step uses a repourl, do *not* turn this on.
    If your buildbot's bzr build step uses a baseURL, then you may set this value to any of (case-insensitive) "Yes", "Y", "True", or "T" to have the Buildbot master append the branch name to the baseURL.

.. note::

   The bzr smart server (as of version 2.2.2) doesn't know how to resolve ``bzr://`` urls into absolute paths so any paths in ``locations.conf`` won't match, hence no change notifications will be sent to Buildbot.
   Setting configuration parameters globally or in-branch might still work.
   When Buildbot no longer has a hardcoded password, it will be a configuration option here as well.

Here's a simple example that you might have in your :file:`~/.bazaar/locations.conf`\.

.. code-block:: ini

    [chroot-*:///var/local/myrepo/mybranch]
    buildbot_on = change
    buildbot_server = localhost

.. bb:chsrc:: P4Source

.. _P4Source:

P4Source
~~~~~~~~

The :bb:chsrc:`P4Source` periodically polls a `Perforce <http://www.perforce.com/>`_ depot for changes.
It accepts the following arguments:

``p4port``
    The Perforce server to connect to (as :samp:`{host}:{port}`).

``p4user``
    The Perforce user.

``p4passwd``
    The Perforce password.

``p4base``
    The base depot path to watch, without the trailing '/...'.

``p4bin``
    An optional string parameter.
    Specify the location of the perforce command line binary (p4).
    You only need to do this if the perforce binary is not in the path of the Buildbot user.
    Defaults to `p4`.

``split_file``
    A function that maps a pathname, without the leading ``p4base``, to a (branch, filename) tuple.
    The default just returns ``(None, branchfile)``, which effectively disables branch support.
    You should supply a function which understands your repository structure.

``pollInterval``
    How often to poll, in seconds.
    Defaults to 600 (10 minutes).

``pollRandomDelayMin``
    Minimum delay in seconds to wait before each poll, default is 0.
    This is useful in case you have a lot of pollers and you want to spread the
    polling load over a period of time.
    Setting it equal to the maximum delay will effectively delay all polls by a
    fixed amount of time.
    Must be less than or equal to the maximum delay.

``pollRandomDelayMax``
    Maximum delay in seconds to wait before each poll, default is 0.
    This is useful in case you have a lot of pollers and you want to spread the
    polling load over a period of time.
    Must be less than the poll interval.

``project``
    Set the name of the project to be used for the :bb:chsrc:`P4Source`.
    This will then be set in any changes generated by the ``P4Source``, and can be used in a Change Filter for triggering particular builders.

``pollAtLaunch``
    Determines when the first poll occurs.
    True = immediately on launch, False = wait for one pollInterval (default).

``histmax``
    The maximum number of changes to inspect at a time.
    If more than this number occur since the last poll, older changes will be silently ignored.

``encoding``
    The character encoding of ``p4``\'s output.
    This defaults to "utf8", but if your commit messages are in another encoding, specify that here.
    For example, if you're using Perforce on Windows, you may need to use "cp437" as the encoding if "utf8" generates errors in your master log.

``server_tz``
    The timezone of the Perforce server, using the usual timezone format (e.g: ``"Europe/Stockholm"``) in case it's not in UTC.

``use_tickets``
    Set to ``True`` to use ticket-based authentication, instead of passwords (but you still need to specify ``p4passwd``).

``ticket_login_interval``
    How often to get a new ticket, in seconds, when ``use_tickets`` is enabled.
    Defaults to 86400 (24 hours).

``revlink``
    A function that maps branch and revision to a valid url (e.g. p4web), stored along with the change.
    This function must be a callable which takes two arguments, the branch and the revision.
    Defaults to lambda branch, revision: (u'')

``resolvewho``
    A function that resolves the Perforce 'user@workspace' into a more verbose form, stored as the author of the change. Useful when usernames do not match email addresses and external, client-side lookup is required.
    This function must be a callable which takes one argument.
    Defaults to lambda who: (who)

Example #1
++++++++++

This configuration uses the :envvar:`P4PORT`, :envvar:`P4USER`, and :envvar:`P4PASSWD` specified in the buildmaster's environment.
It watches a project in which the branch name is simply the next path component, and the file is all path components after.

.. code-block:: python

    from buildbot.plugins import changes

    s = changes.P4Source(p4base='//depot/project/',
                         split_file=lambda branchfile: branchfile.split('/',1))
    c['change_source'] = s

Example #2
++++++++++

Similar to the previous example but also resolves the branch and revision into a valid revlink.

.. code-block:: python

    from buildbot.plugins import changes

    s = changes.P4Source(
        p4base='//depot/project/',
        split_file=lambda branchfile: branchfile.split('/',1))
        revlink=lambda branch, revision: 'http://p4web:8080/@md=d&@/{}?ac=10'.format(revision)
    c['change_source'] = s

.. bb:chsrc:: SVNPoller

.. _SVNPoller:

SVNPoller
~~~~~~~~~

.. py:class:: buildbot.changes.svnpoller.SVNPoller

The :bb:chsrc:`SVNPoller` is a ChangeSource which periodically polls a `Subversion <https://subversion.apache.org>`_ repository for new revisions, by running the ``svn log`` command in a subshell.
It can watch a single branch or multiple branches.

:bb:chsrc:`SVNPoller` accepts the following arguments:

``repourl``
    The base URL path to watch, like ``svn://svn.twistedmatrix.com/svn/Twisted/trunk``, or ``http://divmod.org/svn/Divmo/``, or even ``file:///home/svn/Repository/ProjectA/branches/1.5/``.
    This must include the access scheme, the location of the repository (both the hostname for remote ones, and any additional directory names necessary to get to the repository), and the sub-path within the repository's virtual filesystem for the project and branch of interest.

    The :bb:chsrc:`SVNPoller` will only pay attention to files inside the subdirectory specified by the complete repourl.

``split_file``
    A function to convert pathnames into ``(branch, relative_pathname)`` tuples.
    Use this to explain your repository's branch-naming policy to :bb:chsrc:`SVNPoller`.
    This function must accept a single string (the pathname relative to the repository) and return a two-entry tuple.
    Directory pathnames always end with a right slash to distinguish them from files, like ``trunk/src/``, or ``src/``.
    There are a few utility functions in :mod:`buildbot.changes.svnpoller` that can be used as a :meth:`split_file` function; see below for details.

    For directories, the relative pathname returned by :meth:`split_file` should end with a right slash but an empty string is also accepted for the root, like ``("branches/1.5.x", "")`` being converted from ``"branches/1.5.x/"``.

    The default value always returns ``(None, path)``, which indicates that all files are on the trunk.

    Subclasses of :bb:chsrc:`SVNPoller` can override the :meth:`split_file` method instead of using the ``split_file=`` argument.

``project``
    Set the name of the project to be used for the :bb:chsrc:`SVNPoller`.
    This will then be set in any changes generated by the :bb:chsrc:`SVNPoller`, and can be used in a :ref:`Change Filter <ChangeFilter>` for triggering particular builders.

``svnuser``
    An optional string parameter.
    If set, the option `--user` argument will be added to all :command:`svn` commands.
    Use this if you have to authenticate to the svn server before you can do :command:`svn info` or :command:`svn log` commands.
    Can be a :ref:`Secret`.

``svnpasswd``
    Like ``svnuser``, this will cause a option `--password` argument to be passed to all :command:`svn` commands.
    Can be a :ref:`Secret`.

``pollInterval``
    How often to poll, in seconds.
    Defaults to 600 (checking once every 10 minutes).
    Lower this if you want the Buildbot to notice changes faster, raise it if you want to reduce the network and CPU load on your svn server.
    Please be considerate of public SVN repositories by using a large interval when polling them.

``pollRandomDelayMin``
    Minimum delay in seconds to wait before each poll, default is 0.
    This is useful in case you have a lot of pollers and you want to spread the
    polling load over a period of time.
    Setting it equal to the maximum delay will effectively delay all polls by a
    fixed amount of time.
    Must be less than or equal to the maximum delay.

``pollRandomDelayMax``
    Maximum delay in seconds to wait before each poll, default is 0.
    This is useful in case you have a lot of pollers and you want to spread the
    polling load over a period of time.
    Must be less than the poll interval.

``pollAtLaunch``
    Determines when the first poll occurs.
    True = immediately on launch, False = wait for one pollInterval (default).

``histmax``
    The maximum number of changes to inspect at a time.
    Every ``pollInterval`` seconds, the :bb:chsrc:`SVNPoller` asks for the last ``histmax`` changes and looks through them for any revisions it does not already know about.
    If more than ``histmax`` revisions have been committed since the last poll, older changes will be silently ignored.
    Larger values of ``histmax`` will cause more time and memory to be consumed on each poll attempt.
    ``histmax`` defaults to 100.

``svnbin``
    This controls the :command:`svn` executable to use.
    If subversion is installed in a weird place on your system (outside of the buildmaster's :envvar:`PATH`), use this to tell :bb:chsrc:`SVNPoller` where to find it.
    The default value of `svn` will almost always be sufficient.

``revlinktmpl``
    This parameter is deprecated in favour of specifying a global revlink option.
    This parameter allows a link to be provided for each revision (for example, to websvn or viewvc).
    These links appear anywhere changes are shown, such as on build or change pages.
    The proper form for this parameter is an URL with the portion that will substitute for a revision number replaced by ''%s''.
    For example, ``'http://myserver/websvn/revision.php?rev=%s'`` could be used to cause revision links to be created to a websvn repository viewer.

``cachepath``
    If specified, this is a pathname of a cache file that :bb:chsrc:`SVNPoller` will use to store its state between restarts of the master.

``extra_args``
    If specified, the extra arguments will be added to the svn command args.

Several split file functions are available for common SVN repository layouts.
For a poller that is only monitoring trunk, the default split file function is available explicitly as ``split_file_alwaystrunk``:

.. code-block:: python

    from buildbot.plugins import changes, util

    c['change_source'] = changes.SVNPoller(
        repourl="svn://svn.twistedmatrix.com/svn/Twisted/trunk",
        split_file=util.svn.split_file_alwaystrunk)

For repositories with the ``/trunk`` and :samp:`/branches/{BRANCH}` layout, ``split_file_branches`` will do the job:

.. code-block:: python

    from buildbot.plugins import changes, util

    c['change_source'] = changes.SVNPoller(
        repourl="https://amanda.svn.sourceforge.net/svnroot/amanda/amanda",
        split_file=util.svn.split_file_branches)

When using this splitter the poller will set the ``project`` attribute of any changes to the ``project`` attribute of the poller.

For repositories with the :samp:`{PROJECT}/trunk` and :samp:`{PROJECT}/branches/{BRANCH}` layout, ``split_file_projects_branches`` will do the job:

.. code-block:: python

    from buildbot.plugins import changes, util

    c['change_source'] = changes.SVNPoller(
        repourl="https://amanda.svn.sourceforge.net/svnroot/amanda/",
        split_file=util.svn.split_file_projects_branches)

When using this splitter the poller will set the ``project`` attribute of any changes to the project determined by the splitter.

The :bb:chsrc:`SVNPoller` is highly adaptable to various Subversion layouts.
See :ref:`Customizing-SVNPoller` for details and some common scenarios.

.. bb:chsrc:: BzrPoller

.. _Bzr-Poller:

Bzr Poller
~~~~~~~~~~

If you cannot insert a Bzr hook in the server, you can use the :bb:chsrc:`BzrPoller`.
To use it, put :contrib-src:`master/contrib/bzr_buildbot.py` somewhere that your Buildbot configuration can import it.
Even putting it in the same directory as the :file:`master.cfg` should work.
Install the poller in the Buildbot configuration as with any other change source.
Minimally, provide a URL that you want to poll (``bzr://``, ``bzr+ssh://``, or ``lp:``), making sure the Buildbot user has necessary privileges.

.. code-block:: python

    # put bzr_buildbot.py file to the same directory as master.cfg
    from bzr_buildbot import BzrPoller

    c['change_source'] = BzrPoller(
        url='bzr://hostname/my_project',
        poll_interval=300)

The ``BzrPoller`` parameters are:

``url``
    The URL to poll.

``poll_interval``
    The number of seconds to wait between polls.
    Defaults to 10 minutes.

``branch_name``
    Any value to be used as the branch name.
    Defaults to None, or specify a string, or specify the constants from :contrib-src:`bzr_buildbot.py <master/contrib/bzr_buildbot.py>` ``SHORT`` or ``FULL`` to get the short branch name or full branch address.

``blame_merge_author``
    Normally, the user that commits the revision is the user that is responsible for the change.
    When run in a pqm (Patch Queue Manager, see https://launchpad.net/pqm) environment, the user that commits is the Patch Queue Manager, and the user that committed the merged, *parent* revision is responsible for the change.
    Set this value to ``True`` if this is pointed against a PQM-managed branch.

.. bb:chsrc:: GitPoller

.. _GitPoller:

GitPoller
~~~~~~~~~

If you cannot take advantage of post-receive hooks as provided by :contrib-src:`master/contrib/git_buildbot.py` for example, then you can use the :bb:chsrc:`GitPoller`.

The :bb:chsrc:`GitPoller` periodically fetches from a remote Git repository and processes any changes.
It requires its own working directory for operation.
The default should be adequate, but it can be overridden via the ``workdir`` property.

.. note:: There can only be a single `GitPoller` pointed at any given repository.

The :bb:chsrc:`GitPoller` requires Git-1.7 and later.
It accepts the following arguments:

``repourl``
    The git-url that describes the remote repository, e.g. ``git@example.com:foobaz/myrepo.git`` (see the :command:`git fetch` help for more info on git-url formats)

``branches``
    One of the following:

    * a list of the branches to fetch. Non-existing branches are ignored.
    * ``True`` indicating that all branches should be fetched
    * a callable which takes a single argument.
      It should take a remote refspec (such as ``'refs/heads/master'``), and return a boolean indicating whether that branch should be fetched.

``branch``
    Accepts a single branch name to fetch.
    Exists for backwards compatibility with old configurations.

``pollInterval``
    Interval in seconds between polls, default is 10 minutes

``pollRandomDelayMin``
    Minimum delay in seconds to wait before each poll, default is 0.
    This is useful in case you have a lot of pollers and you want to spread the
    polling load over a period of time.
    Setting it equal to the maximum delay will effectively delay all polls by a
    fixed amount of time.
    Must be less than or equal to the maximum delay.

``pollRandomDelayMax``
    Maximum delay in seconds to wait before each poll, default is 0.
    This is useful in case you have a lot of pollers and you want to spread the
    polling load over a period of time.
    Must be less than the poll interval.

``pollAtLaunch``
    Determines when the first poll occurs.
    True = immediately on launch, False = wait for one pollInterval (default).

``buildPushesWithNoCommits``
    Determines if a push on a new branch or update of an already known branch with
    already known commits should trigger a build.
    This is useful in case you have build steps depending on the name of the
    branch and you use topic branches for development. When you merge your topic
    branch into "master" (for instance), a new build will be triggered.
    (defaults to False).

``gitbin``
    Path to the Git binary, defaults to just ``'git'``

``category``
    Set the category to be used for the changes produced by the :bb:chsrc:`GitPoller`.
    This will then be set in any changes generated by the :bb:chsrc:`GitPoller`, and can be used in a Change Filter for triggering particular builders.

``project``
    Set the name of the project to be used for the :bb:chsrc:`GitPoller`.
    This will then be set in any changes generated by the ``GitPoller``, and can be used in a Change Filter for triggering particular builders.

``usetimestamps``
    Parse each revision's commit timestamp (default is ``True``), or ignore it in favor of the current time, so that recently processed commits appear together in the waterfall page.

``encoding``
    Set encoding will be used to parse author's name and commit message.
    Default encoding is ``'utf-8'``.
    This will not be applied to file names since Git will translate non-ascii file names to unreadable escape sequences.

``workdir``
    The directory where the poller should keep its local repository.
    The default is :samp:`gitpoller_work`.
    If this is a relative path, it will be interpreted relative to the master's basedir.
    Multiple Git pollers can share the same directory.

``only_tags``
    Determines if the GitPoller should poll for new tags in the git repository.

``sshPrivateKey`` (optional)
    Specifies private SSH key for git to use. This may be either a :ref:`Secret`
    or just a string. This option requires Git-2.3 or later. The master must
    either have the host in the known hosts file or the host key must be
    specified via the `sshHostKey` option.

``sshHostKey`` (optional)
    Specifies public host key to match when authenticating with SSH
    public key authentication. This may be either a :ref:`Secret` or just a
    string. `sshPrivateKey` must be specified in order to use this option.
    The host key must be in the form of `<key type> <base64-encoded string>`,
    e.g. `ssh-rsa AAAAB3N<...>FAaQ==`.

``sshKnownHosts`` (optional)
   Specifies the contents of the SSH known_hosts file to match when authenticating with SSH public key authentication.
   This may be either a :ref:`Secret` or just a string.
   `sshPrivateKey` must be specified in order to use this option.
   `sshHostKey` must not be specified in order to use this option.

A configuration for the Git poller might look like this:

.. code-block:: python

    from buildbot.plugins import changes

    c['change_source'] = changes.GitPoller(repourl='git@example.com:foobaz/myrepo.git',
                                           branches=['master', 'great_new_feature'])

.. bb:chsrc:: HgPoller

.. _HgPoller:

HgPoller
~~~~~~~~

The :bb:chsrc:`HgPoller` periodically pulls a named branch from a remote Mercurial repository and processes any changes.
It requires its own working directory for operation, which must be specified via the ``workdir`` property.

The :bb:chsrc:`HgPoller` requires a working ``hg`` executable, and at least a read-only access to the repository it polls (possibly through ssh keys or by tweaking the ``hgrc`` of the system user Buildbot runs as).

The :bb:chsrc:`HgPoller` will not transmit any change if there are several heads on the watched named branch.
This is similar (although not identical) to the Mercurial executable behaviour.
This exceptional condition is usually the result of a developer mistake, and usually does not last for long.
It is reported in logs.
If fixed by a later merge, the buildmaster administrator does not have anything to do: that merge will be transmitted, together with the intermediate ones.

The :bb:chsrc:`HgPoller` accepts the following arguments:

``name``
    The name of the poller.
    This must be unique, and defaults to the ``repourl``.

``repourl``
    The url that describes the remote repository, e.g. ``http://hg.example.com/projects/myrepo``.
    Any url suitable for ``hg pull`` can be specified.

``bookmarks``
    A list of the bookmarks to monitor.

``branches``
    A list of the branches to monitor; defaults to ``['default']``.

``branch``
    The desired branch to pull.
    Exists for backwards compatibility with old configurations.

``workdir``
    The directory where the poller should keep its local repository.
    It is mandatory for now, although later releases may provide a meaningful default.

    It also serves to identify the poller in the buildmaster internal database.
    Changing it may result in re-processing all changes so far.

    Several :bb:chsrc:`HgPoller` instances may share the same ``workdir`` for mutualisation of the common history between two different branches, thus easing on local and remote system resources and bandwidth.

    If relative, the ``workdir`` will be interpreted from the master directory.

``pollInterval``
    Interval in seconds between polls, default is 10 minutes

``pollRandomDelayMin``
    Minimum delay in seconds to wait before each poll, default is 0.
    This is useful in case you have a lot of pollers and you want to spread the
    polling load over a period of time.
    Setting it equal to the maximum delay will effectively delay all polls by a
    fixed amount of time.
    Must be less than or equal to the maximum delay.

``pollRandomDelayMax``
    Maximum delay in seconds to wait before each poll, default is 0.
    This is useful in case you have a lot of pollers and you want to spread the
    polling load over a period of time.
    Must be less than the poll interval.

``pollAtLaunch``
    Determines when the first poll occurs.
    True = immediately on launch, False = wait for one pollInterval (default).

``hgbin``
    Path to the Mercurial binary, defaults to just ``'hg'``.

``category``
    Set the category to be used for the changes produced by the :bb:chsrc:`HgPoller`.
    This will then be set in any changes generated by the :bb:chsrc:`HgPoller`, and can be used in a Change Filter for triggering particular builders.

``project``
    Set the name of the project to be used for the :bb:chsrc:`HgPoller`.
    This will then be set in any changes generated by the ``HgPoller``, and can be used in a Change Filter for triggering particular builders.

``usetimestamps``
    Parse each revision's commit timestamp (default is ``True``), or ignore it in favor of the current time, so that recently processed commits appear together in the waterfall page.

``encoding``
    Set encoding will be used to parse author's name and commit message.
    Default encoding is ``'utf-8'``.

``revlink``
    A function that maps branch and revision to a valid url (e.g. hgweb), stored along with the change.
    This function must be a callable which takes two arguments, the branch and the revision.
    Defaults to lambda branch, revision: (u'')

A configuration for the Mercurial poller might look like this:

.. code-block:: python

    from buildbot.plugins import changes

    c['change_source'] = changes.HgPoller(repourl='http://hg.example.org/projects/myrepo',
                                          branch='great_new_feature',
                                          workdir='hg-myrepo')


.. bb:chsrc:: GitHubPullrequestPoller

.. _GitHubPullrequestPoller:

GitHubPullrequestPoller
~~~~~~~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.changes.github.GitHubPullrequestPoller

This :bb:chsrc:`GitHubPullrequestPoller` periodically polls the GitHub API for new or updated pull requests. The `author`, `revision`, `revlink`, `branch` and `files` fields in the recorded changes are populated with information extracted from the pull request. This allows to filter for certain changes in files and create a blamelist based on the authors in the GitHub pull request.

The :bb:chsrc:`GitHubPullrequestPoller` accepts the following arguments:

``owner``
    The owner of the GitHub repository. This argument is required.

``repo``
    The name of the GitHub repository. This argument is required.

``branches``
    List of branches to accept as base branch (e.g. master). Defaults to `None` and accepts all branches as base.

``pollInterval``
    Poll interval between polls in seconds. Default is 10 minutes.

``pollAtLaunch``
    Whether to poll on startup of the buildbot master. Default is `False` and first poll will occur `pollInterval` seconds after the master start.

``category``
    Set the category to be used for the changes produced by the :bb:chsrc:`GitHubPullrequestPoller`.
    This will then be set in any changes generated by the :bb:chsrc:`GitHubPullrequestPoller`, and can be used in a Change Filter for triggering particular builders.

``baseURL``
    GitHub API endpoint. Default is ``https://api.github.com``.

``pullrequest_filter``
    A callable which takes a `dict` which contains the decoded `JSON` object of the GitHub pull request as argument. All fields specified by the GitHub API are accessible. If the callable returns `False` the pull request is ignored. Default is `True` which does not filter any pull requests.

``token``
    A GitHub API token to execute all requests to the API authenticated. It is strongly recommended to use a API token since it increases GitHub API rate limits significantly.

``repository_type``
   Set which type of repository link will be in the `repository` property. Possible values ``https``, ``svn``, ``git`` or ``svn``. This link can then be used in a Source Step to checkout the source.

``magic_link``
   Set to `True` if the changes should contain ``refs/pulls/<PR #>/merge`` in the `branch` property and a link to the base `repository` in the repository property. These properties can be used by the :bb:step:`GitHub` source to pull from the special branch in the base repository. Default is `False`.

``github_property_whitelist``
   A list of ``fnmatch`` expressions which match against the flattened pull request information JSON prefixed with ``github``. For example ``github.number`` represents the pull request number. Available entries can be looked up in the GitHub API Documentation or by examining the data returned for a pull request by the API.

.. bb:chsrc:: BitbucketPullrequestPoller

.. _BitbucketPullrequestPoller:

BitbucketPullrequestPoller
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.changes.bitbucket.BitbucketPullrequestPoller

This :bb:chsrc:`BitbucketPullrequestPoller` periodically polls Bitbucket for new or updated pull requests.
It uses Bitbuckets powerful `Pull Request REST API`_ to gather the information needed.

The :bb:chsrc:`BitbucketPullrequestPoller` accepts the following arguments:

``owner``
    The owner of the Bitbucket repository.
    All Bitbucket Urls are of the form ``https://bitbucket.org/owner/slug/``.

``slug``
    The name of the Bitbucket repository.

``auth``
    Authorization data tuple ``(usename, password)`` (optional).
    If set, it will be used as authorization headers at Bitbucket API.

``branch``
    A single branch or a list of branches which should be processed.
    If it is ``None`` (the default) all pull requests are used.

``pollInterval``
    Interval in seconds between polls, default is 10 minutes.

``pollAtLaunch``
    Determines when the first poll occurs.
    ``True`` = immediately on launch, ``False`` = wait for one ``pollInterval`` (default).

``category``
    Set the category to be used by the :bb:chsrc:`BitbucketPullrequestPoller`.
    This will then be set in any changes generated by the :bb:chsrc:`BitbucketPullrequestPoller`, and can be used in a Change Filter for triggering particular builders.

``project``
    Set the name of the project to be used by the :bb:chsrc:`BitbucketPullrequestPoller`.
    This will then be set in any changes generated by the ``BitbucketPullrequestPoller``, and can be used in a Change Filter for triggering particular builders.

``pullrequest_filter``
    A callable which takes one parameter, the decoded Python object of the pull request JSON.
    If it returns ``False``, the pull request is ignored.
    It can be used to define custom filters based on the content of the pull request.
    See the Bitbucket documentation for more information about the format of the response.
    By default, the filter always returns ``True``.

``usetimestamps``
    Parse each revision's commit timestamp (default is ``True``), or ignore it in favor of the current time, so that recently processed commits appear together in the waterfall page.

``bitbucket_property_whitelist``
   A list of ``fnmatch`` expressions which match against the flattened pull request information JSON prefixed with ``bitbucket``. For example ``bitbucket.id`` represents the pull request ID. Available entries can be looked up in the BitBucket API Documentation or by examining the data returned for a pull request by the API.

``encoding``
    This parameter is deprecated and has no effects.
    Author's name and commit message are always parsed in ``'utf-8'``.

A minimal configuration for the Bitbucket pull request poller might look like this:

.. code-block:: python

    from buildbot.plugins import changes

    c['change_source'] = changes.BitbucketPullrequestPoller(
        owner='myname',
        slug='myrepo',
      )

Here is a more complex configuration using a ``pullrequest_filter``.
The pull request is only processed if at least 3 people have already approved it:

.. code-block:: python

    def approve_filter(pr, threshold):
        approves = 0
        for participant in pr['participants']:
            if participant['approved']:
                approves = approves + 1

        if approves < threshold:
            return False
        return True

    from buildbot.plugins import changes
    c['change_source'] = changes.BitbucketPullrequestPoller(
        owner='myname',
        slug='myrepo',
        branch='mybranch',
        project='myproject',
        pullrequest_filter=lambda pr : approve_filter(pr,3),
        pollInterval=600,
    )

.. warning::

    Anyone who can create pull requests for the Bitbucket repository can initiate a change, potentially causing the buildmaster to run arbitrary code.

.. _Pull Request REST API: https://confluence.atlassian.com/display/BITBUCKET/pullrequests+Resource

.. bb:chsrc:: GerritChangeSource

.. _GerritChangeSource:

GerritChangeSource
~~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.changes.gerritchangesource.GerritChangeSource

The :bb:chsrc:`GerritChangeSource` class connects to a Gerrit server by its SSH interface and uses its event source mechanism, `gerrit stream-events <https://gerrit-documentation.storage.googleapis.com/Documentation/2.2.1/cmd-stream-events.html>`_.

Note that the Gerrit event stream is stateless and any events that occur while buildbot is not connected to Gerrit will be lost. See :bb:chsrc:`GerritEventLogPoller` for a stateful change source.

The ``patchset-created`` and ``ref-updated`` events will be deduplicated, that is, if multiple events related to the same revision are received, only the first will be acted upon.
This allows ``GerritChangeSource`` to be used together with :bb:chsrc:`GerritEventLogPoller`.

The :bb:chsrc:`GerritChangeSource` accepts the following arguments:

``gerritserver``
    The dns or ip that host the Gerrit ssh server

``gerritport``
    The port of the Gerrit ssh server

``username``
    The username to use to connect to Gerrit

``identity_file``
    Ssh identity file to for authentication (optional).
    Pay attention to the `ssh passphrase`

``handled_events``
    Event to be handled (optional).
    By default processes `patchset-created` and `ref-updated`

``get_files``
    Populate the `files` attribute of emitted changes (default `False`).
    Buildbot will run an extra query command for each handled event to determine the changed files.

``debug``
    Print Gerrit event in the log (default `False`).
    This allows to debug event content, but will eventually fill your logs with useless Gerrit event logs.

By default this class adds a change to the Buildbot system for each of the following events:

``patchset-created``
    A change is proposed for review.
    Automatic checks like :file:`checkpatch.pl` can be automatically triggered.
    Beware of what kind of automatic task you trigger.
    At this point, no trusted human has reviewed the code, and a patch could be specially crafted by an attacker to compromise your workers.

``ref-updated``
    A change has been merged into the repository.
    Typically, this kind of event can lead to a complete rebuild of the project, and upload binaries to an incremental build results server.

But you can specify how to handle events:

* Any event with change and patchSet will be processed by universal collector by default.
* In case you've specified processing function for the given kind of events, all events of this kind will be processed only by this function, bypassing universal collector.

An example:

.. code-block:: python

    from buildbot.plugins import changes

    class MyGerritChangeSource(changes.GerritChangeSource):
        """Custom GerritChangeSource
        """
        def eventReceived_patchset_created(self, properties, event):
            """Handler events without properties
            """
            properties = {}
            self.addChangeFromEvent(properties, event)

This class will populate the property list of the triggered build with the info received from Gerrit server in JSON format.

.. warning::

   If you selected :class:`GerritChangeSource`, you **must** use :bb:step:`Gerrit` source step: the ``branch`` property of the change will be :samp:`{target_branch}/{change_id}` and such a ref cannot be resolved, so the :bb:step:`Git` source step would fail.

.. index:: Properties; from GerritChangeSource

In case of ``patchset-created`` event, these properties will be:

``event.change.branch``
    Branch of the Change

``event.change.id``
    Change's ID in the Gerrit system (the ChangeId: in commit comments)

``event.change.number``
    Change's number in Gerrit system

``event.change.owner.email``
    Change's owner email (owner is first uploader)

``event.change.owner.name``
    Change's owner name

``event.change.project``
    Project of the Change

``event.change.subject``
    Change's subject

``event.change.url``
    URL of the Change in the Gerrit's web interface

``event.patchSet.number``
    Patchset's version number

``event.patchSet.ref``
    Patchset's Gerrit "virtual branch"

``event.patchSet.revision``
    Patchset's Git commit ID

``event.patchSet.uploader.email``
    Patchset uploader's email (owner is first uploader)

``event.patchSet.uploader.name``
    Patchset uploader's name (owner is first uploader)

``event.type``
    Event type (``patchset-created``)

``event.uploader.email``
    Patchset uploader's email

``event.uploader.name``
    Patchset uploader's name

In case of ``ref-updated`` event, these properties will be:

``event.refUpdate.newRev``
    New Git commit ID (after merger)

``event.refUpdate.oldRev``
    Previous Git commit ID (before merger)

``event.refUpdate.project``
    Project that was updated

``event.refUpdate.refName``
    Branch that was updated

``event.submitter.email``
    Submitter's email (merger responsible)

``event.submitter.name``
    Submitter's name (merger responsible)

``event.type``
    Event type (``ref-updated``)

``event.submitter.email``
    Submitter's email (merger responsible)

``event.submitter.name``
    Submitter's name (merger responsible)

A configuration for this source might look like:

.. code-block:: python

    from buildbot.plugins import changes

    c['change_source'] = changes.GerritChangeSource(
        "gerrit.example.com",
        "gerrit_user",
        handled_events=["patchset-created", "change-merged"])

See :file:`master/docs/examples/git_gerrit.cfg` or :file:`master/docs/examples/repo_gerrit.cfg` in the Buildbot distribution for a full example setup of Git+Gerrit or Repo+Gerrit of :bb:chsrc:`GerritChangeSource`.

.. bb:chsrc:: GerritEventLogPoller

.. _GerritEventLogPoller:

GerritEventLogPoller
~~~~~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.changes.gerritchangesource.GerritEventLogPoller

The :bb:chsrc:`GerritEventLogPoller` class is similar to :bb:chsrc:`GerritChangeSource` but connects to the Gerrit server by its HTTP interface and uses the events-log_ plugin.

Note that the decision of whether to use :bb:chsrc:`GerritEventLogPoller` and :bb:chsrc:`GerritChangeSource` will depend on your needs. The trade off is:

1. :bb:chsrc:`GerritChangeSource` is low-overhead and reacts instantaneously to events, but a broken connection to Gerrit will lead to missed changes
2. :bb:chsrc:`GerritEventLogPoller` is subject to polling overhead and reacts only at it's polling rate, but is robust to a broken connection to Gerrit and missed changes will be discovered when a connection is restored.

You can use both at the same time to get the advantages of each. They will coordinate through the database to avoid duplicate changes generated for buildbot.

.. note::

    The :bb:chsrc:`GerritEventLogPoller` requires either the ``txrequest`` or the ``treq`` package.

The :bb:chsrc:`GerritEventLogPoller` accepts the following arguments:

``baseURL``
    The HTTP url where to find Gerrit. If the URL of the events-log endpoint for your server is ``https://example.com/a/plugins/events-log/events/`` then the ``baseURL`` is ``https://example.com/a``. Ensure that ``/a`` is included.

``auth``
    A request's authentication configuration.
    If Gerrit is configured with ``BasicAuth``, then it shall be ``('login', 'password')``.
    If Gerrit is configured with ``DigestAuth``, then it shall be ``requests.auth.HTTPDigestAuth('login', 'password')`` from the requests module.
    However, note that usage of ``requests.auth.HTTPDigestAuth`` is incompatible with ``treq``.

``handled_events``
    Event to be handled (optional).
    By default processes `patchset-created` and `ref-updated`.

``pollInterval``
    Interval in seconds between polls (default is 30 sec).

``pollAtLaunch``
    Determines when the first poll occurs.
    True = immediately on launch (default), False = wait for one pollInterval.

``gitBaseURL``
    The git URL where Gerrit is accessible via git+ssh protocol.

``get_files``
    Populate the `files` attribute of emitted changes (default `False`).
    Buildbot will run an extra query command for each handled event to determine the changed files.

``debug``
    Print Gerrit event in the log (default `False`).
    This allows to debug event content, but will eventually fill your logs with useless Gerrit event logs.

The same customization can be done as :bb:chsrc:`GerritChangeSource` for handling special events.

.. _events-log: https://gerrit.googlesource.com/plugins/events-log/

GerritChangeFilter
~~~~~~~~~~~~~~~~~~
.. py:class:: buildbot.changes.gerritchangesource.GerritChangeFilter

:class:`GerritChangeFilter` is a ready to use :class:`ChangeFilter` you can pass to :bb:sched:`AnyBranchScheduler` in order to filter changes, to create pre-commit builders or post-commit schedulers.
It has the same api as :ref:`Change Filter <ChangeFilter>`, except it has additional `eventtype` set of filter (can as well be specified as value, list, regular expression, or callable).

An example is following:

.. code-block:: python

    from buildbot.plugins import schedulers, util

    # this scheduler will create builds when a patch is uploaded to gerrit
    # but only if it is uploaded to the "main" branch
    schedulers.AnyBranchScheduler(
        name="main-precommit",
        change_filter=util.GerritChangeFilter(branch="main", eventtype="patchset-created"),
        treeStableTimer=15*60,
        builderNames=["main-precommit"])

    # this scheduler will create builds when a patch is merged in the "main" branch
    # for post-commit tests
    schedulers.AnyBranchScheduler(name="main-postcommit",
                                  change_filter=util.GerritChangeFilter("main", "ref-updated"),
                                  treeStableTimer=15*60,
                                  builderNames=["main-postcommit"])

.. bb:chsrc:: Change Hooks

.. _Change-Hooks-HTTP-Notifications:

Change Hooks (HTTP Notifications)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Buildbot already provides a web frontend, and that frontend can easily be used to receive HTTP push notifications of commits from services like GitHub.
See :ref:`Change-Hooks` for more information.

.. index: change

.. _Change-Attrs:

Changes
-------

.. py:class:: buildbot.changes.changes.Change

A :class:`Change` is an abstract way Buildbot uses to represent a single change to the source files performed by a developer.
In version control systems that support the notion of atomic check-ins, a change represents a changeset or commit.
Instances of :class:`Change` have the following attributes.

.. _Change-Attr-Who:

Who
~~~

Each :class:`Change` has a :attr:`who` attribute, which specifies which developer is responsible for the change.
This is a string which comes from a namespace controlled by the VC repository.
Frequently this means it is a username on the host which runs the repository, but not all VC systems require this.
Each :class:`StatusNotifier` will map the :attr:`who` attribute into something appropriate for their particular means of communication: an email address, an IRC handle, etc.

This ``who`` attribute is also parsed and stored into Buildbot's database (see :ref:`User-Objects`).
Currently, only ``who`` attributes in Changes from ``git`` repositories are translated into user objects, but in the future all incoming Changes will have their ``who`` parsed and stored.

.. _Change-Attr-Files:

Files
~~~~~

It also has a list of :attr:`files`, which are just the tree-relative filenames of any files that were added, deleted, or modified for this :class:`Change`.
These filenames are checked by the :func:`fileIsImportant` function of a scheduler to decide whether it should trigger a new build or not. For example, the scheduler could use the following function to only run a build if a C file was checked in:

.. code-block:: python

    def has_C_files(change):
        for name in change.files:
            if name.endswith(".c"):
                return True
        return False

Certain :class:`BuildStep`\s can also use the list of changed files to run a more targeted series of tests, e.g. the ``python_twisted.Trial`` step can run just the unit tests that provide coverage for the modified .py files instead of running the full test suite.

.. _Change-Attr-Comments:

Comments
~~~~~~~~

The Change also has a :attr:`comments` attribute, which is a string containing any checkin comments.

.. _Change-Attr-Project:

Project
~~~~~~~

The :attr:`project` attribute of a change or source stamp describes the project to which it corresponds, as a short human-readable string.
This is useful in cases where multiple independent projects are built on the same buildmaster.
In such cases, it can be used to control which builds are scheduled for a given commit, and to limit status displays to only one project.

.. _Change-Attr-Repository:

Repository
~~~~~~~~~~

This attribute specifies the repository in which this change occurred.
In the case of DVCS's, this information may be required to check out the committed source code.
However, using the repository from a change has security risks: if Buildbot is configured to blindly trust this information, then it may easily be tricked into building arbitrary source code, potentially compromising the workers and the integrity of subsequent builds.

.. _Change-Attr-Codebase:

Codebase
~~~~~~~~

This attribute specifies the codebase to which this change was made.
As described in :ref:`source stamps <Source-Stamps>` section, multiple repositories may contain the same codebase.
A change's codebase is usually determined by the :bb:cfg:`codebaseGenerator` configuration.
By default the codebase is ''; this value is used automatically for single-codebase configurations.

.. _Change-Attr-Revision:

Revision
~~~~~~~~

Each Change can have a :attr:`revision` attribute, which describes how to get a tree with a specific state: a tree which includes this Change (and all that came before it) but none that come after it.
If this information is unavailable, the :attr:`revision` attribute will be ``None``.
These revisions are provided by the :class:`ChangeSource`.

Revisions are always strings.

`CVS`
    :attr:`revision` is the seconds since the epoch as an integer.

`SVN`
    :attr:`revision` is the revision number

`Darcs`
    :attr:`revision` is a large string, the output of :command:`darcs changes --context`

`Mercurial`
    :attr:`revision` is a short string (a hash ID), the output of :command:`hg identify`

`P4`
    :attr:`revision` is the transaction number

`Git`
    :attr:`revision` is a short string (a SHA1 hash), the output of e.g.  :command:`git rev-parse`

Branches
~~~~~~~~

The Change might also have a :attr:`branch` attribute.
This indicates that all of the Change's files are in the same named branch.
The schedulers get to decide whether the branch should be built or not.

For VC systems like CVS, Git, Mercurial and Monotone the :attr:`branch` name is unrelated to the filename.
(That is, the branch name and the filename inhabit unrelated namespaces.)
For SVN, branches are expressed as subdirectories of the repository, so the file's ``repourl`` is a combination of some base URL, the branch name, and the filename within the branch.
(In a sense, the branch name and the filename inhabit the same namespace.)
Darcs branches are subdirectories of a base URL just like SVN.

`CVS`
    branch='warner-newfeature', files=['src/foo.c']

`SVN`
    branch='branches/warner-newfeature', files=['src/foo.c']

`Darcs`
    branch='warner-newfeature', files=['src/foo.c']

`Mercurial`
    branch='warner-newfeature', files=['src/foo.c']

`Git`
    branch='warner-newfeature', files=['src/foo.c']

`Monotone`
    branch='warner-newfeature', files=['src/foo.c']

Change Properties
~~~~~~~~~~~~~~~~~

A Change may have one or more properties attached to it, usually specified through the Force Build form or :bb:cmdline:`sendchange`.
Properties are discussed in detail in the :ref:`Build-Properties` section.
