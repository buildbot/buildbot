.. _Command-line-Tool:

Command-line Tool
=================

This section describes command-line tools available after buildbot
installation. Since version 0.8 the one-for-all :command:`buildbot`
command-line tool was divided into two parts namely :command:`buildbot`
and :command:`buildslave`. The last one was separated from main
command-line tool to minimize dependencies required for running a
buildslave while leaving all other functions to :command:`buildbot` tool.

Every command-line tool has a list of global options and a set of commands
which have their own options. One can run these tools in the following way:

.. code-block:: none

   buildbot [global options] command [command options]
   buildslave [global options] command [command options]

The ``buildbot`` command is used on the master, while ``buildslave`` is used on
the slave.  Global options are the same for both tools which perform the
following actions:

--help
    Print general help about available commands and global options and exit.
    All subsequent arguments are ignored.

--verbose
    Set verbose output.

--version
    Print current buildbot version and exit. All subsequent arguments are
    ignored.

You can get help on any command by specifying ``--help`` as a
command option:

.. code-block:: none

   buildbot @var{command} --help

You can also use manual pages for :command:`buildbot` and
:command:`buildslave` for quick reference on command-line options.

The remainder of this section describes each buildbot command.  See
:bb:index:`cmdline` for a full list.

buildbot
--------

The :command:`buildbot` command-line tool can be used to start or stop a
buildmaster or buildbot, and to interact with a running buildmaster.
Some of its subcommands are intended for buildmaster admins, while
some are for developers who are editing the code that the buildbot is
monitoring.

Administrator Tools
~~~~~~~~~~~~~~~~~~~

The following :command:`buildbot` sub-commands are intended for
buildmaster administrators:

.. bb:cmdline:: create-master

create-master
+++++++++++++

.. code-block:: none

    buildbot create-master -r {BASEDIR}

This creates a new directory and populates it with files that allow it to be used as a buildmaster's base directory.

You will usually want to use the :option:`-r` option to create a relocatable :file:`buildbot.tac`.
This allows you to move the master directory without editing this file.

.. bb:cmdline:: start (buildbot)

start
+++++

.. code-block:: none

    buildbot start [--nodaemon] {BASEDIR}

This starts a buildmaster which was already created in the given base directory.
The daemon is launched in the background, with events logged to a file named :file:`twistd.log`.

The :option:`--nodaemon` option instructs Buildbot to skip daemonizing.
The process will start in the foreground.
It will only return to the command-line when it is stopped.

.. bb:cmdline:: restart (buildbot)

restart
+++++++

.. code-block:: none

    buildbot restart [--nodaemon] {BASEDIR}

Restart the buildmaster.
This is equivalent to ``stop`` followed by ``start``
The :option:`--nodaemon` option has the same meaning as for ``start``.

.. bb:cmdline:: stop (buildbot)

stop
++++

.. code-block:: none

    buildbot stop {BASEDIR}

This terminates the daemon (either buildmaster or buildslave) running in the given directory.
The :option:`--clean` option shuts down the buildmaster cleanly.

.. bb:cmdline:: sighup

sighup
++++++

.. code-block:: none

    buildbot sighup {BASEDIR}

This sends a SIGHUP to the buildmaster running in the given directory, which causes it to re-read its :file:`master.cfg` file.

Developer Tools
~~~~~~~~~~~~~~~

These tools are provided for use by the developers who are working on
the code that the buildbot is monitoring.

.. bb:cmdline:: statuslog

statuslog
+++++++++

.. code-block:: none

    buildbot statuslog --master {MASTERHOST}:{PORT}

This command starts a simple text-based status client, one which just
prints out a new line each time an event occurs on the buildmaster.

The :option:`--master` option provides the location of the
:class:`buildbot.status.client.PBListener` status port, used to deliver
build information to realtime status clients. The option is always in
the form of a string, with hostname and port number separated by a
colon (:samp:`{HOSTNAME}:{PORTNUM}`). Note that this port is *not* the
same as the slaveport (although a future version may allow the same
port number to be used for both purposes). If you get an error message
to the effect of ``Failure: twisted.cred.error.UnauthorizedLogin:``,
this may indicate that you are connecting to the slaveport rather than
a :class:`PBListener` port.

