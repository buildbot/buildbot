This section describes command-line tools available after buildbot
installation. Since version 0.8 the one-for-all @command{buildbot}
command-line tool was divided into two parts namely @command{buildbot}
and @command{buildslave}. The last one was separated from main
command-line tool to minimize dependencies required for running a
buildslave while leaving all other functions to @command{buildbot} tool.

Every command-line tool has a list of global options and a set of commands
which have their own options. One can run these tools in the following way:

@example
buildbot [global options] @var{command} [command options]
@end example

Global options are the same for both tools which perform the following
actions:
@table @code

@item @code{--help}
Print general help about available commands and global options and exit.
All subsequent arguments are ignored.

@item @code{--verbose}
Set verbose output.

@item @code{--version}
Print current buildbot version and exit. All subsequent arguments are
ignored.
@end table

One can also get help on any command by specifying @var{--help} as a
command option:

@example
buildbot @var{command} --help
@end example

You can also use manual pages for @command{buildbot} and
@command{buildslave} for quick reference on command-line options.

@menu
* buildbot::
* buildslave::
@end menu

@node buildbot
@section buildbot

The @command{buildbot} command-line tool can be used to start or stop a
buildmaster and to interact with a running buildmaster. Some of its
subcommands are intended for buildmaster admins, while some are for
developers who are editing the code that the buildbot is monitoring.

@menu
* Administrator Tools::
* Developer Tools::
* Other Tools::
* .buildbot config directory::
@end menu

@node Administrator Tools
@subsection Administrator Tools

The following @command{buildbot} sub-commands are intended for
buildmaster administrators:

@menu
* create-master::
* start: start (buildbot).
* stop: stop (buildbot).
* sighup::
@end menu

@node create-master
@subsubsection create-master

This creates a new directory and populates it with files that allow it
to be used as a buildmaster's base directory.

You will usually want to use the @code{-r} option to create a relocatable
@code{buildbot.tac}.  This allows you to move the master directory without
editing this file.

@example
buildbot create-master -r BASEDIR
@end example

@node start (buildbot)
@subsubsection start

This starts a buildmaster which was already created in the given base
directory. The daemon is launched in the background, with events logged
to a file named @file{twistd.log}.

@example
buildbot start BASEDIR
@end example

@node stop (buildbot)
@subsubsection stop

This terminates the buildmaster running in the given directory.

@example
buildbot stop BASEDIR
@end example

@node sighup
@subsubsection sighup

This sends a SIGHUP to the buildmaster running in the given directory,
which causes it to re-read its @file{master.cfg} file.

@example
buildbot sighup BASEDIR
@end example

@node Developer Tools
@subsection Developer Tools

These tools are provided for use by the developers who are working on
the code that the buildbot is monitoring.

@menu
* statuslog::
* statusgui::
* try::
@end menu

@node statuslog
@subsubsection statuslog

@example
buildbot statuslog --master @var{MASTERHOST}:@var{PORT}
@end example

This command starts a simple text-based status client, one which just
prints out a new line each time an event occurs on the buildmaster.

The @option{--master} option provides the location of the
@code{buildbot.status.client.PBListener} status port, used to deliver
build information to realtime status clients. The option is always in
the form of a string, with hostname and port number separated by a
colon (@code{HOSTNAME:PORTNUM}). Note that this port is @emph{not} the
same as the slaveport (although a future version may allow the same
port number to be used for both purposes). If you get an error message
to the effect of ``Failure: twisted.cred.error.UnauthorizedLogin:'',
this may indicate that you are connecting to the slaveport rather than
a @code{PBListener} port.

The @option{--master} option can also be provided by the
@code{masterstatus} name in @file{.buildbot/options} (@pxref{.buildbot
config directory}).

@node statusgui
@subsubsection statusgui

@cindex statusgui

If you have set up a PBListener (@pxref{PBListener}), you will be able
to monitor your Buildbot using a simple Gtk+ application invoked with
the @code{buildbot statusgui} command:

@example
buildbot statusgui --master @var{MASTERHOST}:@var{PORT}
@end example

This command starts a simple Gtk+-based status client, which contains a few
boxes for each Builder that change color as events occur. It uses the same
@option{--master} argument and @code{masterstatus} option as the
@command{buildbot statuslog} command (@pxref{statuslog}).

