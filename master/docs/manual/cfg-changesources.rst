.. -*- rst -*-
.. _Change-Sources:

Change Sources
--------------

A Version Control System mantains a source tree, and tells the
buildmaster when it changes. The first step of each :class:`Build` is typically
to acquire a copy of some version of this tree.

This chapter describes how the Buildbot learns about what :class:`Change`\s have
occurred. For more information on VC systems and :class:`Change`\s, see
:ref:`Version-Control-Systems`.

:class:`Change`\s can be provided by a variety of :class:`ChangeSource` types, although any given
project will typically have only a single :class:`ChangeSource` active. This section
provides a description of all available :class:`ChangeSource` types and explains how to
set up each of them.

In general, each Buildmaster watches a single source tree.  It is possible to
work around this, but true support for multi-tree builds remains elusive.

.. _Choosing-a-Change-Source:

Choosing a Change Source
~~~~~~~~~~~~~~~~~~~~~~~~

There are a variety of :class:`ChangeSource` classes available, some of which are
meant to be used in conjunction with other tools to deliver :class:`Change`
events from the VC repository to the buildmaster.

As a quick guide, here is a list of VC systems and the :class:`ChangeSource`\s
that might be useful with them. 

CVS
 * :bb:chsrc:`CVSMaildirSource` (watching mail sent by ``contrib/buildbot_cvs_mail.py`` script) 
 * :bb:chsrc:`PBChangeSource` (listening for connections from ``buildbot
   sendchange`` run in a loginfo script)
 * :bb:chsrc:`PBChangeSource` (listening for connections from a long-running
   :file:`contrib/viewcvspoll.py` polling process which examines the ViewCVS
   database directly
 * :bb:chsrc:`Change Hooks` in WebStatus

SVN
 * :bb:chsrc:`PBChangeSource` (listening for connections from
   :file:`contrib/svn_buildbot.py` run in a postcommit script)
 * :bb:chsrc:`PBChangeSource` (listening for connections from a long-running
   :file:`contrib/svn_watcher.py` or :file:`contrib/svnpoller.py` polling
   process
 * :bb:chsrc:`SVNCommitEmailMaildirSource` (watching for email sent by
   :file:`commit-email.pl`)
 * :bb:chsrc:`SVNPoller` (polling the SVN repository)
 * :bb:chsrc:`Change Hooks` in WebStatus
 * :bb:chsrc:`GoogleCodeAtomPoller` (polling the
   commit feed for a GoogleCode Git repository)

Darcs
 * :bb:chsrc:`PBChangeSource` (listening for connections from
   :file:`contrib/darcs_buildbot.py` in a commit script)
 * :bb:chsrc:`Change Hooks` in WebStatus

Mercurial
 * :bb:chsrc:`PBChangeSource` (listening for connections from
   :file:`contrib/hg_buildbot.py` run in an 'changegroup' hook)
 * :bb:chsrc:`Change Hooks` in WebStatus
 * :bb:chsrc:`PBChangeSource` (listening for connections from
   :file:`buildbot/changes/hgbuildbot.py` run as an in-process 'changegroup'
   hook)
 * :bb:chsrc:`GoogleCodeAtomPoller` (polling the
   commit feed for a GoogleCode Git repository)

Bzr (the newer Bazaar)
 * :bb:chsrc:`PBChangeSource` (listening for connections from
   :file:`contrib/bzr_buildbot.py` run in a post-change-branch-tip or commit hook)
 * :bb:chsrc:`BzrPoller` (polling the Bzr repository)
 * :bb:chsrc:`Change Hooks` in WebStatus

Git
 * :bb:chsrc:`PBChangeSource` (listening for connections from
   :file:`contrib/git_buildbot.py` run in the post-receive hook)
 * :bb:chsrc:`PBChangeSource` (listening for connections from
   :file:`contrib/github_buildbot.py`, which listens for notifications
   from GitHub)
 * :bb:chsrc:`Change Hooks` in WebStatus
 * github change hook (specifically designed for GitHub notifications,
   but requiring a publicly-accessible WebStatus)
 * :bb:chsrc:`GitPoller` (polling a remote git repository)
 * :bb:chsrc:`GoogleCodeAtomPoller` (polling the
   commit feed for a GoogleCode Git repository)


Repo/Git
 * :bb:chsrc:`GerritChangeSource` connects to Gerrit
   via SSH to get a live stream of changes

Monotone
 * :bb:chsrc:`PBChangeSource` (listening for connections from
   :file:`monotone-buildbot.lua`, which is available with monotone)

All VC systems can be driven by a :bb:chsrc:`PBChangeSource` and the ``buildbot
sendchange`` tool run from some form of commit script.  If you write an email
parsing function, they can also all be driven by a suitable :ref:`mail-parsing
source <Mail-parsing-ChangeSources>`. Additionally, handlers for web-based
notification (i.e. from GitHub) can be used with WebStatus' change_hook module.
The interface is simple, so adding your own handlers (and sharing!) should be a
breeze.

See :bb:index:`chsrc` for a full list of change sources.

.. index:: Change Sources

.. bb:cfg:: change_source

Configuring Change Sources
~~~~~~~~~~~~~~~~~~~~~~~~~~

The :bb:cfg:`change_source` configuration key holds all active
change sources for the confguration.

Most configurations have a single :class:`ChangeSource`, watching only a single
tree::

    c['change_source'] = PBChangeSource()

For more advanced configurations, the parameter can be a list of change sources::

    source1 = ...
    source2 = ...
    c['change_source'] = [ source1, source1 ]

Repository and Project
++++++++++++++++++++++

:class:`ChangeSource`\s will, in general, automatically provide the proper :attr:`repository`
attribute for any changes they produce.  For systems which operate on URL-like
specifiers, this is a repository URL. Other :class:`ChangeSource`\s adapt the concept as
necessary.

Many :class:`ChangeSource`\s allow you to specify a project, as well.  This attribute is
useful when building from several distinct codebases in the same buildmaster:
the project string can serve to differentiate the different codebases.
:class:`Scheduler`\s can filter on project, so you can configure different builders to
run for each project.

.. _Mail-parsing-ChangeSources:

Mail-parsing ChangeSources
~~~~~~~~~~~~~~~~~~~~~~~~~~

Many projects publish information about changes to their source tree
by sending an email message out to a mailing list, frequently named
:samp:`{PROJECT}-commits` or :samp:`{PROJECT}-changes`. Each message usually contains a
description of the change (who made the change, which files were
affected) and sometimes a copy of the diff. Humans can subscribe to
this list to stay informed about what's happening to the source tree.

The Buildbot can also be subscribed to a `-commits` mailing list, and
can trigger builds in response to Changes that it hears about. The
buildmaster admin needs to arrange for these email messages to arrive
in a place where the buildmaster can find them, and configure the
buildmaster to parse the messages correctly. Once that is in place,
the email parser will create Change objects and deliver them to the
Schedulers (see :ref:`Schedulers`) just like any other ChangeSource.

There are two components to setting up an email-based ChangeSource.
The first is to route the email messages to the buildmaster, which is
done by dropping them into a `maildir`. The second is to actually
parse the messages, which is highly dependent upon the tool that was
used to create them. Each VC system has a collection of favorite
change-emailing tools, and each has a slightly different format, so
each has a different parsing function. There is a separate
ChangeSource variant for each parsing function.

Once you've chosen a maildir location and a parsing function, create
the change source and put it in ``change_source`` ::

    from buildbot.changes.mail import SyncmailMaildirSource
    c['change_source'] = SyncmailMaildirSource("~/maildir-buildbot",
                                               prefix="/trunk/")

.. _Subscribing-the-Buildmaster:

Subscribing the Buildmaster
+++++++++++++++++++++++++++

The recommended way to install the buildbot is to create a dedicated
account for the buildmaster. If you do this, the account will probably
have a distinct email address (perhaps
`buildmaster@example.org`). Then just arrange for this
account's email to be delivered to a suitable maildir (described in
the next section).

If the buildbot does not have its own account, `extension addresses`
can be used to distinguish between email intended for the buildmaster
and email intended for the rest of the account. In most modern MTAs,
the e.g. `foo@example.org` account has control over every email
address at example.org which begins with "foo", such that email
addressed to `account-foo@example.org` can be delivered to a
different destination than `account-bar@example.org`. qmail
does this by using separate :file:`.qmail` files for the two destinations
(:file:`.qmail-foo` and :file:`.qmail-bar`, with :file:`.qmail`
controlling the base address and :file:`.qmail-default` controlling all
other extensions). Other MTAs have similar mechanisms.

Thus you can assign an extension address like
`foo-buildmaster@example.org` to the buildmaster, and retain
`foo@example.org` for your own use.

.. _Using-Maildirs:

Using Maildirs
++++++++++++++

A `maildir` is a simple directory structure originally developed for
qmail that allows safe atomic update without locking. Create a base
directory with three subdirectories: :file:`new`, :file:`tmp`, and :file:`cur`.
When messages arrive, they are put into a uniquely-named file (using
pids, timestamps, and random numbers) in :file:`tmp`. When the file is
complete, it is atomically renamed into :file:`new`. Eventually the
buildmaster notices the file in :file:`new`, reads and parses the
contents, then moves it into :file:`cur`. A cronjob can be used to delete
files in :file:`cur` at leisure.

Maildirs are frequently created with the :command:`maildirmake` tool,
but a simple :command:`mkdir -p ~/MAILDIR/\{cur,new,tmp\}` is pretty much
equivalent.

Many modern MTAs can deliver directly to maildirs. The usual :file:`.forward`
or :file:`.procmailrc` syntax is to name the base directory with a trailing
slash, so something like ``~/MAILDIR/``\. qmail and postfix are
maildir-capable MTAs, and procmail is a maildir-capable MDA (Mail
Delivery Agent).

Here is an example procmail config, located in :file:`~/.procmailrc`::

    # .procmailrc
    # routes incoming mail to appropriate mailboxes
    PATH=/usr/bin:/usr/local/bin
    MAILDIR=$HOME/Mail
    LOGFILE=.procmail_log
    SHELL=/bin/sh

    :0
    *
    new

If procmail is not setup on a system wide basis, then the following one-line
:file:`.forward` file will invoke it. ::

    !/usr/bin/procmail

For MTAs which cannot put files into maildirs directly, the
`safecat` tool can be executed from a :file:`.forward` file to accomplish
the same thing.

The Buildmaster uses the linux DNotify facility to receive immediate
notification when the maildir's :file:`new` directory has changed. When
this facility is not available, it polls the directory for new
messages, every 10 seconds by default.

.. _Parsing-Email-Change-Messages:

Parsing Email Change Messages
+++++++++++++++++++++++++++++

The second component to setting up an email-based :class:`ChangeSource` is to
parse the actual notices. This is highly dependent upon the VC system
and commit script in use.

A couple of common tools used to create these change emails, along with the
buildbot tools to parse them, are:

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
        http://www.selenic.com/mercurial/wiki/index.cgi/NotifyExtension

Git
    post-receive-email
        http://git.kernel.org/?p=git/git.git;a=blob;f=contrib/hooks/post-receive-email;hb=HEAD


The following sections describe the parsers available for each of
these tools.

Most of these parsers accept a ``prefix=`` argument, which is used
to limit the set of files that the buildmaster pays attention to. This
is most useful for systems like CVS and SVN which put multiple
projects in a single repository (or use repository names to indicate
branches). Each filename that appears in the email is tested against
the prefix: if the filename does not start with the prefix, the file
is ignored. If the filename *does* start with the prefix, that
prefix is stripped from the filename before any further processing is
done. Thus the prefix usually ends with a slash.

.. bb:chsrc:: CVSMaildirSource

.. _CVSMaildirSource:

CVSMaildirSource
++++++++++++++++

.. py:class:: buildbot.changes.mail.CVSMaildirSource

This parser works with the :file:`buildbot_cvs_maildir.py` script in the 
contrib directory. 

The script sends an email containing all the files submitted in
one directory. It is invoked by using the :file:`CVSROOT/loginfo` facility.

The Buildbot's :bb:chsrc:`CVSMaildirSource` knows how to parse 
these messages and turn them into Change objects. It takes two parameters, 
the directory name of the maildir root, and an optional function to create
a URL for each file. The function takes three parameters::

    file   - file name
    oldRev - old revision of the file
    newRev - new revision of the file

It must return, oldly enough, a url for the file in question. For example::

    def fileToUrl( file, oldRev, newRev ):
        return 'http://example.com/cgi-bin/cvsweb.cgi/' + file + '?rev=' + newRev

    from buildbot.changes.mail import CVSMaildirSource
    c['change_source'] = CVSMaildirSource("/home/buildbot/Mail", urlmaker=fileToUrl)

Configuration of CVS and buildbot_cvs_mail.py
#############################################

CVS must be configured to invoke the buildbot_cvs_mail.py script when files
are checked in. This is done via the CVS loginfo configuration file.

To update this, first do::

    cvs checkout CVSROOT

cd to the CVSROOT directory and edit the file loginfo, adding a line like::

    SomeModule /cvsroot/CVSROOT/buildbot_cvs_mail.py --cvsroot :ext:example.com:/cvsroot -e buildbot -P SomeModule %@{sVv@}

.. note:: For cvs version 1.12.x, the ``--path %p`` option is required.
   Version 1.11.x and 1.12.x report the directory path differently.

The above example you put the buildbot_cvs_mail.py script under /cvsroot/CVSROOT. 
It can be anywhere. Run the script with --help to see all the options.
At the very least, the 
options ``-e`` (email) and ``-P`` (project) should be specified. The line must end with ``%{sVv}``
This is expanded to the files that were modified.

Additional entries can be added to support more modules.

The following is an abreviated form of buildbot_cvs_mail.py --help::

    Usage:

        buildbot-cvs-mail [options] %@{sVv@}

    Where options are:

        --category=category
        -C
            Category for change. This becomes the Change.category attribute.
            This may not make sense to specify it here, as category is meant
            to distinguish the diffrent types of bots inside a same project,
            such as "test", "docs", "full"
        
        --cvsroot=<path>
        -c
            CVSROOT for use by buildbot slaves to checkout code.
            This becomes the Change.repository attribute. 
            Exmaple: :ext:myhost:/cvsroot
    
        --email=email
        -e email
            Email address of the buildbot.

        --fromhost=hostname
        -f hostname
            The hostname that email messages appear to be coming from.  The From:
            header of the outgoing message will look like user@@hostname.  By
            default, hostname is the machine's fully qualified domain name.

        --help / -h
            Print this text.

        -m hostname
        --mailhost=hostname
            The hostname of an available SMTP server.  The default is
            'localhost'.

        --mailport=port
            The port number of SMTP server.  The default is '25'.

        --quiet / -q
            Don't print as much status to stdout.

        --path=path
        -p path
            The path for the files in this update. This comes from the %p parameter
            in loginfo for CVS version 1.12.x. Do not use this for CVS version 1.11.x

        --project=project
        -P project
            The project for the source. Use the CVS module being modified. This 
            becomes the Change.project attribute.
        
        -R ADDR
        --reply-to=ADDR
            Add a "Reply-To: ADDR" header to the email message.

        -t
        --testing
            Construct message and send to stdout for testing

    The rest of the command line arguments are:

        %@{sVv@}
            CVS %@{sVv@} loginfo expansion.  When invoked by CVS, this will be a single
            string containing the files that are changing.

.. bb:chsrc:: SVNCommitEmailMaildirSource

.. _SVNCommitEmailMaildirSource:
    
SVNCommitEmailMaildirSource
++++++++++++++++++++++++++++

.. py:class:: buildbot.changes.mail.SVNCommitEmailMaildirSource

:bb:chsrc:`SVNCommitEmailMaildirSource` parses message sent out by the
:file:`commit-email.pl` script, which is included in the Subversion
distribution.

It does not currently handle branches: all of the Change objects that
it creates will be associated with the default (i.e. trunk) branch. ::

    from buildbot.changes.mail import SVNCommitEmailMaildirSource
    c['change_source'] = SVNCommitEmailMaildirSource("~/maildir-buildbot")

.. bb:chsrc:: BzrLaunchpadEmailMaildirSource

.. _BzrLaunchpadEmailMaildirSource:
    
BzrLaunchpadEmailMaildirSource
+++++++++++++++++++++++++++++++

.. py:class:: buildbot.changes.mail.BzrLaunchpadEmailMaildirSource

:bb:chsrc:`BzrLaunchpadEmailMaildirSource` parses the mails that are sent to
addresses that subscribe to branch revision notifications for a bzr branch
hosted on Launchpad.

The branch name defaults to :samp:`lp:{Launchpad path}`. For example
``lp:~maria-captains/maria/5.1``.

If only a single branch is used, the default branch name can be changed by
setting ``defaultBranch``.

For multiple branches, pass a dictionary as the value of the ``branchMap``
option to map specific repository paths to specific branch names (see example
below). The leading ``lp:`` prefix of the path is optional.

The ``prefix`` option is not supported (it is silently ignored). Use the
``branchMap`` and ``defaultBranch`` instead to assign changes to
branches (and just do not subscribe the buildbot to branches that are not of
interest).

The revision number is obtained from the email text. The bzr revision id is
not available in the mails sent by Launchpad. However, it is possible to set
the bzr `append_revisions_only` option for public shared repositories to
avoid new pushes of merges changing the meaning of old revision numbers. ::

    from buildbot.changes.mail import BzrLaunchpadEmailMaildirSource
    bm = { 'lp:~maria-captains/maria/5.1' : '5.1', 'lp:~maria-captains/maria/6.0' : '6.0' }
    c['change_source'] = BzrLaunchpadEmailMaildirSource("~/maildir-buildbot", branchMap = bm)

.. bb:chsrc:: PBChangeSource

.. _PBChangeSource:

PBChangeSource
~~~~~~~~~~~~~~

.. py:class:: buildbot.changes.pb.PBChangeSource

:bb:chsrc:`PBChangeSource` actually listens on a TCP port for
clients to connect and push change notices *into* the
Buildmaster. This is used by the built-in ``buildbot sendchange``
notification tool, as well as several version-control hook
scripts. This change is also useful for
creating new kinds of change sources that work on a `push` model
instead of some kind of subscription scheme, for example a script
which is run out of an email :file:`.forward` file. This ChangeSource
always runs on the same TCP port as the slaves.  It shares the same
protocol, and in fact shares the same space of "usernames", so you
cannot configure a :bb:chsrc:`PBChangeSource` with the same name as a slave.

If you have a publicly accessible slave port, and are using
:bb:chsrc:`PBChangeSource`, *you must establish a secure username and password
for the change source*.  If your sendchange credentials are known (e.g., the
defaults), then your buildmaster is susceptible to injection of arbitrary
changes, which (depending on the build factories) could lead to arbitrary code
execution on buildslaves.

The :bb:chsrc:`PBChangeSource` is created with the following arguments.

`port`
    which port to listen on. If ``None`` (which is the default), it
    shares the port used for buildslave connections.

`user` and `passwd`
    The user/passwd account information that the client program must use
    to connect. Defaults to ``change`` and ``changepw``.  Do not use
    these defaults on a publicly exposed port!

`prefix`
    The prefix to be found and stripped from filenames delivered over the
    connection, defaulting to ``None``. Any filenames which do not start with this prefix will be
    removed. If all the filenames in a given Change are removed, the that
    whole Change will be dropped. This string should probably end with a
    directory separator.
    
    This is useful for changes coming from version control systems that
    represent branches as parent directories within the repository (like
    SVN and Perforce). Use a prefix of ``trunk/`` or
    ``project/branches/foobranch/`` to only follow one branch and to get
    correct tree-relative filenames. Without a prefix, the :bb:chsrc:`PBChangeSource`
    will probably deliver Changes with filenames like :file:`trunk/foo.c`
    instead of just :file:`foo.c`. Of course this also depends upon the
    tool sending the Changes in (like :command:`buildbot sendchange`) and
    what filenames it is delivering: that tool may be filtering and
    stripping prefixes at the sending end.

The following hooks are useful for sending changes to a :bb:chsrc:`PBChangeSource`\:

.. _Mercurial-Hook:

Mercurial Hook
++++++++++++++

Since Mercurial is written in python, the hook script can invoke
Buildbot's :meth:`sendchange` function directly, rather than having to
spawn an external process. This function delivers the same sort of
changes as :command:`buildbot sendchange` and the various hook scripts in
:file:`contrib/`, so you'll need to add a :bb:chsrc:`PBChangeSource` to your
buildmaster to receive these changes.

To set this up, first choose a Mercurial repository that represents
your central `official` source tree. This will be the same
repository that your buildslaves will eventually pull from. Install
Buildbot on the machine that hosts this repository, using the same
version of python as Mercurial is using (so that the Mercurial hook
can import code from buildbot). Then add the following to the
:file:`.hg/hgrc` file in that repository, replacing the buildmaster
hostname/portnumber as appropriate for your buildbot:

.. code-block:: ini

    [hooks]
    changegroup.buildbot = python:buildbot.changes.hgbuildbot.hook
    
    [hgbuildbot]
    master = buildmaster.example.org:9987

.. note:: Mercurial lets you define multiple ``changegroup`` hooks by
   giving them distinct names, like ``changegroup.foo`` and
   ``changegroup.bar``, which is why we use ``changegroup.buildbot``
   in this example. There is nothing magical about the `buildbot`
   suffix in the hook name. The ``[hgbuildbot]`` section *is* special,
   however, as it is the only section that the buildbot hook pays
   attention to.) 