The :option:`--master` option can also be provided by the
``masterstatus`` name in :file:`.buildbot/options`
(see :ref:`buildbot-config-directory`).

.. bb:cmdline:: statusgui

statusgui
+++++++++

If you have set up a :bb:status:`PBListener`, you will be able
to monitor your Buildbot using a simple Gtk+ application invoked with
the ``buildbot statusgui`` command:

.. code-block:: none

    buildbot statusgui --master {MASTERHOST}:{PORT}

This command starts a simple Gtk+-based status client, which contains a few
boxes for each Builder that change color as events occur. It uses the same
``--master`` argument and ``masterstatus`` option as the
``buildbot statuslog`` command (:bb:cmdline:`statuslog`).

.. bb:cmdline:: try

try
+++

This lets a developer to ask the question ``What would happen if I
committed this patch right now?``. It runs the unit test suite (across
multiple build platforms) on the developer's current code, allowing
them to make sure they will not break the tree when they finally
commit their changes.

The ``buildbot try`` command is meant to be run from within a
developer's local tree, and starts by figuring out the base revision
of that tree (what revision was current the last time the tree was
updated), and a patch that can be applied to that revision of the tree
to make it match the developer's copy. This ``(revision, patch)`` pair is
then sent to the buildmaster, which runs a build with that
:class:`SourceStamp`. If you want, the tool will emit status messages as the
builds run, and will not terminate until the first failure has been
detected (or the last success).

There is an alternate form which accepts a pre-made patch file
(typically the output of a command like :command:`svn diff`). This ``--diff``
form does not require a local tree to run from. See :ref:`try--diff` concerning
the ``--diff`` command option.

For this command to work, several pieces must be in place: the
:bb:sched:`Try_Jobdir` or ::bb:sched:`Try_Userpass`, as well as some client-side
configuration.

Locating the master
###################

The :command:`try` command needs to be told how to connect to the
try scheduler, and must know which of the authentication
approaches described above is in use by the buildmaster. You specify
the approach by using ``--connect=ssh`` or ``--connect=pb``
(or ``try_connect = 'ssh'`` or ``try_connect = 'pb'`` in
:file:`.buildbot/options`).

For the PB approach, the command must be given a :option:`--master`
argument (in the form :samp:`{HOST}:{PORT}`) that points to TCP port that you
picked in the :class:`Try_Userpass` scheduler. It also takes a
:option:`--username` and :option:`--passwd` pair of arguments that match
one of the entries in the buildmaster's ``userpass`` list. These
arguments can also be provided as ``try_master``,
``try_username``, and ``try_password`` entries in the
:file:`.buildbot/options` file.

For the SSH approach, the command must be given :option:`--host` and
:option:`--username`, to get to the buildmaster host. It must also be given
:option:`--jobdir`, which points to the inlet directory configured
above. The jobdir can be relative to the user's home directory, but
most of the time you will use an explicit path like
:file:`~buildbot/project/trydir`. These arguments can be provided in
:file:`.buildbot/options` as ``try_host``, ``try_username``,
``try_password``, and ``try_jobdir``.

The SSH approach also provides a :option:`--buildbotbin` argument to
allow specification of the buildbot binary to run on the
buildmaster. This is useful in the case where buildbot is installed in
a :ref:`virtualenv <Installation-in-a-Virtualenv>` on the buildmaster
host, or in other circumstances where the buildbot command is not on
the path of the user given by :option:`--username`. The
:option:`--buildbotbin` argument can be provided in
:file:`.buildbot/options` as ``try_buildbotbin``

The following command line arguments are deprecated, but retained for
backward compatibility:

--tryhost
  is replaced by :option:`--host`
--trydir
  is replaced by :option:`--jobdir`
--master
  is replaced by :option:`--masterstatus`

Likewise, the following :file:`.buildbot/options` file entries are
deprecated, but retained for backward compatibility:

 * ``try_dir`` is replaced by ``try_jobdir``
 * ``masterstatus`` is replaced by ``try_masterstatus``