@node try
@subsubsection try

This lets a developer to ask the question ``What would happen if I
committed this patch right now?''. It runs the unit test suite (across
multiple build platforms) on the developer's current code, allowing
them to make sure they will not break the tree when they finally
commit their changes.

The @command{buildbot try} command is meant to be run from within a
developer's local tree, and starts by figuring out the base revision
of that tree (what revision was current the last time the tree was
updated), and a patch that can be applied to that revision of the tree
to make it match the developer's copy. This (revision, patch) pair is
then sent to the buildmaster, which runs a build with that
SourceStamp. If you want, the tool will emit status messages as the
builds run, and will not terminate until the first failure has been
detected (or the last success).

There is an alternate form which accepts a pre-made patch file
(typically the output of a command like 'svn diff'). This ``--diff''
form does not require a local tree to run from. See @xref{try}, concerning
the ``--diff'' command option.

For this command to work, several pieces must be in place: the @xref{Try
Schedulers}, as well as some client-side configuration.

@heading locating the master

The @command{try} command needs to be told how to connect to the
try scheduler, and must know which of the authentication
approaches described above is in use by the buildmaster. You specify
the approach by using @option{--connect=ssh} or @option{--connect=pb}
(or @code{try_connect = 'ssh'} or @code{try_connect = 'pb'} in
@file{.buildbot/options}).

For the PB approach, the command must be given a @option{--master}
argument (in the form HOST:PORT) that points to TCP port that you picked
in the @code{Try_Userpass} scheduler. It also takes a
@option{--username} and @option{--passwd} pair of arguments that match
one of the entries in the buildmaster's @code{userpass} list. These
arguments can also be provided as @code{try_master},
@code{try_username}, and @code{try_password} entries in the
@file{.buildbot/options} file.

For the SSH approach, the command must be given @option{--host} and
@option{--username} to get to the buildmaster host. It must also be
given @option{--jobdir}, which points to the inlet directory configured
above. The jobdir can be relative to the user's home directory, but most
of the time you will use an explicit path like
@file{~buildbot/project/jobdir}. These arguments can be provided in
@file{.buildbot/options} as @code{try_host}, @code{try_username}, and
@code{try_jobdir}.

In addition, the SSH approach needs to connect to a PBListener status
port, so it can retrieve and report the results of the build (the PB
approach uses the existing connection to retrieve status information,
so this step is not necessary). This requires a @option{--masterstatus}
argument, or a @code{try_masterstatus} entry in @file{.buildbot/options},
in the form of a HOSTNAME:PORT string.

The following command line arguments are deprecated, but retained for
backward compatibility:

@itemize @bullet
@item
@option{--tryhost} is replaced by @option{--host}
@item
@option{--trydir} is replaced by @option{--jobdir}
@item
@option{--master} is replaced by @option{--masterstatus}
@end itemize

Likewise, the following @file{.buildbot/options} file entries are
deprecated, but retained for backward compatibility:

@itemize @bullet
@item
@code{try_dir} is replaced by @code{try_jobdir}
@item
@code{masterstatus} is replaced by @code{try_masterstatus}
@end itemize


@heading choosing the Builders

A trial build is performed on multiple Builders at the same time, and
the developer gets to choose which Builders are used (limited to a set
selected by the buildmaster admin with the TryScheduler's
@code{builderNames=} argument). The set you choose will depend upon
what your goals are: if you are concerned about cross-platform
compatibility, you should use multiple Builders, one from each
platform of interest. You might use just one builder if that platform
has libraries or other facilities that allow better test coverage than
what you can accomplish on your own machine, or faster test runs.

The set of Builders to use can be specified with multiple
@option{--builder} arguments on the command line. It can also be
specified with a single @code{try_builders} option in
@file{.buildbot/options} that uses a list of strings to specify all
the Builder names:

@example
try_builders = ["full-OSX", "full-win32", "full-linux"]
@end example

If you are using the PB approach, you can get the names of the builders
that are configured for the try scheduler using the @code{get-builder-names}
argument:

@example
buildbot try --get-builder-names --connect=pb --master=... --username=... --passwd=...
@end example

@heading specifying the VC system