Also note that this runs as a ``changegroup`` hook, rather than as
an ``incoming`` hook. The ``changegroup`` hook is run with
multiple revisions at a time (say, if multiple revisions are being
pushed to this repository in a single :command:`hg push` command),
whereas the ``incoming`` hook is run with just one revision at a
time. The ``hgbuildbot.hook`` function will only work with the
``changegroup`` hook.

If the buildmaster :bb:chsrc:`PBChangeSource` is configured to require
sendchange credentials then you can set these with the ``auth``
parameter. When this parameter is not set it defaults to
``change:changepw``, which are the defaults for the ``user`` and
``password`` values of a ``PBChangeSource`` which doesn't require
authentication. 

.. code-block:: ini

    [hgbuildbot]
    master = buildmaster.example.org:9987
    auth = clientname:supersecret

You can set this parameter in either the global :file:`/etc/mercurial/hgrc`,
your personal :file:`~/.hgrc` file or the repository local :file:`.hg/hgrc`
file. But since this value is stored in plain text, you must make sure that
it can only be read by those users that need to know the authentication
credentials.

The ``[hgbuildbot]`` section has two other parameters that you
might specify, both of which control the name of the branch that is
attached to the changes coming from this hook.

One common branch naming policy for Mercurial repositories is to use
it just like Darcs: each branch goes into a separate repository, and
all the branches for a single project share a common parent directory.
For example, you might have :file:`/var/repos/{PROJECT}/trunk/` and
:file:`/var/repos/{PROJECT}/release`. To use this style, use the
``branchtype = dirname`` setting, which simply uses the last
component of the repository's enclosing directory as the branch name:

.. code-block:: ini

    [hgbuildbot]
    master = buildmaster.example.org:9987
    branchtype = dirname

Another approach is to use Mercurial's built-in branches (the kind
created with :command:`hg branch` and listed with :command:`hg
branches`). This feature associates persistent names with particular
lines of descent within a single repository. (note that the buildbot
``source.Mercurial`` checkout step does not yet support this kind
of branch). To have the commit hook deliver this sort of branch name
with the Change object, use ``branchtype = inrepo``:

.. code-block:: ini

    [hgbuildbot]
    master = buildmaster.example.org:9987
    branchtype = inrepo

Finally, if you want to simply specify the branchname directly, for
all changes, use ``branch = BRANCHNAME``. This overrides
``branchtype``:

.. code-block:: ini

    [hgbuildbot]
    master = buildmaster.example.org:9987
    branch = trunk

If you use ``branch=`` like this, you'll need to put a separate
:file:`.hgrc` in each repository. If you use ``branchtype=``, you may be
able to use the same :file:`.hgrc` for all your repositories, stored in
:file:`~/.hgrc` or :file:`/etc/mercurial/hgrc`.

As twisted needs to hook some Signals, and that some web server are
strictly forbiding that, the parameter ``fork`` in the
``[hgbuildbot]`` section will instruct mercurial to fork before
sending the change request. Then as the created process will be of short
life, it is considered as safe to disable the signal restriction in
the Apache setting like that ``WSGIRestrictSignal Off``. Refer to the
documentation of your web server for other way to do the same.