Waiting for results
###################

If you provide the :option:`--wait` option (or ``try_wait = True``
in :file:`.buildbot/options`), the ``buildbot try`` command will
wait until your changes have either been proven good or bad before
exiting. Unless you use the :option:`--quiet` option (or
``try_quiet=True``), it will emit a progress message every 60
seconds until the builds have completed.

The SSH connection method does not support waiting for results.

Choosing the Builders
#####################

A trial build is performed on multiple Builders at the same time, and
the developer gets to choose which Builders are used (limited to a set
selected by the buildmaster admin with the :class:`TryScheduler`'s
``builderNames=`` argument). The set you choose will depend upon
what your goals are: if you are concerned about cross-platform
compatibility, you should use multiple Builders, one from each
platform of interest. You might use just one builder if that platform
has libraries or other facilities that allow better test coverage than
what you can accomplish on your own machine, or faster test runs.

The set of Builders to use can be specified with multiple
:option:`--builder` arguments on the command line. It can also be
specified with a single ``try_builders`` option in
:file:`.buildbot/options` that uses a list of strings to specify all
the Builder names:

    try_builders = ["full-OSX", "full-win32", "full-linux"]

If you are using the PB approach, you can get the names of the builders
that are configured for the try scheduler using the ``get-builder-names``
argument:

    buildbot try --get-builder-names --connect=pb --master=... --username=... --passwd=...

Specifying the VC system
########################

The :command:`try` command also needs to know how to take the
developer's current tree and extract the (revision, patch)
source-stamp pair. Each VC system uses a different process, so you
start by telling the :command:`try` command which VC system you are
using, with an argument like :option:`--vc=cvs` or :option:`--vc=git`.
This can also be provided as ``try_vc`` in
:file:`.buildbot/options`.

.. The order of this list comes from the end of scripts/tryclient.py

The following names are recognized: ``bzr`` ``cvs`` ``darcs`` ``hg``
``git`` ``mtn`` ``p4`` ``svn``


Finding the top of the tree
###########################

Some VC systems (notably CVS and SVN) track each directory
more-or-less independently, which means the :command:`try` command
needs to move up to the top of the project tree before it will be able
to construct a proper full-tree patch. To accomplish this, the
:command:`try` command will crawl up through the parent directories
until it finds a marker file. The default name for this marker file is
:file:`.buildbot-top`, so when you are using CVS or SVN you should
``touch .buildbot-top`` from the top of your tree before running
:command:`buildbot try`. Alternatively, you can use a filename like
:file:`ChangeLog` or :file:`README`, since many projects put one of
these files in their top-most directory (and nowhere else). To set
this filename, use ``--topfile=ChangeLog``, or set it in the
options file with ``try_topfile = 'ChangeLog'``.

You can also manually set the top of the tree with
``--topdir=~/trees/mytree``, or ``try_topdir =
'~/trees/mytree'``. If you use ``try_topdir``, in a
:file:`.buildbot/options` file, you will need a separate options file
for each tree you use, so it may be more convenient to use the
``try_topfile`` approach instead.

Other VC systems which work on full projects instead of individual
directories (Darcs, Mercurial, Git, Monotone) do not require
:command:`try` to know the top directory, so the :option:`--try-topfile`
and :option:`--try-topdir` arguments will be ignored.

If the :command:`try` command cannot find the top directory, it will
abort with an error message.

The following command line arguments are deprecated, but retained for
backward compatibility:

 * ``--try-topdir`` is replaced by :option:`--topdir`
 * ``--try-topfile`` is replaced by :option:`--topfile`

Determining the branch name
###########################

Some VC systems record the branch information in a way that ``try``
can locate it. For the others, if you are using something other than
the default branch, you will have to tell the buildbot which branch
your tree is using. You can do this with either the :option:`--branch`
argument, or a ``try_branch`` entry in the
:file:`.buildbot/options` file.

Determining the revision and patch
##################################

Each VC system has a separate approach for determining the tree's base
revision and computing a patch.