The @command{try} command also needs to know how to take the
developer's current tree and extract the (revision, patch)
source-stamp pair. Each VC system uses a different process, so you
start by telling the @command{try} command which VC system you are
using, with an argument like @option{--vc=cvs} or @option{--vc=git}.
This can also be provided as @code{try_vc} in
@file{.buildbot/options}.

The following names are recognized: @code{bzr} @code{cvs}
@code{darcs} @code{git} @code{hg} @code{mtn} @code{p4} @code{svn}


@heading finding the top of the tree

Some VC systems (notably CVS and SVN) track each directory
more-or-less independently, which means the @command{try} command
needs to move up to the top of the project tree before it will be able
to construct a proper full-tree patch. To accomplish this, the
@command{try} command will crawl up through the parent directories
until it finds a marker file. The default name for this marker file is
@file{.buildbot-top}, so when you are using CVS or SVN you should
@code{touch .buildbot-top} from the top of your tree before running
@command{buildbot try}. Alternatively, you can use a filename like
@file{ChangeLog} or @file{README}, since many projects put one of
these files in their top-most directory (and nowhere else). To set
this filename, use @option{--topfile=ChangeLog}, or set it in the
options file with @code{try_topfile = 'ChangeLog'}.

You can also manually set the top of the tree with
@option{--topdir=~/trees/mytree}, or @code{try_topdir =
'~/trees/mytree'}. If you use @code{try_topdir}, in a
@file{.buildbot/options} file, you will need a separate options file
for each tree you use, so it may be more convenient to use the
@code{try_topfile} approach instead.

Other VC systems which work on full projects instead of individual
directories (darcs, mercurial, git, monotone) do not require
@command{try} to know the top directory, so the @option{--topfile}
and @option{--topdir} arguments will be ignored.

If the @command{try} command cannot find the top directory, it will
abort with an error message. 

The following command line arguments are deprecated, but retained for
backward compatibility:

@itemize @bullet
@item
@option{--try-topdir} is replaced by @option{--topdir}
@item
@option{--try-topfile} is replaced by @option{--topfile}
@end itemize

@heading determining the branch name

Some VC systems record the branch information in a way that ``try''
can locate it.  For the others, if you are using something other than
the default branch, you will have to tell the buildbot which branch
your tree is using. You can do this with either the @option{--branch}
argument, or a @option{try_branch} entry in the
@file{.buildbot/options} file.

@heading determining the revision and patch

Each VC system has a separate approach for determining the tree's base
revision and computing a patch.

@table @code

    @item CVS

@command{try} pretends that the tree is up to date. It converts the
current time into a @code{-D} time specification, uses it as the base
revision, and computes the diff between the upstream tree as of that
point in time versus the current contents. This works, more or less,
but requires that the local clock be in reasonably good sync with the
repository.

@item SVN
@command{try} does a @code{svn status -u} to find the latest
repository revision number (emitted on the last line in the ``Status
against revision: NN'' message). It then performs an @code{svn diff
-rNN} to find out how your tree differs from the repository version,
and sends the resulting patch to the buildmaster. If your tree is not
up to date, this will result in the ``try'' tree being created with
the latest revision, then @emph{backwards} patches applied to bring it
``back'' to the version you actually checked out (plus your actual
code changes), but this will still result in the correct tree being
used for the build.

@item bzr
@command{try} does a @code{bzr revision-info} to find the base revision,
then a @code{bzr diff -r$base..} to obtain the patch.

@item Mercurial
@code{hg identify --debug} emits the full revision id (as opposed to
the common 12-char truncated) which is a SHA1 hash of the current
revision's contents. This is used as the base revision.
@code{hg diff} then provides the patch relative to that
revision. For @command{try} to work, your working directory must only
have patches that are available from the same remotely-available
repository that the build process' @code{source.Mercurial} will use.