The ``category`` parameter sets the category for any changes generated from
the hook.  Likewise, the ``project`` parameter sets the project.  Changes'
``repository`` attributes are formed from the Mercurial repo path by
stripping ``strip`` slashes.

.. _Bzr-Hook:

Bzr Hook
++++++++

Bzr is also written in Python, and the Bzr hook depends on Twisted to send the
changes.

To install, put :file:`contrib/bzr_buildbot.py` in one of your plugins
locations a bzr plugins directory (e.g.,
:file:`~/.bazaar/plugins`). Then, in one of your bazaar conf files (e.g.,
:file:`~/.bazaar/locations.conf`), set the location you want to connect with buildbot
with these keys:

  * ``buildbot_on``
    one of 'commit', 'push, or 'change'. Turns the plugin on to report changes via
    commit, changes via push, or any changes to the trunk. 'change' is
    recommended.

  * ``buildbot_server``
    (required to send to a buildbot master) the URL of the buildbot master to
    which you will connect (as of this writing, the same server and port to which
    slaves connect).

  * ``buildbot_port``
    (optional, defaults to 9989) the port of the buildbot master to which you will
    connect (as of this writing, the same server and port to which slaves connect)

  * ``buildbot_pqm``
    (optional, defaults to not pqm) Normally, the user that commits the revision
    is the user that is responsible for the change. When run in a pqm (Patch Queue
    Manager, see https://launchpad.net/pqm) environment, the user that commits is
    the Patch Queue Manager, and the user that committed the *parent* revision is
    responsible for the change. To turn on the pqm mode, set this value to any of
    (case-insensitive) "Yes", "Y", "True", or "T".

  * ``buildbot_dry_run``
    (optional, defaults to not a dry run) Normally, the post-commit hook will
    attempt to communicate with the configured buildbot server and port. If this
    parameter is included and any of (case-insensitive) "Yes", "Y", "True", or
    "T", then the hook will simply print what it would have sent, but not attempt
    to contact the buildbot master.

  * ``buildbot_send_branch_name``
    (optional, defaults to not sending the branch name) If your buildbot's bzr
    source build step uses a repourl, do *not* turn this on. If your buildbot's
    bzr build step uses a baseURL, then you may set this value to any of
    (case-insensitive) "Yes", "Y", "True", or "T" to have the buildbot master
    append the branch name to the baseURL.

.. note:: The bzr smart server (as of version 2.2.2) doesn't know how
   to resolve ``bzr://`` urls into absolute paths so any paths in
   ``locations.conf`` won't match, hence no change notifications
   will be sent to Buildbot. Setting configuration parameters globally
   or in-branch might still work. When buildbot no longer has a
   hardcoded password, it will be a configuration option here as well.

Here's a simple example that you might have in your
:file:`~/.bazaar/locations.conf`\.

.. code-block:: ini

    [chroot-*:///var/local/myrepo/mybranch]
    buildbot_on = change
    buildbot_server = localhost

.. bb:chsrc:: P4Source

.. _P4Source:
    
P4Source
~~~~~~~~

The :bb:chsrc:`P4Source` periodically polls a `Perforce <http://www.perforce.com/>`_
depot for changes. It accepts the following arguments:

``p4base``
    The base depot path to watch, without the trailing '/...'.

``p4port``
    The Perforce server to connect to (as :samp:`{host}:{port}`).

``p4user``
    The Perforce user.

``p4passwd``
    The Perforce password.

``p4bin``
    An optional string parameter. Specify the location of the perforce command
    line binary (p4).  You only need to do this if the perforce binary is not
    in the path of the buildbot user.  Defaults to `p4`.

``split_file``
    A function that maps a pathname, without the leading ``p4base``, to a
    (branch, filename) tuple. The default just returns ``(None, branchfile)``,
    which effectively disables branch support. You should supply a function
    which understands your repository structure.

``pollinterval``
    How often to poll, in seconds. Defaults to 600 (10 minutes).

``histmax``
    The maximum number of changes to inspect at a time. If more than this
    number occur since the last poll, older changes will be silently
    ignored.

``encoding``
    The character encoding of ``p4``\'s output.  This defaults to "utf8", but
    if your commit messages are in another encoding, specify that here.

Example
+++++++

This configuration uses the :envvar:`P4PORT`, :envvar:`P4USER`, and :envvar:`P4PASSWD`
specified in the buildmaster's environment. It watches a project in which the
branch name is simply the next path component, and the file is all path
components after. ::

    from buildbot.changes import p4poller
    s = p4poller.P4Source(p4base='//depot/project/',
                          split_file=lambda branchfile: branchfile.split('/',1),
                         )
    c['change_source'] = s

.. bb:chsrc:: BonsaiPoller

.. _BonsaiPoller:
    
BonsaiPoller
~~~~~~~~~~~~

The :bb:chsrc:`BonsaiPoller` periodically polls a Bonsai server. This is a
CGI script accessed through a web server that provides information
about a CVS tree, for example the Mozilla bonsai server at
http://bonsai.mozilla.org. Bonsai servers are usable by both
humans and machines. In this case, the buildbot's change source forms
a query which asks about any files in the specified branch which have
changed since the last query.


:bb:chsrc:`BonsaiPoller` accepts the following arguments:

``bonsaiURL``
    The base URL of the Bonsai server, e.g., ``http://bonsai.mozilla.org``

``module``
    The module to look for changes in. Commonly this is ``all``.

``branch``
    The branch to look for changes in.  This will appear in the
    ``branch`` field of the resulting change objects.

``tree``
    The tree to look for changes in.  Commonly this is ``all``.

``cvsroot``
    The CVS root of the repository.  Usually this is ``/cvsroot``.

``pollInterval``
    The time (in seconds) between queries for changes.

``project``
    The project name to attach to all change objects produced by this
    change source.

.. bb:chsrc:: SVNPoller

.. _SVNPoller:

SVNPoller
~~~~~~~~~

.. py:class:: buildbot.changes.svnpoller.SVNPoller

The :bb:chsrc:`SVNPoller` is a ChangeSource
which periodically polls a `Subversion <http://subversion.tigris.org/>`_
repository for new revisions, by running the ``svn log``
command in a subshell. It can watch a single branch or multiple
branches.

:bb:chsrc:`SVNPoller` accepts the following arguments:

``svnurl``
    The base URL path to watch, like
    ``svn://svn.twistedmatrix.com/svn/Twisted/trunk``, or
    ``http://divmod.org/svn/Divmo/``, or even
    ``file:///home/svn/Repository/ProjectA/branches/1.5/``. This must
    include the access scheme, the location of the repository (both the
    hostname for remote ones, and any additional directory names necessary
    to get to the repository), and the sub-path within the repository's
    virtual filesystem for the project and branch of interest.
    
    The :bb:chsrc:`SVNPoller` will only pay attention to files inside the
    subdirectory specified by the complete svnurl.

``split_file``
    A function to convert pathnames into ``(branch, relative_pathname)``
    tuples. Use this to explain your repository's branch-naming policy to
    :bb:chsrc:`SVNPoller`. This function must accept a single string and return
    a two-entry tuple. There are a few utility functions in
    :mod:`buildbot.changes.svnpoller` that can be used as a
    :meth:`split_file` function, see below for details.
    
    The default value always returns ``(None, path)``, which indicates that
    all files are on the trunk.
    
    Subclasses of :bb:chsrc:`SVNPoller` can override the :meth:`split_file`
    method instead of using the ``split_file=`` argument.

``project``
    Set the name of the project to be used for the :bb:chsrc:`SVNPoller`.
    This will then be set in any changes generated by the :bb:chsrc:`SVNPoller`,
    and can be used in a Change Filter for triggering particular builders.

``svnuser``
    An optional string parameter. If set, the :option:`--user` argument will
    be added to all :command:`svn` commands. Use this if you have to
    authenticate to the svn server before you can do :command:`svn info` or
    :command:`svn log` commands.

``svnpasswd``
    Like ``svnuser``, this will cause a :option:`--password` argument to
    be passed to all :command:`svn` commands.

``pollinterval``
    How often to poll, in seconds. Defaults to 600 (checking once every 10
    minutes). Lower this if you want the buildbot to notice changes
    faster, raise it if you want to reduce the network and CPU load on
    your svn server. Please be considerate of public SVN repositories by
    using a large interval when polling them.

``histmax``
    The maximum number of changes to inspect at a time. Every ``pollinterval``
    seconds, the :bb:chsrc:`SVNPoller` asks for the last HISTMAX changes and
    looks through them for any ones it does not already know about. If
    more than ``histmax`` revisions have been committed since the last poll,
    older changes will be silently ignored. Larger values of ``histmax`` will
    cause more time and memory to be consumed on each poll attempt.
    ``histmax`` defaults to 100.

``svnbin``
    This controls the :command:`svn` executable to use. If subversion is
    installed in a weird place on your system (outside of the
    buildmaster's :envvar:`PATH`), use this to tell :bb:chsrc:`SVNPoller` where
    to find it. The default value of `svn` will almost always be
    sufficient.

``revlinktmpl``
    This parameter allows a link to be provided for each revision (for example,
    to websvn or viewvc).  These links appear anywhere changes are shown, such
    as on build or change pages.  The proper form for this parameter is an URL
    with the portion that will substitute for a revision number replaced by
    ''%s''.  For example, ``'http://myserver/websvn/revision.php?rev=%s'``
    could be used to cause revision links to be created to a websvn repository
    viewer.

``cachepath``
    If specified, buildbot will cache processed revisions between
    restarts. This means you don't miss changes that were committed if
    the master is down for any reason.


Branches
++++++++

Each source file that is tracked by a Subversion repository has a
fully-qualified SVN URL in the following form:
:samp:`({REPOURL})({PROJECT-plus-BRANCH})({FILEPATH})`. When you create the
:bb:chsrc:`SVNPoller`, you give it a ``svnurl`` value that includes all
of the :samp:`{REPOURL}` and possibly some portion of the :samp:`{PROJECT-plus-BRANCH}`
string. The :bb:chsrc:`SVNPoller` is responsible for producing Changes that
contain a branch name and a :samp:`{FILEPATH}` (which is relative to the top of
a checked-out tree). The details of how these strings are split up
depend upon how your repository names its branches.

PROJECT/BRANCHNAME/FILEPATH repositories
########################################

One common layout is to have all the various projects that share a
repository get a single top-level directory each. Then under a given
project's directory, you get two subdirectories, one named :file:`trunk`
and another named :file:`branches`. Under :file:`branches` you have a bunch of
other directories, one per branch, with names like :file:`1.5.x` and
:file:`testing`. It is also common to see directories like :file:`tags` and
:file:`releases` next to :file:`branches` and :file:`trunk`.

For example, the Twisted project has a subversion server on
``svn.twistedmatrix.com`` that hosts several sub-projects. The
repository is available through a SCHEME of ``svn:``. The primary
sub-project is Twisted, of course, with a repository root of
``svn://svn.twistedmatrix.com/svn/Twisted``. Another sub-project is
Informant, with a root of
``svn://svn.twistedmatrix.com/svn/Informant``, etc. Inside any
checked-out Twisted tree, there is a file named :file:`bin/trial` (which is
used to run unit test suites).

The trunk for Twisted is in
`svn://svn.twistedmatrix.com/svn/Twisted/trunk`, and the
fully-qualified SVN URL for the trunk version of :command:`trial` would be
`svn://svn.twistedmatrix.com/svn/Twisted/trunk/bin/trial`. The same
SVNURL for that file on a branch named `1.5.x` would be
`svn://svn.twistedmatrix.com/svn/Twisted/branches/1.5.x/bin/trial`.

To set up a :bb:chsrc:`SVNPoller` that watches the Twisted trunk (and
nothing else), we would use the following::

    from buildbot.changes.svnpoller import SVNPoller
    c['change_source'] = SVNPoller("svn://svn.twistedmatrix.com/svn/Twisted/trunk")

In this case, every Change that our :bb:chsrc:`SVNPoller` produces will
have ``.branch=None``, to indicate that the Change is on the trunk.
No other sub-projects or branches will be tracked.

If we want our ChangeSource to follow multiple branches, we have to do
two things. First we have to change our ``svnurl=`` argument to
watch more than just ``.../Twisted/trunk``. We will set it to
``.../Twisted`` so that we'll see both the trunk and all the branches.
Second, we have to tell :bb:chsrc:`SVNPoller` how to split the
:samp:`({PROJECT-plus-BRANCH})({FILEPATH})` strings it gets from the repository
out into :samp:`({BRANCH})` and :samp:`({FILEPATH})` pairs.

We do the latter by providing a :meth:`split_file` function. This function
is responsible for splitting something like
``branches/1.5.x/bin/trial`` into ``branch='branches/1.5.x'`` and
``filepath='bin/trial'``. This function is always given a string
that names a file relative to the subdirectory pointed to by the
:bb:chsrc:`SVNPoller`\'s ``svnurl=`` argument. It is expected to return a
:samp:`({BRANCHNAME}, {FILEPATH})` tuple (in which :samp:`{FILEPATH}` is relative to the
branch indicated), or ``None`` to indicate that the file is outside any
project of interest.

(note that we want to see ``branches/1.5.x`` rather than just
``1.5.x`` because when we perform the SVN checkout, we will probably
append the branch name to the ``baseURL``, which requires that we keep the
``branches`` component in there. Other VC schemes use a different
approach towards branches and may not require this artifact.)

If your repository uses this same :samp:`{PROJECT}/{BRANCH}/{FILEPATH}` naming
scheme, the following function will work::

    def split_file_branches(path):
        pieces = path.split('/')
        if pieces[0] == 'trunk':
            return (None, '/'.join(pieces[1:]))
        elif pieces[0] == 'branches':
            return ('/'.join(pieces[0:2]),
                    '/'.join(pieces[2:]))
        else:
            return None

This function is provided as
:meth:`buildbot.changes.svnpoller.split_file_branches` for your
convenience. So to have our Twisted-watching :bb:chsrc:`SVNPoller` follow
multiple branches, we would use this::

    from buildbot.changes.svnpoller import SVNPoller, split_file_branches
    c['change_source'] = SVNPoller("svn://svn.twistedmatrix.com/svn/Twisted",
                                   split_file=split_file_branches)

Changes for all sorts of branches (with names like ``branches/1.5.x``,
and ``None`` to indicate the trunk) will be delivered to the Schedulers.
Each Scheduler is then free to use or ignore each branch as it sees
fit.

BRANCHNAME/PROJECT/FILEPATH repositories
########################################

Another common way to organize a Subversion repository is to put the
branch name at the top, and the projects underneath. This is
especially frequent when there are a number of related sub-projects
that all get released in a group.

For example, `Divmod.org <http://Divmod.org>`_ hosts a project named `Nevow` as well as one
named `Quotient`. In a checked-out Nevow tree there is a directory
named `formless` that contains a python source file named
:file:`webform.py`. This repository is accessible via webdav (and thus
uses an `http:` scheme) through the divmod.org hostname. There are
many branches in this repository, and they use a
:samp:`({BRANCHNAME})/({PROJECT})` naming policy.

The fully-qualified SVN URL for the trunk version of :file:`webform.py` is
``http://divmod.org/svn/Divmod/trunk/Nevow/formless/webform.py``.
You can do an :command:`svn co` with that URL and get a copy of the latest
version. The 1.5.x branch version of this file would have a URL of
``http://divmod.org/svn/Divmod/branches/1.5.x/Nevow/formless/webform.py``.
The whole Nevow trunk would be checked out with
``http://divmod.org/svn/Divmod/trunk/Nevow``, while the Quotient
trunk would be checked out using
``http://divmod.org/svn/Divmod/trunk/Quotient``.

Now suppose we want to have an :bb:chsrc:`SVNPoller` that only cares about
the Nevow trunk. This case looks just like the
:samp:`{PROJECT}/{BRANCH}` layout
described earlier::

    from buildbot.changes.svnpoller import SVNPoller
    c['change_source'] = SVNPoller("http://divmod.org/svn/Divmod/trunk/Nevow")

But what happens when we want to track multiple Nevow branches? We
have to point our ``svnurl=`` high enough to see all those
branches, but we also don't want to include Quotient changes (since
we're only building Nevow). To accomplish this, we must rely upon the
:meth:`split_file` function to help us tell the difference between
files that belong to Nevow and those that belong to Quotient, as well
as figuring out which branch each one is on. ::

    from buildbot.changes.svnpoller import SVNPoller
    c['change_source'] = SVNPoller("http://divmod.org/svn/Divmod",
                                   split_file=my_file_splitter)

The :meth:`my_file_splitter` function will be called with
repository-relative pathnames like:

:file:`trunk/Nevow/formless/webform.py`
    This is a Nevow file, on the trunk. We want the Change that includes this
    to see a filename of :file:`formless/webform.py`, and a branch of
    ``None``

:file:`branches/1.5.x/Nevow/formless/webform.py`
    This is a Nevow file, on a branch. We want to get
    ``branch='branches/1.5.x'`` and ``filename='formless/webform.py'``.

:file:`trunk/Quotient/setup.py`
    This is a Quotient file, so we want to ignore it by having
    :meth:`my_file_splitter` return ``None``.

:file:`branches/1.5.x/Quotient/setup.py`
    This is also a Quotient file, which should be ignored.

The following definition for :meth:`my_file_splitter` will do the job::

    def my_file_splitter(path):
        pieces = path.split('/')
        if pieces[0] == 'trunk':
            branch = None
            pieces.pop(0) # remove 'trunk'
        elif pieces[0] == 'branches':
            pieces.pop(0) # remove 'branches'
            # grab branch name
            branch = 'branches/' + pieces.pop(0)
        else:
            return None # something weird
        projectname = pieces.pop(0)
        if projectname != 'Nevow':
            return None # wrong project
        return (branch, '/'.join(pieces))

.. bb:chsrc:: BzrPoller

.. _Bzr-Poller:
        
Bzr Poller
~~~~~~~~~~

If you cannot insert a Bzr hook in the server, you can use the Bzr Poller. To
use, put :file:`contrib/bzr_buildbot.py` somewhere that your buildbot
configuration can import it. Even putting it in the same directory as the :file:`master.cfg`
should work. Install the poller in the buildbot configuration as with any
other change source. Minimally, provide a URL that you want to poll (``bzr://``,
``bzr+ssh://``, or ``lp:``), though make sure the buildbot user has necessary
privileges. You may also want to specify these optional values.

``poll_interval``
    The number of seconds to wait between polls.  Defaults to 10 minutes.

``branch_name``
    Any value to be used as the branch name. Defaults to None, or specify a
    string, or specify the constants from :file:`bzr_buildbot.py`
    ``SHORT`` or ``FULL`` to
    get the short branch name or full branch address.

``blame_merge_author``
    normally, the user that commits the revision is the user that is responsible
    for the change. When run in a pqm (Patch Queue Manager, see
    https://launchpad.net/pqm) environment, the user that commits is the Patch
    Queue Manager, and the user that committed the merged, *parent* revision is
    responsible for the change. set this value to ``True`` if this is pointed against
    a PQM-managed branch.

.. bb:chsrc:: GitPoller

.. _GitPoller:
    
GitPoller
~~~~~~~~~

If you cannot take advantage of post-receive hooks as provided by
:file:`contrib/git_buildbot.py` for example, then you can use the :bb:chsrc:`GitPoller`.

The :bb:chsrc:`GitPoller` periodically fetches from a remote git repository and
processes any changes. It requires its own working directory for operation, which
can be specified via the ``workdir`` property. By default a temporary directory will
be used.

The :bb:chsrc:`GitPoller` only works with git ``1.7`` and up, out of the
box.  If you're using earlier versions of git, you can get things to
work by manually creating an empty repository in
:samp:`{tempdir}/gitpoller_work``.

:bb:chsrc:`GitPoller` accepts the following arguments:

``repourl``
    the git-url that describes the remote repository, e.g.
    ``git@example.com:foobaz/myrepo.git``
    (see the :command:`git fetch` help for more info on git-url formats)

``branch``
    the desired branch to fetch, will default to ``'master'``

``workdir``
    the directory where the poller should keep its local repository. will
    default to :samp:`{tempdir}/gitpoller_work`, which is probably not
    what you want.  If this is a relative path, it will be interpreted
    relative to the master's basedir.

                
``pollinterval``
    interval in seconds between polls, default is 10 minutes

``gitbin``
    path to the git binary, defaults to just ``'git'``

``fetch_refspec``
    One or more refspecs to use when fetching updates for the
    repository. By default, the :bb:chsrc:`GitPoller` will simply fetch
    all refs. If your repository is large enough that this would be
    unwise (or active enough on irrelevant branches that it'd be a
    waste of time to fetch them all), you may wish to specify only a
    certain refs to be updated. (A single refspec may be passed as a
    string, or multiple refspecs may be passed as a list or set of
    strings.)

``category``
    Set the category to be used for the changes produced by the
    :bb:chsrc:`GitPoller`. This will then be set in any changes generated
    by the :bb:chsrc:`GitPoller`, and can be used in a Change Filter for
    triggering particular builders.

``project``
    Set the name of the project to be used for the
    :bb:chsrc:`GitPoller`. This will then be set in any changes generated
    by the ``GitPoller``, and can be used in a Change Filter for
    triggering particular builders.

``usetimestamps``
    parse each revision's commit timestamp (default is ``True``),
    or ignore it in favor of the current time (so recently processed
    commits appear together in the waterfall page) 

``encoding``
    Set encoding will be used to parse author's name and commit
    message. Default encoding is ``'utf-8'``. This will not be
    applied to file names since git will translate non-ascii file
    names to unreadable escape sequences.

Example
+++++++

::
    
    from buildbot.changes.gitpoller import GitPoller
    c['change_source'] = GitPoller('git@@example.com:foobaz/myrepo.git',
                                   branch='great_new_feature',
                                   workdir='/home/buildbot/gitpoller_workdir')

.. bb:chsrc:: GerritChangeSource

.. _GerritChangeSource:

GerritChangeSource
~~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.changes.gerritchangesource.GerritChangeSource

The :bb:chsrc:`GerritChangeSource` class connects to a Gerrit server by its SSH
interface and uses its event source mechanism,
`gerrit stream-events <http://gerrit.googlecode.com/svn/documentation/2.1.6/cmd-stream-events.html>`_.

This class adds a change to the buildbot system for each of the following events:

``patchset-created``
    A change is proposed for review. Automatic checks like
    :file:`checkpatch.pl` can be automatically triggered. Beware of
    what kind of automatic task you trigger. At this point, no trusted
    human has reviewed the code, and a patch could be specially
    crafted by an attacker to compromise your buildslaves. 

``ref-updated``
    A change has been merged into the repository. Typically, this kind
    of event can lead to a complete rebuild of the project, and upload
    binaries to an incremental build results server.

This class will populate the property list of the triggered build with the info
received from Gerrit server in JSON format.

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

Example
+++++++

::

    from buildbot.changes.gerritchangesource import GerritChangeSource
    c['change_source'] = GerritChangeSource(gerrit_server, gerrit_user)


see 
:file:`master/docs/examples/repo_gerrit.cfg` in the Buildbot
distribution for an example setup of :bb:chsrc:`GerritChangeSource`.

.. bb:chsrc:: Change Hooks

.. _Change-Hooks-HTTP-Notifications:

Change Hooks (HTTP Notifications)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Buildbot already provides a web frontend, and that frontend can easily be used
to receive HTTP push notifications of commits from services like GitHub.  See
:ref:`Change-Hooks` for more information.

.. bb:chsrc:: GoogleCodeAtomPoller

.. _GoogleCodeAtomPoller:
                                   
GoogleCodeAtomPoller
~~~~~~~~~~~~~~~~~~~~

The :bb:chsrc:`GoogleCodeAtomPoller` periodically polls a Google Code Project's
commit feed for changes. Works on SVN, Git, and Mercurial repositories. Branches
are not understood (yet). It accepts the following arguments:

``feedurl``
    The commit Atom feed URL of the GoogleCode repository (MANDATORY)

``pollinterval`` 
    Polling frequency for the feed (in seconds). Default is 1 hour (OPTIONAL)


Example
+++++++

To poll the Ostinato project's commit feed every 3 hours, use ::

    from contrib.googlecode_atom import GoogleCodeAtomPoller
    poller = GoogleCodeAtomPoller(
        feedurl="http://code.google.com/feeds/p/ostinato/hgchanges/basic",
        pollinterval=10800) 
    c['change_source'] = [ poller ]