CVS
    :command:`try` pretends that the tree is up to date. It converts the
    current time into a :option:`-D` time specification, uses it as the base
    revision, and computes the diff between the upstream tree as of that
    point in time versus the current contents. This works, more or less,
    but requires that the local clock be in reasonably good sync with the
    repository.

SVN
    :command:`try` does a :command:`svn status -u` to find the latest
    repository revision number (emitted on the last line in the :samp:`Status
    against revision: {NN}` message). It then performs an :samp:`svn diff
    -r{NN}` to find out how your tree differs from the repository version,
    and sends the resulting patch to the buildmaster. If your tree is not
    up to date, this will result in the ``try`` tree being created with
    the latest revision, then *backwards* patches applied to bring it
    ``back`` to the version you actually checked out (plus your actual
    code changes), but this will still result in the correct tree being
    used for the build.

bzr
    :command:`try` does a ``bzr revision-info`` to find the base revision,
    then a ``bzr diff -r$base..`` to obtain the patch.

Mercurial
    ``hg parents --template '{node}\n'`` emits the full revision id (as opposed to
    the common 12-char truncated) which is a SHA1 hash of the current 
    revision's contents. This is used as the base revision. 
    ``hg diff`` then provides the patch relative to that
    revision. For :command:`try` to work, your working directory must only
    have patches that are available from the same remotely-available
    repository that the build process' ``source.Mercurial`` will use.

Perforce
    :command:`try` does a ``p4 changes -m1 ...`` to determine the latest
    changelist and implicitly assumes that the local tree is synced to this
    revision. This is followed by a ``p4 diff -du`` to obtain the patch.
    A p4 patch differs slightly from a normal diff. It contains full depot
    paths and must be converted to paths relative to the branch top. To convert
    the following restriction is imposed. The p4base (see :bb:chsrc:`P4Source`)
    is assumed to be ``//depot``

Darcs
    :command:`try` does a ``darcs changes --context`` to find the list
    of all patches back to and including the last tag that was made. This text
    file (plus the location of a repository that contains all these
    patches) is sufficient to re-create the tree. Therefore the contents
    of this ``context`` file *are* the revision stamp for a
    Darcs-controlled source tree.  It then does a ``darcs diff -u``
    to compute the patch relative to that revision.

Git
    ``git branch -v`` lists all the branches available in the local
    repository along with the revision ID it points to and a short summary
    of the last commit. The line containing the currently checked out
    branch begins with ``* `` (star and space) while all the others start
    with ``  `` (two spaces). :command:`try` scans for this line and extracts
    the branch name and revision from it. Then it generates a diff against
    the base revision.

.. The spaces in the previous 2 literals are non-breakable spaces
   &#160;
    
.. todo::

    I'm not sure if this actually works the way it's intended
    since the extracted base revision might not actually exist in the
    upstream repository. Perhaps we need to add a --remote option to
    specify the remote tracking branch to generate a diff against.

Monotone
    :command:`mtn automate get_base_revision_id` emits the full revision id
    which is a SHA1 hash of the current revision's contents. This is used as
    the base revision.
    :command:`mtn diff` then provides the patch relative to that
    revision.  For :command:`try` to work, your working directory must
    only have patches that are available from the same
    remotely-available repository that the build process'
    :class:`source.Monotone` will use.

patch information
#################

You can provide the :option:`--who=dev` to designate who is running the
try build. This will add the ``dev`` to the Reason field on the try
build's status web page. You can also set ``try_who = dev`` in the
:file:`.buildbot/options` file. Note that :option:`--who=dev` will not
work on version 0.8.3 or earlier masters.

Similarly, :option:`--comment=COMMENT` will specify the comment for the patch,
which is also displayed in the patch information.  The corresponding
config-file option is ``try_comment``.

Sending properties
##################

You can set properties to send with your change using either the
:option:`--property=key=value` option, which sets a single property,
or the :option:`--properties=key1=value1,key2=value2...` option,
which sets multiple comma-separated properties.
Either of these can be sepcified multiple times.
Note that the :option:`--properties` option uses commas to split on
properties, so if your property value itself contains a comma,
you'll need to use the :option:`--property` option to set it.

.. _try--diff:

try --diff
++++++++++