@item Perforce
@command{try} does a @code{p4 changes -m1 ...} to determine the latest
changelist and implicitly assumes that the local tree is synched to this
revision. This is followed by a @code{p4 diff -du} to obtain the patch.
A p4 patch differs sligtly from a normal diff. It contains full depot
paths and must be converted to paths relative to the branch top. To convert
the following restriction is imposed. The p4base (see @pxref{P4Source})
 is assumed to be @code{//depot}

@item Darcs
@command{try} does a @code{darcs changes --context} to find the list
of all patches back to and including the last tag that was made. This text
file (plus the location of a repository that contains all these
patches) is sufficient to re-create the tree. Therefore the contents
of this ``context'' file @emph{are} the revision stamp for a
Darcs-controlled source tree.  It then does a @code{darcs diff
-u} to compute the patch relative to that revision.

@item Git
@code{git branch -v} lists all the branches available in the local
repository along with the revision ID it points to and a short summary
of the last commit. The line containing the currently checked out
branch begins with '* ' (star and space) while all the others start
with '  ' (two spaces). @command{try} scans for this line and extracts
the branch name and revision from it. Then it generates a diff against
the base revision.
@c TODO: I'm not sure if this actually works the way it's intended
@c since the extracted base revision might not actually exist in the
@c upstream repository. Perhaps we need to add a --remote option to
@c specify the remote tracking branch to generate a diff against.

@item Monotone
@code{mtn automate get_base_revision_id} emits the full revision id
which is a SHA1 hash of the current revision's contents. This is used as
the base revision.
@code{mtn diff} then provides the patch relative to that revision.  For
@command{try} to work, your working directory must only have patches
that are available from the same remotely-available repository that the
build process' @code{source.Monotone} will use.

@end table

@heading showing who built

You can provide the @option{--who=dev} to designate who is running the
try build. This will add the @code{dev} to the Reason field on the try
build's status web page. You can also set @code{try_who = dev} in the
@file{.buildbot/options} file. Note that @option{--who=dev} will not
work on version 0.8.3 or earlier masters.

@heading waiting for results

If you provide the @option{--wait} option (or @code{try_wait = True}
in @file{.buildbot/options}), the @command{buildbot try} command will
wait until your changes have either been proven good or bad before
exiting. Unless you use the @option{--quiet} option (or
@code{try_quiet=True}), it will emit a progress message every 60
seconds until the builds have completed.

Sometimes you might have a patch from someone else that you want to
submit to the buildbot. For example, a user may have created a patch
to fix some specific bug and sent it to you by email. You've inspected
the patch and suspect that it might do the job (and have at least
confirmed that it doesn't do anything evil). Now you want to test it
out.

One approach would be to check out a new local tree, apply the patch,
run your local tests, then use ``buildbot try'' to run the tests on
other platforms. An alternate approach is to use the @command{buildbot
try --diff} form to have the buildbot test the patch without using a
local tree.

This form takes a @option{--diff} argument which points to a file that
contains the patch you want to apply. By default this patch will be
applied to the TRUNK revision, but if you give the optional
@option{--baserev} argument, a tree of the given revision will be used
as a starting point instead of TRUNK.

You can also use @command{buildbot try --diff=-} to read the patch
from stdin.

Each patch has a ``patchlevel'' associated with it. This indicates the
number of slashes (and preceding pathnames) that should be stripped
before applying the diff. This exactly corresponds to the @option{-p}
or @option{--strip} argument to the @command{patch} utility. By
default @command{buildbot try --diff} uses a patchlevel of 0, but you
can override this with the @option{-p} argument.

When you use @option{--diff}, you do not need to use any of the other
options that relate to a local tree, specifically @option{--vc},
@option{--topfile}, or @option{--topdir}. These options will
be ignored. Of course you must still specify how to get to the
buildmaster (with @option{--connect}, @option{--host}, etc).


@node Other Tools
@subsection Other Tools

These tools are generally used by buildmaster administrators.

@menu
* sendchange::
* debugclient::
@end menu

@node sendchange
@subsubsection sendchange

This command is used to tell the buildmaster about source changes. It
is intended to be used from within a commit script, installed on the
VC server. It requires that you have a PBChangeSource
(@pxref{PBChangeSource}) running in the buildmaster (by being set in
@code{c['change_source']}).

@example
buildbot sendchange --master @var{MASTERHOST}:@var{PORT} --auth @var{USER}:@var{PASS} \
        --who @var{COMMITTER} @var{FILENAMES..}
@end example

The @code{auth} option specifies the credentials to use to connect to the
master, in the form @code{user:pass}.  If the password is omitted, then
sendchange will prompt for it.  If both are omitted, the old default (username
"change" and password "changepw") will be used.  Note that this password is
well-known, and should not be used on an internet-accessible port.

The @code{master} and @code{who} arguments can also be given in the
options file (@pxref{.buildbot config directory}).  There are other (optional)
arguments which can influence the @code{Change} that gets submitted:

@table @code
@item --branch
(or option @code{branch}) This provides the (string) branch specifier. If
omitted, it defaults to None, indicating the ``default branch''. All files
included in this Change must be on the same branch.

@item --category
(or option @code{category}) This provides the (string) category specifier. If
omitted, it defaults to None, indicating ``no category''. The category property
can be used by Schedulers to filter what changes they listen to.

@item --project
(or option @code{project}) This provides the (string) project to which this
change applies, and defaults to ''.  The project can be used by schedulers to
decide which builders should respond to a particular change.

@item --repository
(or option @code{repository}) This provides the repository from which this
change came, and defaults to ''.

@item --revision
This provides a revision specifier, appropriate to the VC system in use.

@item --revision_file
This provides a filename which will be opened and the contents used as
the revision specifier. This is specifically for Darcs, which uses the
output of @command{darcs changes --context} as a revision specifier.
This context file can be a couple of kilobytes long, spanning a couple
lines per patch, and would be a hassle to pass as a command-line
argument.

@item --property
This parameter is used to set a property on the Change generated by sendchange.
Properties are specified as a name:value pair, separated by a colon. You may
specify many properties by passing this parameter multiple times.

@item --comments
This provides the change comments as a single argument. You may want
to use @option{--logfile} instead.

@item --logfile
This instructs the tool to read the change comments from the given
file. If you use @code{-} as the filename, the tool will read the
change comments from stdin.

@item --encoding
Specifies the character encoding for all other parameters, defaulting to 'utf8'.

@end table


@node debugclient
@subsubsection debugclient

@example
buildbot debugclient --master @var{MASTERHOST}:@var{PORT} --passwd @var{DEBUGPW}
@end example

This launches a small Gtk+/Glade-based debug tool, connecting to the
buildmaster's ``debug port''. This debug port shares the same port
number as the slaveport (@pxref{Setting the PB Port for Slaves}), but the
@code{debugPort} is only enabled if you set a debug password in the
buildmaster's config file (@pxref{Debug Options}). The
@option{--passwd} option must match the @code{c['debugPassword']}
value.

@option{--master} can also be provided in @file{.debug/options} by the
@code{master} key. @option{--passwd} can be provided by the
@code{debugPassword} key.  @xref{.buildbot config directory}.

The @code{Connect} button must be pressed before any of the other
buttons will be active. This establishes the connection to the
buildmaster. The other sections of the tool are as follows:

@table @code
@item Reload .cfg
Forces the buildmaster to reload its @file{master.cfg} file. This is
equivalent to sending a SIGHUP to the buildmaster, but can be done
remotely through the debug port. Note that it is a good idea to be
watching the buildmaster's @file{twistd.log} as you reload the config
file, as any errors which are detected in the config file will be
announced there.

@item Rebuild .py
(not yet implemented). The idea here is to use Twisted's ``rebuild''
facilities to replace the buildmaster's running code with a new
version. Even if this worked, it would only be used by buildbot
developers.

@item poke IRC
This locates a @code{words.IRC} status target and causes it to emit a
message on all the channels to which it is currently connected. This
was used to debug a problem in which the buildmaster lost the
connection to the IRC server and did not attempt to reconnect.

@item Commit
This allows you to inject a Change, just as if a real one had been
delivered by whatever VC hook you are using. You can set the name of
the committed file and the name of the user who is doing the commit.
Optionally, you can also set a revision for the change. If the
revision you provide looks like a number, it will be sent as an
integer, otherwise it will be sent as a string.

@item Force Build
This lets you force a Builder (selected by name) to start a build of
the current source tree.

@item Currently
(obsolete). This was used to manually set the status of the given
Builder, but the status-assignment code was changed in an incompatible
way and these buttons are no longer meaningful.

@end table


@node .buildbot config directory
@subsection .buildbot config directory

Many of the @command{buildbot} tools must be told how to contact the
buildmaster that they interact with. This specification can be
provided as a command-line argument, but most of the time it will be
easier to set them in an ``options'' file. The @command{buildbot}
command will look for a special directory named @file{.buildbot},
starting from the current directory (where the command was run) and
crawling upwards, eventually looking in the user's home directory. It
will look for a file named @file{options} in this directory, and will
evaluate it as a python script, looking for certain names to be set.
You can just put simple @code{name = 'value'} pairs in this file to
set the options.

For a description of the names used in this file, please see the
documentation for the individual @command{buildbot} sub-commands. The
following is a brief sample of what this file's contents could be.

@example
# for status-reading tools
masterstatus = 'buildbot.example.org:12345'
# for 'sendchange' or the debug port
master = 'buildbot.example.org:18990'
debugPassword = 'eiv7Po'
@end example

Note carefully that the names in the @code{options} file usually do not match
the command-line option name.

@table @code
@item masterstatus
Equivalent to @code{--master} for @ref{statuslog} and @ref{statusgui}, this
gives the location of the @code{client.PBListener} status port.

@item master
Equivalent to @code{--master} for @ref{debugclient} and @ref{sendchange}.
This option is used for two purposes.  It is the location of the
@code{debugPort} for @command{debugclient} and the location of the
@code{pb.PBChangeSource} for @command{sendchange}.  Generally these are the
same port.

@item debugPassword
Equivalent to @code{--passwd} for @ref{debugclient}.

XXX Must match the value of @code{c['debugPassword']}, used to protect the
debug port, for the @command{debugclient} command.

@item username
Equivalent to @code{--username} for the @ref{sendchange} command.

@item branch
Equivalent to @code{--branch} for the @ref{sendchange} command.

@item category
Equivalent to @code{--category} for the @ref{sendchange} command.

@item try_connect
Equivalent to @code{--connect}, this specifies how the @ref{try} command should
deliver its request to the buildmaster. The currently accepted values are
``ssh'' and ``pb''.

@item try_builders
Equivalent to @code{--builders}, specifies which builders should be used for
the @ref{try} build.

@item try_vc
Equivalent to @code{--vc} for @ref{try}, this specifies the version control
system being used.

@item try_branch
Equivlanent to @code{--branch}, this indicates that the current tree is on a non-trunk branch.

@item try_topdir
@item try_topfile
Use @code{try_topdir}, equivalent to @code{--try-topdir}, to explicitly
indicate the top of your working tree, or @code{try_topfile}, equivalent to
@code{--try-topfile} to name a file that will only be found in that top-most
directory.

@item try_host
@item try_username
@item try_dir
When @code{try_connect} is ``ssh'', the command will use @code{try_host} for
@code{--tryhost}, @code{try_username} for @code{--username}, and @code{try_dir}
for @code{--trydir}.  Apologies for the confusing presence and absence of
'try'.

@item try_username
@item try_password
@item try_master
Similarly, when @code{try_connect} is ``pb'', the command will pay attention to
@code{try_username} for @code{--username}, @code{try_password} for
@code{--passwd}, and @code{try_master} for @code{--master}.

@item try_wait
@item masterstatus
@code{try_wait} and @code{masterstatus} (equivalent to @code{--wait} and
@code{master}, respectively) are used to ask the @ref{try} command to wait for
the requested build to complete.

@end table

@node buildslave
@section buildslave

@command{buildslave} command-line tool is used for buildslave management
only and does not provide any additional functionality. One can create,
start, stop and restart the buildslave.

@menu
* create-slave::
* start: start (buildslave).
* stop: stop (buildslave).
@end menu

@node create-slave
@subsection create-slave

This creates a new directory and populates it with files that let it
be used as a buildslave's base directory. You must provide several
arguments, which are used to create the initial @file{buildbot.tac}
file.

The @code{-r} option is advisable here, just like for @code{create-master}.

@example
buildslave create-slave -r @var{BASEDIR} @var{MASTERHOST}:@var{PORT} @var{SLAVENAME} @var{PASSWORD}
@end example

The create-slave options are described in @xref{Buildslave Options}.

@node start (buildslave)
@subsection start

This starts a buildslave which was already created in the given base
directory. The daemon is launched in the background, with events logged
to a file named @file{twistd.log}.

@example
buildbot start BASEDIR
@end example

@node stop (buildslave)
@subsection stop

This terminates the daemon buildslave running in the given directory.

@example
buildbot stop BASEDIR
@end example