Sometimes you might have a patch from someone else that you want to
submit to the buildbot. For example, a user may have created a patch
to fix some specific bug and sent it to you by email. You've inspected
the patch and suspect that it might do the job (and have at least
confirmed that it doesn't do anything evil). Now you want to test it
out.

One approach would be to check out a new local tree, apply the patch,
run your local tests, then use ``buildbot try`` to run the tests on
other platforms. An alternate approach is to use the ``buildbot
try --diff`` form to have the buildbot test the patch without using a
local tree.

This form takes a :option:`--diff` argument which points to a file that
contains the patch you want to apply. By default this patch will be
applied to the TRUNK revision, but if you give the optional
:option:`--baserev` argument, a tree of the given revision will be used
as a starting point instead of TRUNK.

You can also use ``buildbot try --diff=-`` to read the patch
from :file:`stdin`.

Each patch has a ``patchlevel`` associated with it. This indicates the
number of slashes (and preceding pathnames) that should be stripped
before applying the diff. This exactly corresponds to the :option:`-p`
or :option:`--strip` argument to the :command:`patch` utility. By
default ``buildbot try --diff`` uses a patchlevel of 0, but you
can override this with the :option:`-p` argument.

When you use :option:`--diff`, you do not need to use any of the other
options that relate to a local tree, specifically :option:`--vc`,
:option:`--try-topfile`, or :option:`--try-topdir`. These options will
be ignored. Of course you must still specify how to get to the
buildmaster (with :option:`--connect`, :option:`--tryhost`, etc).

Other Tools
~~~~~~~~~~~

These tools are generally used by buildmaster administrators.

.. bb:cmdline:: sendchange

sendchange
++++++++++

This command is used to tell the buildmaster about source changes. It
is intended to be used from within a commit script, installed on the
VC server. It requires that you have a :class:`PBChangeSource`
(:bb:chsrc:`PBChangeSource`) running in the buildmaster (by being set in
``c['change_source']``).

.. code-block:: none

    buildbot sendchange --master {MASTERHOST}:{PORT} --auth {USER}:{PASS}
            --who {USER} {FILENAMES..}

The :option:`auth` option specifies the credentials to use to connect to the
master, in the form ``user:pass``.  If the password is omitted, then
sendchange will prompt for it.  If both are omitted, the old default (username
"change" and password "changepw") will be used.  Note that this password is
well-known, and should not be used on an internet-accessible port.

The :option:`master` and :option:`username` arguments can also be given in the
options file (see :ref:`buildbot-config-directory`).  There are other (optional)
arguments which can influence the ``Change`` that gets submitted:

--branch
    (or option ``branch``) This provides the (string) branch specifier. If
    omitted, it defaults to ``None``, indicating the ``default branch``. All files
    included in this Change must be on the same branch.

--category
    (or option ``category``) This provides the (string) category specifier. If
    omitted, it defaults to ``None``, indicating ``no category``. The category property
    can be used by :class:`Scheduler`\s to filter what changes they listen to.

--project
        (or option ``project``) This provides the (string) project to which this
        change applies, and defaults to ''.  The project can be used by schedulers to
        decide which builders should respond to a particular change.

--repository
    (or option ``repository``) This provides the repository from which this
    change came, and defaults to ``''``.

--revision
    This provides a revision specifier, appropriate to the VC system in use.

--revision_file
    This provides a filename which will be opened and the contents used as
    the revision specifier. This is specifically for Darcs, which uses the
    output of ``darcs changes --context`` as a revision specifier.
    This context file can be a couple of kilobytes long, spanning a couple
    lines per patch, and would be a hassle to pass as a command-line
    argument.

--property
    This parameter is used to set a property on the :class:`Change` generated by ``sendchange``.
    Properties are specified as a :samp:`{name}:{value}` pair, separated by a colon. You may
    specify many properties by passing this parameter multiple times.

--comments
    This provides the change comments as a single argument. You may want
    to use :option:`--logfile` instead.

--logfile
    This instructs the tool to read the change comments from the given
    file. If you use ``-`` as the filename, the tool will read the
    change comments from stdin.

--encoding
    Specifies the character encoding for all other parameters,
    defaulting to ``'utf8'``. 

--vc
    Specifies which VC system the Change is coming from, one of: ``cvs``,
    ``svn``, ``darcs``, ``hg``, ``bzr``, ``git``, ``mtn``, or ``p4``.
    Defaults to ``None``.

.. bb:cmdline:: debugclient

debugclient
+++++++++++

.. code-block:: none

    buildbot debugclient --master {MASTERHOST}:{PORT} --passwd {DEBUGPW}

This launches a small Gtk+/Glade-based debug tool, connecting to the
buildmaster's ``debug port``. This debug port shares the same port
number as the slaveport (see :ref:`Setting-the-PB-Port-for-Slaves`), but the
``debugPort`` is only enabled if you set a debug password in the
buildmaster's config file (see :ref:`Debug-Options`). The
:option:`--passwd` option must match the ``c['debugPassword']``
value.

:option:`--master` can also be provided in :file:`.debug/options` by the
``master`` key. :option:`--passwd` can be provided by the
``debugPassword`` key.  See :ref:`buildbot-config-directory`.

The :guilabel:`Connect` button must be pressed before any of the other
buttons will be active. This establishes the connection to the
buildmaster. The other sections of the tool are as follows:

:guilabel:`Reload .cfg`
    Forces the buildmaster to reload its :file:`master.cfg` file. This is
    equivalent to sending a SIGHUP to the buildmaster, but can be done
    remotely through the debug port. Note that it is a good idea to be
    watching the buildmaster's :file:`twistd.log` as you reload the config
    file, as any errors which are detected in the config file will be
    announced there.

:guilabel:`Rebuild .py`
    (not yet implemented). The idea here is to use Twisted's ``rebuild``
    facilities to replace the buildmaster's running code with a new
    version. Even if this worked, it would only be used by buildbot
    developers.

:guilabel:`poke IRC`
    This locates a :class:`words.IRC` status target and causes it to emit a
    message on all the channels to which it is currently connected. This
    was used to debug a problem in which the buildmaster lost the
    connection to the IRC server and did not attempt to reconnect.

:guilabel:`Commit`
    This allows you to inject a :class:`Change`, just as if a real one had been
    delivered by whatever VC hook you are using. You can set the name of
    the committed file and the name of the user who is doing the commit.
    Optionally, you can also set a revision for the change. If the
    revision you provide looks like a number, it will be sent as an
    integer, otherwise it will be sent as a string.

:guilabel:`Force Build`
    This lets you force a :class:`Builder` (selected by name) to start a build of
    the current source tree.

:guilabel:`Currently`
    (obsolete). This was used to manually set the status of the given
    :class:`Builder`, but the status-assignment code was changed in an incompatible
    way and these buttons are no longer meaningful.

.. bb:cmdline:: user

user
++++

Note that in order to use this command, you need to configure a
`CommandlineUserManager` instance in your `master.cfg` file, which is
explained in :ref:`Users-Options`.

This command allows you to manage users in buildbot's database.
No extra requirements are needed to use this command, aside from
the Buildmaster running. For details on how Buildbot manages users,
see :ref:`Concepts-Users`.

--master
    The :command:`user` command can be run virtually anywhere
    provided a location of the running buildmaster. The :option:`master`
    argument is of the form ``{MASTERHOST}:{PORT}``.

--username
    PB connection authentication that should match the arguments to
    `CommandlineUserManager`.

--passwd
    PB connection authentication that should match the arguments to
    `CommandlineUserManager`.

--op
    There are four supported values for the :option:`op` argument:
    :option:`add`, :option:`update`, :option:`remove`, and
    :option:`get`. Each are described in full in the following sections.

--bb_username
    Used with the :option:`update` option, this sets the user's username
    for web authentication in the database. It requires :option:`bb_password`
    to be set along with it.

--bb_password
    Also used with the :option:`update` option, this sets the password
    portion of a user's web authentication credentials into the database.
    The password is first encrypted prior to storage for security reasons.

--ids
    When working with users, you need to be able to refer to them by
    unique identifiers to find particular users in the database. The
    :option:`ids` option lets you specify a comma separated list of these
    identifiers for use with the :command:`user` command.

    The :option:`ids` option is used only when using :option:`remove`
    or :option:`show`.

--info
    Users are known in buildbot as a collection of attributes tied
    together by some unique identifier (see :ref:`Concepts-Users`). These
    attributes are specified in the form ``{TYPE}={VALUE}`` when
    using the :option:`info` option. These ``{TYPE}={VALUE}`` pairs
    are specified in a comma separated list, so for example:

    .. code-block:: none

        --info=svn=jschmo,git='Joe Schmo <joe@schmo.com>'

    The :option:`info` option can be specified multiple times in the
    :command:`user` command, as each specified option will be interpreted
    as a new user. Note that :option:`info` is only used with :option:`add`
    or with :option:`update`, and whenever you use :option:`update` you need
    to specify the identifier of the user you want to update. This is done
    by prepending the :option:`info` arguments with ``{ID:}``. If we were
    to update ``'jschmo'`` from the previous example, it would look like this:

    .. code-block:: none

        --info=jschmo:git='Joseph Schmo <joe@schmo.com>'

Note that :option:`--master`, :option:`--username`, :option:`--passwd`, and
:option:`--op` are always required to issue the :command:`user` command.

The :option:`--master`, :option:`--username`, and :option:`--passwd` options
can be specified in the option file with keywords :option:`user_master`,
:option:`user_username`, and :option:`user_passwd`, respectively.  If
:option:`user_master` is not specified, then :option:`master` from the options
file will be used instead.

Below are examples of how each command should look. Whenever a
:command:`user` command is successful, results will be shown
to whoever issued the command.

For :option:`add`:

.. code-block:: none

    buildbot user --master={MASTERHOST} --op=add \
            --username={USER} --passwd={USERPW} \
            --info={TYPE}={VALUE},...

For :option:`update`:

.. code-block:: none

    buildbot user --master={MASTERHOST} --op=update \
            --username={USER} --passwd={USERPW} \
            --info={ID}:{TYPE}={VALUE},...

For :option:`remove`:

.. code-block:: none

    buildbot user --master={MASTERHOST} --op=remove \
            --username={USER} --passwd={USERPW} \
            --ids={ID1},{ID2},...

For :option:`get`:

.. code-block:: none

    buildbot user --master={MASTERHOST} --op=get \
            --username={USER} --passwd={USERPW} \
            --ids={ID1},{ID2},...

A note on :option:`update`: when updating the :option:`bb_username`
and :option:`bb_password`, the :option:`info` doesn't need to have
additional ``{TYPE}={VALUE}`` pairs to update and can just take
the ``{ID}`` portion.

.. _buildbot-config-directory:

.buildbot config directory
~~~~~~~~~~~~~~~~~~~~~~~~~~

Many of the :command:`buildbot` tools must be told how to contact the
buildmaster that they interact with. This specification can be
provided as a command-line argument, but most of the time it will be
easier to set them in an ``options`` file. The :command:`buildbot`
command will look for a special directory named :file:`.buildbot`,
starting from the current directory (where the command was run) and
crawling upwards, eventually looking in the user's home directory. It
will look for a file named :file:`options` in this directory, and will
evaluate it as a Python script, looking for certain names to be set.
You can just put simple ``name = 'value'`` pairs in this file to
set the options.

For a description of the names used in this file, please see the
documentation for the individual :command:`buildbot` sub-commands. The
following is a brief sample of what this file's contents could be.

.. code-block:: none

    # for status-reading tools
    masterstatus = 'buildbot.example.org:12345'
    # for 'sendchange' or the debug port
    master = 'buildbot.example.org:18990'
    debugPassword = 'eiv7Po'

Note carefully that the names in the :file:`options` file usually do not match
the command-line option name.

``masterstatus``
    Equivalent to :option:`--master` for :bb:cmdline:`statuslog` and :bb:cmdline:`statusgui`, this
    gives the location of the :class:`client.PBListener` status port.

``master``
    Equivalent to :option:`--master` for :bb:cmdline:`debugclient` and :bb:cmdline:`sendchange`.
    This option is used for two purposes.  It is the location of the
    ``debugPort`` for ``debugclient`` and the location of the
    :class:`pb.PBChangeSource` for ```sendchange``.  Generally these are the
    same port.

``debugPassword``
    Equivalent to :option:`--passwd` for :bb:cmdline:`debugclient`.

    .. important::

        This value must match the value of :bb:cfg:`debugPassword`, used to
        protect the debug port, for the :bb:cmdline:`debugclient` command.

``username``
    Equivalent to :option:`--username` for the :bb:cmdline:`sendchange` command.

``branch``
    Equivalent to :option:`--branch` for the :bb:cmdline:`sendchange` command.

``category``
    Equivalent to :option:`--category` for the :bb:cmdline:`sendchange` command.

``try_connect``
    Equivalent to :option:`--connect`, this specifies how the :bb:cmdline:`try` command should
    deliver its request to the buildmaster. The currently accepted values are
    ``ssh`` and ``pb``.

``try_builders``
    Equivalent to :option:`--builders`, specifies which builders should be used for
    the :bb:cmdline:`try` build.

``try_vc``
    Equivalent to :option:`--vc` for :bb:cmdline:`try`, this specifies the version control
    system being used.

``try_branch``
    Equivalent to :option:`--branch`, this indicates that the current tree is on a
    non-trunk branch.

``try_topdir``

``try_topfile``
    Use ``try_topdir``, equivalent to :option:`--try-topdir`, to explicitly
    indicate the top of your working tree, or ``try_topfile``, equivalent to
    :option:`--try-topfile` to name a file that will only be found in that top-most
    directory.

``try_host``

``try_username``

``try_dir``
    When ``try_connect`` is ``ssh``, the command will use ``try_host`` for
    :option:`--tryhost`, ``try_username`` for :option:`--username`, and ``try_dir``
    for :option:`--trydir`.  Apologies for the confusing presence and absence of
    'try'.

``try_username``

``try_password``

``try_master``
    Similarly, when ``try_connect`` is ``pb``, the command will pay attention to
    ``try_username`` for :option:`--username`, ``try_password`` for
    :option:`--passwd`, and ``try_master`` for :option:`--master`.

``try_wait``

``masterstatus``
    ``try_wait`` and ``masterstatus`` (equivalent to :option:`--wait` and
    ``master``, respectively) are used to ask the :bb:cmdline:`try` command to wait for
    the requested build to complete.

buildslave
----------

:command:`buildslave` command-line tool is used for buildslave management
only and does not provide any additional functionality. One can create,
start, stop and restart the buildslave.

.. bb:cmdline:: create-slave

create-slave
~~~~~~~~~~~~

This creates a new directory and populates it with files that let it
be used as a buildslave's base directory. You must provide several
arguments, which are used to create the initial :file:`buildbot.tac`
file.

The :option:`-r` option is advisable here, just like for ``create-master``.

.. code-block:: none

    buildslave create-slave -r {BASEDIR} {MASTERHOST}:{PORT} {SLAVENAME} {PASSWORD}

The create-slave options are described in :ref:`Buildslave-Options`.

.. bb:cmdline:: start (buildslave)

start
~~~~~

This starts a buildslave which was already created in the given base
directory. The daemon is launched in the background, with events logged
to a file named :file:`twistd.log`.

.. code-block:: none

    buildslave start [--nodaemon] BASEDIR

The :option:`--nodaemon` option instructs Buildbot to skip daemonizing. The
process will start in the foreground.  It will only return to the command-line
when it is stopped.

.. bb:cmdline:: restart (buildslave)

restart
~~~~~~~

.. code-block:: none

    buildslave restart [--nodaemon] BASEDIR

This restarts a buildslave which is already running.
It is equivalent to a ``stop`` followed by a ``start``.

The :option:`--nodaemon` option has the same meaning as for ``start``.

.. bb:cmdline:: stop (buildslave)

stop
~~~~

This terminates the daemon buildslave running in the given directory.

.. code-block:: none

    buildbot stop BASEDIR

