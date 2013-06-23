.. bb:cfg:: status

.. _Status-Targets:

Status Targets
--------------

The Buildmaster has a variety of ways to present build status to
various users. Each such delivery method is a `Status Target` object
in the configuration's :bb:cfg:`status` list. To add status targets, you
just append more objects to this list::

    c['status'] = []
    
    from buildbot.status import html
    c['status'].append(html.Waterfall(http_port=8010))
    
    from buildbot.status import mail
    m = mail.MailNotifier(fromaddr="buildbot@localhost",
                          extraRecipients=["builds@lists.example.com"],
                          sendToInterestedUsers=False)
    c['status'].append(m)
    
    from buildbot.status import words
    c['status'].append(words.IRC(host="irc.example.com", nick="bb",
                                 channels=[{"channel": "#example1"},
                                           {"channel": "#example2",
                                            "password": "somesecretpassword"}]))

Most status delivery objects take a ``categories=`` argument, which
can contain a list of `category` names: in this case, it will only
show status for Builders that are in one of the named categories.

.. note:: Implementation Note

    Each of these objects should be a :class:`service.MultiService` which will be attached
    to the BuildMaster object when the configuration is processed. They should use
    ``self.parent.getStatus()`` to get access to the top-level :class:`IStatus` object,
    either inside :meth:`startService` or later. They may call
    :meth:`status.subscribe()` in :meth:`startService` to receive notifications of
    builder events, in which case they must define :meth:`builderAdded` and related
    methods. See the docstrings in :file:`buildbot/interfaces.py` for full details.

The remainder of this section describes each built-in status target.  A full
list of status targets is available in the :bb:index:`status`.

.. bb:status:: WebStatus

WebStatus
~~~~~~~~~

.. py:class:: buildbot.status.web.baseweb.WebStatus

The :class:`buildbot.status.html.WebStatus` status target runs a small
web server inside the buildmaster. You can point a browser at this web
server and retrieve information about every build the buildbot knows
about, as well as find out what the buildbot is currently working on.

The first page you will see is the *Welcome Page*, which contains
links to all the other useful pages. By default, this page is served from the
:file:`status/web/templates/root.html` file in buildbot's library area.

One of the most complex resource provided by :class:`WebStatus` is the
*Waterfall Display*, which shows a time-based chart of events. This
somewhat-busy display provides detailed information about all steps of all
recent builds, and provides hyperlinks to look at individual build logs and
source changes. By simply reloading this page on a regular basis, you will see
a complete description of everything the buildbot is currently working on.

A similar, but more developer-oriented display is the `Grid` display.  This
arranges builds by :class:`SourceStamp` (horizontal axis) and builder (vertical axis),
and can provide quick information as to which revisions are passing or failing
on which builders.

There are also pages with more specialized information. For example,
there is a page which shows the last 20 builds performed by the
buildbot, one line each. Each line is a link to detailed information
about that build. By adding query arguments to the URL used to reach
this page, you can narrow the display to builds that involved certain
branches, or which ran on certain :class:`Builder`\s. These pages are described
in great detail below.

Configuration
+++++++++++++

The simplest possible configuration for WebStatus is::

    from buildbot.status.html import WebStatus
    c['status'].append(WebStatus(8080))

Buildbot uses a templating system for the web interface. The source
of these templates can be found in the :file:`status/web/templates/` directory
in buildbot's library area. You can override these templates by creating
alternate versions in a :file:`templates/` directory within the buildmaster's
base directory.

If that isn't enough you can also provide additional Jinja2 template loaders::

    import jinja2
    myloaders = [
        jinja2.FileSystemLoader("/tmp/mypath"),
        ]

    c['status'].append(html.WebStatus(
        …,
        jinja_loaders = myloaders,
    ))

The first time a buildmaster is created, the :file:`public_html/`
directory is populated with some sample files, which you will probably
want to customize for your own project. These files are all static:
the buildbot does not modify them in any way as it serves them to HTTP
clients.

Templates in :file:`templates/` take precedence over static files in
:file:`public_html/`.

The initial :file:`robots.txt` file has Disallow lines for all of
the dynamically-generated buildbot pages, to discourage web spiders
and search engines from consuming a lot of CPU time as they crawl
through the entire history of your buildbot. If you are running the
buildbot behind a reverse proxy, you'll probably need to put the
:file:`robots.txt` file somewhere else (at the top level of the parent web
server), and replace the URL prefixes in it with more suitable values.

If you would like to use an alternative root directory, add the
``public_html=`` option to the :class:`WebStatus` creation::

    c['status'].append(WebStatus(8080, public_html="/var/www/buildbot"))

In addition, if you are familiar with twisted.web *Resource
Trees*, you can write code to add additional pages at places inside
this web space. Just use :meth:`webstatus.putChild` to place these
resources.

The following section describes the special URLs and the status views
they provide.

Buildbot Web Resources
++++++++++++++++++++++

Certain URLs are `magic`, and the pages they serve are created by
code in various classes in the :file:`buildbot.status.web` package
instead of being read from disk. The most common way to access these
pages is for the buildmaster admin to write or modify the
:file:`index.html` page to contain links to them. Of course other
project web pages can contain links to these buildbot pages as well.

Many pages can be modified by adding query arguments to the URL. For
example, a page which shows the results of the most recent build
normally does this for all builders at once. But by appending
``?builder=i386`` to the end of the URL, the page will show only the
results for the `i386` builder. When used in this way, you can add
multiple ``builder=`` arguments to see multiple builders. Remembering
that URL query arguments are separated *from each other* with
ampersands, a URL that ends in ``?builder=i386&builder=ppc`` would
show builds for just those two Builders.

The ``branch=`` query argument can be used on some pages. This
filters the information displayed by that page down to only the builds
or changes which involved the given branch. Use ``branch=trunk`` to
reference the trunk: if you aren't intentionally using branches,
you're probably using trunk. Multiple ``branch=`` arguments can be
used to examine multiple branches at once (so appending
``?branch=foo&branch=bar`` to the URL will show builds involving
either branch). No ``branch=`` arguments means to show builds and
changes for all branches.

Some pages may include the Builder name or the build number in the
main part of the URL itself. For example, a page that describes Build
#7 of the `i386` builder would live at :file:`/builders/i386/builds/7`.

The table below lists all of the internal pages and the URLs that can
be used to access them.

``/waterfall``
    This provides a chronologically-oriented display of the activity of
    all builders. It is the same display used by the Waterfall display.
    
    By adding one or more ``builder=`` query arguments, the Waterfall is
    restricted to only showing information about the given Builders. By
    adding one or more ``branch=`` query arguments, the display is
    restricted to showing information about the given branches. In
    addition, adding one or more ``category=`` query arguments to the URL
    will limit the display to Builders that were defined with one of the
    given categories.
    
    A ``show_events=true`` query argument causes the display to include
    non-:class:`Build` events, like slaves attaching and detaching, as well as
    reconfiguration events. ``show_events=false`` hides these events. The
    default is to show them.
    
    By adding the ``failures_only=true`` query argument, the Waterfall is
    restricted to only showing information about the builders that
    are currently failing. A builder is considered failing if the
    last finished build was not successful, a step in the current
    build(s) is failing, or if the builder is offline.
    
    The ``last_time=``, ``first_time=``, and  ``show_time=``
    arguments will control what interval of time is displayed. The default
    is to show the latest events, but these can be used to look at earlier
    periods in history. The ``num_events=`` argument also provides a
    limit on the size of the displayed page.
    
    The Waterfall has references to resources many of the other portions
    of the URL space: :file:`/builders` for access to individual builds,
    :file:`/changes` for access to information about source code changes,
    etc.

``/grid``
    This provides a chronologically oriented display of builders, by
    revision.  The builders are listed down the left side of the page,
    and the revisions are listed across the top.
    
    By adding one or more ``category=`` arguments the grid will be
    restricted to revisions in those categories.
    
    A :samp:`width={N}` argument will limit the number of revisions shown to *N*,
    defaulting to 5.
    
    A :samp:`branch={BRANCHNAME}` argument will limit the grid to revisions on
    branch *BRANCHNAME*.

``/tgrid``
    The Transposed Grid is similar to the standard grid, but, as the name
    implies, transposes the grid: the revisions are listed down the left side
    of the page, and the build hosts are listed across the top.  It accepts
    the same query arguments. The exception being that instead of ``width``
    the argument is named ``length``.

    This page also has a ``rev_order=`` query argument that lets you
    change in what order revisions are shown. Valid values are ``asc``
    (ascending, oldest revision first) and ``desc`` (descending,
    newest revision first).


``/console``
    EXPERIMENTAL: This provides a developer-oriented display of the last
    changes and how they affected the builders.
    
    It allows a developer to quickly see the status of each builder for the
    first build including his or her change. A green box means that the change
    succeeded for all the steps for a given builder. A red box means that
    the changed introduced a new regression on a builder. An orange box
    means that at least one of the tests failed, but it was also failing
    in the previous build, so it is not possible to see if there were any
    regressions from this change. Finally a yellow box means that the test
    is in progress.
    
    By adding one or more ``builder=`` query arguments, the Console view is
    restricted to only showing information about the given Builders. Adding a
    ``repository=`` argument will limit display to a given repository. By
    adding one or more ``branch=`` query arguments, the display is restricted
    to showing information about the given branches. In addition, adding one or
    more ``category=`` query arguments to the URL will limit the display to
    Builders that were defined with one of the given categories.  With the
    ``project=`` query argument, it's possible to restrict the view to changes
    from the given project.  With the ``codebase=`` query argument, it's possible
    to restrict the view to changes for the given codebase.
    
    By adding one or more ``name=`` query arguments to the URL, the console view is
    restricted to only showing changes made by the given users.
    
    NOTE: To use this page, your :file:`buildbot.css` file in
    :file:`public_html` must be the one found in
    :bb:src:`master/buildbot/status/web/files/default.css`. This is the default
    for new installs, but upgrades of very old installs of Buildbot may need to
    manually fix the CSS file.

    The console view is still in development. At this moment by
    default the view sorts revisions lexically, which can lead to odd
    behavior with non-integer revisions (e.g., Git), or with integer
    revisions of different length (e.g., 999 and 1000). It also has
    some issues with displaying multiple branches at the same time. If
    you do have multiple branches, you should use the ``branch=``
    query argument.  The ``order_console_by_time`` option may help
    sorting revisions, although it depends on the date being set
    correctly in each commit::

        w = html.WebStatus(http_port=8080, order_console_by_time=True)

``/rss``
    This provides a rss feed summarizing all failed builds. The same
    query-arguments used by 'waterfall' can be added to filter the
    feed output.

``/atom``
    This provides an atom feed summarizing all failed builds. The same
    query-arguments used by 'waterfall' can be added to filter the feed
    output.

``/json``
    This view provides quick access to Buildbot status information in a form that
    is easily digested from other programs, including JavaScript.  See
    ``/json/help`` for detailed interactive documentation of the output formats
    for this view.

:samp:`/buildstatus?builder=${BUILDERNAME}&number=${BUILDNUM}`
    This displays a waterfall-like chronologically-oriented view of all the
    steps for a given build number on a given builder.

:samp:`/builders/${BUILDERNAME}`
    This describes the given :class:`Builder` and provides buttons to force a
    build.  A ``numbuilds=`` argument will control how many build lines
    are displayed (5 by default).  This page also accepts property filters
    of the form ``property.${PROPERTYNAME}=${PROPERTVALUE}``.  When used,
    only builds and build requests which have properties with matching string
    representations will be shown.

:samp:`/builders/${BUILDERNAME}/builds/${BUILDNUM}`
    This describes a specific Build.

:samp:`/builders/${BUILDERNAME}/builds/${BUILDNUM}/steps/${STEPNAME}`
    This describes a specific BuildStep.

:samp:`/builders/${BUILDERNAME}/builds/${BUILDNUM}/steps/${STEPNAME}/logs/${LOGNAME}`
    This provides an HTML representation of a specific logfile.

:samp:`/builders/${BUILDERNAME}/builds/${BUILDNUM}/steps/${STEPNAME}/logs/${LOGNAME}/text`
    This returns the logfile as plain text, without any HTML coloring
    markup. It also removes the `headers`, which are the lines that
    describe what command was run and what the environment variable
    settings were like. This maybe be useful for saving to disk and
    feeding to tools like :command:`grep`.

``/changes``
    This provides a brief description of the :class:`ChangeSource` in use
    (see :ref:`Change-Sources`).

:samp:`/changes/{NN}`
    This shows detailed information about the numbered :class:`Change`: who was the
    author, what files were changed, what revision number was represented,
    etc.

``/buildslaves``
    This summarizes each :class:`BuildSlave`, including which `Builder`\s are
    configured to use it, whether the buildslave is currently connected or
    not, and host information retrieved from the buildslave itself.

    A ``no_builders=1`` URL argument will omit the builders column.  This is
    useful if each buildslave is assigned to a large number of builders.

``/one_line_per_build``
    This page shows one line of text for each build, merging information
    from all :class:`Builder`\s [#]_. Each line specifies
    the name of the Builder, the number of the :class:`Build`, what revision it
    used, and a summary of the results. Successful builds are in green,
    while failing builds are in red. The date and time of the build are
    added to the right-hand edge of the line. The lines are ordered by
    build finish timestamp.
    
    One or more ``builder=`` or ``branch=`` arguments can be used to
    restrict the list. In addition, a ``numbuilds=`` argument will
    control how many lines are displayed (20 by default).

``/builders``
    This page shows a small table, with one box for each :class:`Builder`,
    containing the results of the most recent :class:`Build`. It does not show the
    individual steps, or the current status. This is a simple summary of
    buildbot status: if this page is green, then all tests are passing.
    
    As with ``/one_line_per_build``, this page will also honor
    ``builder=`` and ``branch=`` arguments.

``/png``
    This view produces an image in png format with information about the last build for the given builder name or whatever other build number if is passed as an argument to the view.

:samp:`/png?builder=${BUILDERNAME}&number=$BUILDNUM&size=large`
    This generate a large png image reporting the status of the given $BUILDNUM for the given builder $BUILDERNAME. The sizes are `small`, `normal` and `large` if no size is given the `normal` size is returned, if no $BUILDNUM is given the last build is returned. For example:

    .. image:: ../_images/success_normal.png

``/users``
    This page exists for authentication reasons when checking ``showUsersPage``.
    It'll redirect to ``/authfail`` on ``False``, ``/users/table`` on ``True``,
    and give a username/password login prompt on ``'auth'``. Passing or failing
    results redirect to the same pages as ``False`` and ``True``.

``/users/table``
    This page shows a table containing users that are stored in the database.
    It has columns for their respective ``uid`` and ``identifier`` values,
    with the ``uid`` values being clickable for more detailed information
    relating to a user.

``/users/table/{NN}``
    Shows all the attributes stored in the database relating to the user
    with uid ``{NN}`` in a table.

``/about``
    This page gives a brief summary of the Buildbot itself: software
    version, versions of some libraries that the Buildbot depends upon,
    etc. It also contains a link to the buildbot.net home page.

There are also a set of web-status resources that are intended for use
by other programs, rather than humans.

``/change_hook``
    This provides an endpoint for web-based source change
    notification. It is used by GitHub and
    contrib/post_build_request.py. See :ref:`Change-Hooks` for more
    details.

WebStatus Configuration Parameters
++++++++++++++++++++++++++++++++++

HTTP Connection
###############

The most common way to run a :class:`WebStatus` is on a regular TCP
port. To do this, just pass in the TCP port number when you create the
:class:`WebStatus` instance; this is called the ``http_port`` argument::

    from buildbot.status.html import WebStatus
    c['status'].append(WebStatus(http_port=8080))

The ``http_port`` argument is actually a `strports specification` for the
port that the web server should listen on. This can be a simple port number, or
a string like ``http_port="tcp:8080:interface=127.0.0.1"`` (to limit
connections to the loopback interface, and therefore to clients running on the
same host) [#]_.

If instead (or in addition) you provide the ``distrib_port``
argument, a twisted.web distributed server will be started either on a
TCP port (if ``distrib_port`` is like ``"tcp:12345"``) or more
likely on a UNIX socket (if ``distrib_port`` is like
``"unix:/path/to/socket"``).

The ``public_html`` option gives the path to a regular directory of HTML
files that will be displayed alongside the various built-in URLs buildbot
supplies.  This is most often used to supply CSS files (:file:`/buildbot.css`)
and a top-level navigational file (:file:`/index.html`), but can also serve any
other files required - even build results!

.. _Authorization:

Authorization
#############

The buildbot web status is, by default, read-only.  It displays lots of
information, but users are not allowed to affect the operation of the
buildmaster.  However, there are a number of supported activities that can
be enabled, and Buildbot can also perform rudimentary username/password
authentication.  The actions are:

``view``
    view buildbot web status

``forceBuild``
    force a particular builder to begin building, optionally with a specific revision, branch, etc.

``forceAllBuilds``
    force *all* builders to start building

``pingBuilder``
    "ping" a builder's buildslaves to check that they are alive

``gracefulShutdown``
    gracefully shut down a slave when it is finished with its current build

``pauseSlave``
    temporarily stop running new builds on a slave

``stopBuild``
    stop a running build

``stopAllBuilds``
    stop all running builds

``cancelPendingBuild``
    cancel a build that has not yet started

``stopChange``
    cancel builds that include a given change number

``cleanShutdown``
    shut down the master gracefully, without interrupting builds

``showUsersPage``
    access to page displaying users in the database, see :ref:`User-Objects`

For each of these actions, you can configure buildbot to never allow the
action, always allow the action, allow the action to any authenticated user, or
check with a function of your creation to determine whether the action is OK
(see below).

This is all configured with the :class:`Authz` class::

    from buildbot.status.html import WebStatus
    from buildbot.status.web.authz import Authz
    authz = Authz(
        forceBuild=True,
        stopBuild=True)
    c['status'].append(WebStatus(http_port=8080, authz=authz))

Each of the actions listed above is an option to :class:`Authz`.  You can
specify ``False`` (the default) to prohibit that action or ``True`` to enable
it.  Or you can specify a callable.  Each such callable will take a username as
its first argument.  The remaining arguments vary depending on the type of
authorization request.  For ``forceBuild``, the second argument is the builder
status.

Authentication
##############

If you do not wish to allow strangers to perform actions, but do want
developers to have such access, you will need to add some authentication
support.  Pass an instance of :class:`status.web.auth.IAuth` as a ``auth``
keyword argument to :class:`Authz`, and specify the action as ``"auth"``. ::

    from buildbot.status.html import WebStatus
    from buildbot.status.web.authz import Authz
    from buildbot.status.web.auth import BasicAuth
    users = [('bob', 'secret-pass'), ('jill', 'super-pass')]
    authz = Authz(auth=BasicAuth(users),
        forceBuild='auth', # only authenticated users
        pingBuilder=True, # but anyone can do this
    )
    c['status'].append(WebStatus(http_port=8080, authz=authz))
    # or
    from buildbot.status.web.auth import HTPasswdAuth
    auth = (HTPasswdAuth('/path/to/htpasswd'))
    # or
    from buildbot.status.web.auth import UsersAuth
    auth = UsersAuth()

The class :class:`BasicAuth` implements a basic authentication mechanism using a
list of user/password tuples provided from the configuration file.  The class
`HTPasswdAuth` implements an authentication against an :file:`.htpasswd`
file. The `HTPasswdAprAuth` a subclass of `HTPasswdAuth` use libaprutil for
authenticating. This adds support for apr1/md5 and sha1 password hashes but
requires libaprutil at runtime. The :class:`UsersAuth` works with
:ref:`User-Objects` to check for valid user credentials.

If you need still-more flexibility, pass a function for the authentication
action.  That function will be called with an authenticated username and some
action-specific arguments, and should return true if the action is authorized. ::

    def canForceBuild(username, builder_status):
        if builder_status.getName() == 'smoketest':
            return True # any authenticated user can run smoketest
        elif username == 'releng':
            return True # releng can force whatever they want
        else:
            return False # otherwise, no way.
    
    authz = Authz(auth=BasicAuth(users),
        forceBuild=canForceBuild)

The ``forceBuild`` and ``pingBuilder`` actions both supply a
:class:`BuilderStatus` object.  The ``stopBuild`` action supplies a :class:`BuildStatus`
object.  The ``cancelPendingBuild`` action supplies a :class:`BuildRequest`.  The
remainder do not supply any extra arguments.

HTTP-based authentication by frontend server
############################################

In case if WebStatus is served through reverse proxy that supports HTTP-based
authentication (like apache, lighttpd), it's possible to to tell WebStatus to
trust web server and get username from request headers. This allows displaying
correct usernames in build reason, interrupt messages, etc.

Just set ``useHttpHeader`` to ``True`` in :class:`Authz` constructor. ::

    authz = Authz(useHttpHeader=True) # WebStatus secured by web frontend with HTTP auth

Please note that WebStatus can decode password for HTTP Basic requests only (for
Digest authentication it's just impossible). Custom :class:`status.web.auth.IAuth`
subclasses may just ignore password at all since it's already validated by web server.

Administrator must make sure that it's impossible to get access to WebStatus
using other way than through frontend. Usually this means that WebStatus should
listen for incoming connections only on localhost (or on some firewall-protected
port). Frontend must require HTTP authentication to access WebStatus pages
(using any source for credentials, such as htpasswd, PAM, LDAP).

If you allow unauthenticated access through frontend as well, it's possible to
specify a ``httpLoginLink`` which will be rendered on the WebStatus for
unauthenticated users as a link named Login. ::

    authz = Authz(useHttpHeader=True, httpLoginLink='https://buildbot/login')

A configuration example with Apache HTTPD as reverse proxy could look like the
following. ::

    authz = Authz(
      useHttpHeader=True,
      httpLoginLink='https://buildbot/login',
      auth = HTPasswdAprAuth('/var/www/htpasswd'),
      forceBuild = 'auth')

Corresponding Apache configuration.

.. code-block:: apache
   
    ProxyPass / http://127.0.0.1:8010/

    <Location /login>
        AuthType Basic
        AuthName "Buildbot"
        AuthUserFile /var/www/htpasswd
        Require valid-user

        RewriteEngine on
        RewriteCond %{HTTP_REFERER} ^https?://([^/]+)/(.*)$
        RewriteRule ^.*$ https://%1/%2 [R,L]
    </Location>

Logging configuration
#####################

The `WebStatus` uses a separate log file (:file:`http.log`) to avoid clutter
buildbot's default log (:file:`twistd.log`) with request/response messages.
This log is also, by default, rotated in the same way as the twistd.log
file, but you can also customize the rotation logic with the following
parameters if you need a different behaviour.

``rotateLength``
    An integer defining the file size at which log files are rotated. 

``maxRotatedFiles``
    The maximum number of old log files to keep. 

URL-decorating options
######################

These arguments adds an URL link to various places in the WebStatus,
such as revisions, repositories, projects and, optionally, ticket/bug references
in change comments.

revlink
'''''''

The ``revlink`` argument on :class:`WebStatus` is deprecated in favour of the
global :bb:cfg:`revlink` option. Only use this if you need to generate
different URLs for different web status instances.

In addition to a callable like :bb:cfg:`revlink`, this argument accepts a
format string or a dict mapping a string (repository name) to format strings.

The format string should use ``%s`` to insert the revision id in the url.  For
example, for Buildbot on GitHub::

    revlink='http://github.com/buildbot/buildbot/tree/%s'

The revision ID will be URL encoded before inserted in the replacement string

changecommentlink
'''''''''''''''''

The ``changecommentlink`` argument can be used to create links to
ticket-ids from change comments (i.e. #123).

The argument can either be a tuple of three strings, a dictionary
mapping strings (project names) to tuples or a callable taking a
changetext (a :class:`jinja2.Markup` instance) and a project name,
returning a the same change text with additional links/html tags added
to it.

If the tuple is used, it should contain three strings where the first
element is a regex that searches for strings (with match groups), the
second is a replace-string that, when substituted with ``\1`` etc,
yields the URL and the third is the title attribute of the link. (The
``<a href="" title=""></a>`` is added by the system.) So, for Trac
tickets (#42, etc): ``changecommentlink(r"#(\d+)",
r"http://buildbot.net/trac/ticket/\1", r"Ticket \g<0>")`` . 

projects
''''''''

A dictionary from strings to strings, mapping project names to URLs,
or a callable taking a project name and returning an URL.

repositories
''''''''''''

Same as the projects arg above, a dict or callable mapping project names
to URLs.

Display-Specific Options
########################

The ``order_console_by_time`` option affects the rendering of the console;
see the description of the console above.

The ``numbuilds`` option determines the number of builds that most status
displays will show.  It can usually be overriden in the URL, e.g.,
``?numbuilds=13``.

The ``num_events`` option gives the default number of events that the
waterfall will display.  The ``num_events_max`` gives the maximum number of
events displayed, even if the web browser requests more.

.. _Change-Hooks:

Change Hooks
++++++++++++

The ``/change_hook`` url is a magic URL which will accept HTTP requests and translate
them into changes for buildbot. Implementations (such as a trivial json-based endpoint
and a GitHub implementation) can be found in :bb:src:`master/buildbot/status/web/hooks`.
The format of the url is :samp:`/change_hook/{DIALECT}` where DIALECT is a package within the 
hooks directory. Change_hook is disabled by default and each DIALECT has to be enabled
separately, for security reasons

An example WebStatus configuration line which enables change_hook and two DIALECTS::

    c['status'].append(html.WebStatus(http_port=8010,allowForce=True,
        change_hook_dialects={
                              'base': True,
                              'somehook': {'option1':True,
                                           'option2':False}}))

Within the WebStatus arguments, the ``change_hook`` key enables/disables the module
and ``change_hook_dialects`` whitelists DIALECTs where the keys are the module names
and the values are optional arguments which will be passed to the hooks.

The :file:`post_build_request.py` script in :file:`master/contrib` allows for the
submission of an arbitrary change request. Run :command:`post_build_request.py
--help` for more information.  The ``base`` dialect must be enabled for this to
work.

GitHub hook
###########

The GitHub hook is simple and takes no options. ::

    c['status'].append(html.WebStatus(..
                       change_hook_dialects={ 'github' : True }))

With this set up, add a Post-Receive URL for the project in the GitHub
administrative interface, pointing to ``/change_hook/github`` relative to
the root of the web status.  For example, if the grid URL is
``http://builds.mycompany.com/bbot/grid``, then point GitHub to
``http://builds.mycompany.com/bbot/change_hook/github``. To specify a project
associated to the repository, append ``?project=name`` to the URL.

Note that there is a standalone HTTP server available for receiving GitHub
notifications, as well: :file:`contrib/github_buildbot.py`.  This script may be
useful in cases where you cannot expose the WebStatus for public consumption.

.. warning::

    The incoming HTTP requests for this hook are not authenticated by default.
    Anyone who can access the web status can "fake" a request from
    GitHub, potentially causing the buildmaster to run arbitrary code.

To protect URL against unauthorized access you should use ``change_hook_auth`` option. ::

    c['status'].append(html.WebStatus(..
                                      change_hook_auth=('user', 'password')))

Then, create a GitHub service hook (see https://help.github.com/articles/post-receive-hooks) with a WebHook URL like ``http://user:password@builds.mycompany.com/bbot/change_hook/github``.

Note that not using ``change_hook_auth`` can expose you to security risks.

BitBucket hook
##############

The BitBucket hook is as simple as GitHub one and it also takes no options. ::

    c['status'].append(html.WebStatus(..
                       change_hook_dialects={ 'bitbucket' : True }))

When this is setup you should add a `POST` service pointing to ``/change_hook/bitbucket``
relative to the root of the web status. For example, it the grid URL is
``http://builds.mycompany.com/bbot/grid``, then point BitBucket to
``http://builds.mycompany.com/change_hook/bitbucket``. To specify a project associated
to the repository, append ``?project=name`` to the URL.

Note that there is a satandalone HTTP server available for receiving BitBucket
notifications, as well: :file:`contrib/bitbucket_buildbot.py`. This script may be
useful in cases where you cannot expose the WebStatus for public consumption.

.. warning::

    As in the previous case, the incoming HTTP requests for this hook are not
    authenticated bu default. Anyone who can access the web status can "fake"
    a request from BitBucket, potentially causing the buildmaster to run
    arbitrary code.

To protect URL against unauthorized access you should use ``change_hook_auth`` option. ::

  c['status'].append(html.WebStatus(..
                                    change_hook_auth=('user', 'password')))

Then, create a BitBucket service hook (see https://confluence.atlassian.com/display/BITBUCKET/POST+Service+Management) with a WebHook URL like ``http://user:password@builds.mycompany.com/bbot/change_hook/bitbucket``.

Note that as before, not using ``change_hook_auth`` can expose you to security risks.

Google Code hook
################

The Google Code hook is quite similar to the GitHub Hook. It has one option
for the "Post-Commit Authentication Key" used to check if the request is
legitimate::

    c['status'].append(html.WebStatus(
        …,
        change_hook_dialects={'googlecode': {'secret_key': 'FSP3p-Ghdn4T0oqX'}}
    ))

This will add a "Post-Commit URL" for the project in the Google Code
administrative interface, pointing to ``/change_hook/googlecode`` relative to
the root of the web status.

Alternatively, you can use the :ref:`GoogleCodeAtomPoller` :class:`ChangeSource`
that periodically poll the Google Code commit feed for changes.

.. note::

   Google Code doesn't send the branch on which the changes were made. So, the
   hook always returns ``'default'`` as the branch, you can override it with the
   ``'branch'`` option::

      change_hook_dialects={'googlecode': {'secret_key': 'FSP3p-Ghdn4T0oqX', 'branch': 'master'}}

Poller hook
###########

The poller hook allows you to use GET requests to trigger polling. One
advantage of this is your buildbot instance can (at start up) poll to get
changes that happened while it was down, but then you can still use a commit
hook to get fast notification of new changes.

Suppose you have a poller configured like this::

    c['change_source'] = SVNPoller(
        svnurl="https://amanda.svn.sourceforge.net/svnroot/amanda/amanda",
        split_file=split_file_branches)

And you configure your WebStatus to enable this hook::

    c['status'].append(html.WebStatus(
        …,
        change_hook_dialects={'poller': True}
    ))

Then you will be able to trigger a poll of the SVN repository by poking the
``/change_hook/poller`` URL from a commit hook like this::

    curl http://yourbuildbot/change_hook/poller?poller=https%3A%2F%2Famanda.svn.sourceforge.net%2Fsvnroot%2Famanda%2Famanda

If no ``poller`` argument is provided then the hook will trigger polling of all
polling change sources.

You can restrict which pollers the webhook has access to using the ``allowed``
option::

    c['status'].append(html.WebStatus(
        …,
        change_hook_dialects={'poller': {'allowed': ['https://amanda.svn.sourceforge.net/svnroot/amanda/amanda']}}
    ))


.. bb:status:: MailNotifier

.. index:: single: email; MailNotifier

MailNotifier
~~~~~~~~~~~~

.. py:class:: buildbot.status.mail.MailNotifier

The buildbot can also send email when builds finish. The most common
use of this is to tell developers when their change has caused the
build to fail. It is also quite common to send a message to a mailing
list (usually named `builds` or similar) about every build.

The :class:`MailNotifier` status target is used to accomplish this. You
configure it by specifying who mail should be sent to, under what
circumstances mail should be sent, and how to deliver the mail. It can
be configured to only send out mail for certain builders, and only
send messages when the build fails, or when the builder transitions
from success to failure. It can also be configured to include various
build logs in each message.


If a proper lookup function is configured, the message will be sent to the
"interested users" list (:ref:`Doing-Things-With-Users`), which includes all
developers who made changes in the build.  By default, however, Buildbot does
not know how to construct an email addressed based on the information from the
version control system.  See the ``lookup`` argument, below, for more
information.

You can add additional, statically-configured, recipients with the
``extraRecipients`` argument.  You can also add interested users by setting the
``owners`` build property to a list of users in the scheduler constructor
(:ref:`Configuring-Schedulers`).

Each :class:`MailNotifier` sends mail to a single set of recipients. To send
different kinds of mail to different recipients, use multiple
:class:`MailNotifier`\s.

The following simple example will send an email upon the completion of
each build, to just those developers whose :class:`Change`\s were included in
the build. The email contains a description of the :class:`Build`, its results,
and URLs where more information can be obtained. ::

    from buildbot.status.mail import MailNotifier
    mn = MailNotifier(fromaddr="buildbot@example.org", lookup="example.org")
    c['status'].append(mn)

To get a simple one-message-per-build (say, for a mailing list), use
the following form instead. This form does not send mail to individual
developers (and thus does not need the ``lookup=`` argument,
explained below), instead it only ever sends mail to the `extra
recipients` named in the arguments::

    mn = MailNotifier(fromaddr="buildbot@example.org",
                      sendToInterestedUsers=False,
                      extraRecipients=['listaddr@example.org'])

If your SMTP host requires authentication before it allows you to send emails,
this can also be done by specifying ``smtpUser`` and ``smptPassword``::

    mn = MailNotifier(fromaddr="myuser@gmail.com",
                      sendToInterestedUsers=False,
                      extraRecipients=["listaddr@example.org"],
                      relayhost="smtp.gmail.com", smtpPort=587,
                      smtpUser="myuser@gmail.com", smtpPassword="mypassword")

If you want to require Transport Layer Security (TLS), then you can also
set ``useTls``::

    mn = MailNotifier(fromaddr="myuser@gmail.com",
                      sendToInterestedUsers=False,
                      extraRecipients=["listaddr@example.org"],
                      useTls=True, relayhost="smtp.gmail.com", smtpPort=587,
                      smtpUser="myuser@gmail.com", smtpPassword="mypassword")

.. note:: If you see ``twisted.mail.smtp.TLSRequiredError`` exceptions in
   the log while using TLS, this can be due *either* to the server not
   supporting TLS or to a missing `PyOpenSSL`_ package on the buildmaster system.

In some cases it is desirable to have different information then what is
provided in a standard MailNotifier message. For this purpose MailNotifier
provides the argument ``messageFormatter`` (a function) which allows for the
creation of messages with unique content.

For example, if only short emails are desired (e.g., for delivery to phones) ::

    from buildbot.status.builder import Results
    def messageFormatter(mode, name, build, results, master_status):
        result = Results[results]
    
        text = list()
        text.append("STATUS: %s" % result.title())
        return {
            'body' : "\n".join(text),
            'type' : 'plain'
        }
    
    mn = MailNotifier(fromaddr="buildbot@example.org",
                      sendToInterestedUsers=False,
                      mode=('problem',),
                      extraRecipients=['listaddr@example.org'],
                      messageFormatter=messageFormatter)

Another example of a function delivering a customized html email
containing the last 80 log lines of logs of the last build step is
given below::

    from buildbot.status.builder import Results

    import cgi, datetime    

    def html_message_formatter(mode, name, build, results, master_status):
        """Provide a customized message to Buildbot's MailNotifier.
        
        The last 80 lines of the log are provided as well as the changes
        relevant to the build.  Message content is formatted as html.
        """
        result = Results[results]
        
        limit_lines = 80
        text = list()
        text.append(u'<h4>Build status: %s</h4>' % result.upper())
        text.append(u'<table cellspacing="10"><tr>')
        text.append(u"<td>Buildslave for this Build:</td><td><b>%s</b></td></tr>" % build.getSlavename())
        if master_status.getURLForThing(build):
            text.append(u'<tr><td>Complete logs for all build steps:</td><td><a href="%s">%s</a></td></tr>'
                        % (master_status.getURLForThing(build),
                           master_status.getURLForThing(build))
                        )
            text.append(u'<tr><td>Build Reason:</td><td>%s</td></tr>' % build.getReason())
            source = u""
            for ss in build.getSourceStamps():
                if ss.codebase:
                    source += u'%s: ' % ss.codebase
                if ss.branch:
                    source += u"[branch %s] " % ss.branch
                if ss.revision:
                    source +=  ss.revision
                else:
                    source += u"HEAD"
                if ss.patch:
                    source += u" (plus patch)"
                if ss.patch_info: # add patch comment
                    source += u" (%s)" % ss.patch_info[1]
            text.append(u"<tr><td>Build Source Stamp:</td><td><b>%s</b></td></tr>" % source)
            text.append(u"<tr><td>Blamelist:</td><td>%s</td></tr>" % ",".join(build.getResponsibleUsers()))
            text.append(u'</table>')
            if ss.changes:
                text.append(u'<h4>Recent Changes:</h4>')
                for c in ss.changes:
                    cd = c.asDict()
                    when = datetime.datetime.fromtimestamp(cd['when'] ).ctime()
                    text.append(u'<table cellspacing="10">')
                    text.append(u'<tr><td>Repository:</td><td>%s</td></tr>' % cd['repository'] )
                    text.append(u'<tr><td>Project:</td><td>%s</td></tr>' % cd['project'] )
                    text.append(u'<tr><td>Time:</td><td>%s</td></tr>' % when)
                    text.append(u'<tr><td>Changed by:</td><td>%s</td></tr>' % cd['who'] )
                    text.append(u'<tr><td>Comments:</td><td>%s</td></tr>' % cd['comments'] )
                    text.append(u'</table>')
                    files = cd['files']
                    if files:
                        text.append(u'<table cellspacing="10"><tr><th align="left">Files</th></tr>')
                        for file in files:
                            text.append(u'<tr><td>%s:</td></tr>' % file['name'] )
                        text.append(u'</table>')
            text.append(u'<br>')
            # get log for last step 
            logs = build.getLogs()
            # logs within a step are in reverse order. Search back until we find stdio
            for log in reversed(logs):
                if log.getName() == 'stdio':
                    break
            name = "%s.%s" % (log.getStep().getName(), log.getName())
            status, dummy = log.getStep().getResults()
            content = log.getText().splitlines() # Note: can be VERY LARGE
            url = u'%s/steps/%s/logs/%s' % (master_status.getURLForThing(build),
                                           log.getStep().getName(),
                                           log.getName())
            
            text.append(u'<i>Detailed log of last build step:</i> <a href="%s">%s</a>'
                        % (url, url))
            text.append(u'<br>')
            text.append(u'<h4>Last %d lines of "%s"</h4>' % (limit_lines, name))
            unilist = list()
            for line in content[len(content)-limit_lines:]:
                unilist.append(cgi.escape(unicode(line,'utf-8')))
            text.append(u'<pre>'.join([uniline for uniline in unilist]))
            text.append(u'</pre>')
            text.append(u'<br><br>')
            text.append(u'<b>-The Buildbot</b>')
            return {
                'body': u"\n".join(text),
                'type': 'html'
                }
    
    mn = MailNotifier(fromaddr="buildbot@example.org",
                      sendToInterestedUsers=False,
                      mode=('failing',),
                      extraRecipients=['listaddr@example.org'],
                      messageFormatter=html_message_formatter)

MailNotifier arguments
++++++++++++++++++++++

``fromaddr``
    The email address to be used in the 'From' header.

``sendToInterestedUsers``
    (boolean). If ``True`` (the default), send mail to all of the Interested
    Users. If ``False``, only send mail to the ``extraRecipients`` list.

``extraRecipients``
    (list of strings). A list of email addresses to which messages should
    be sent (in addition to the InterestedUsers list, which includes any
    developers who made :class:`Change`\s that went into this build). It is a good
    idea to create a small mailing list and deliver to that, then let
    subscribers come and go as they please.

``subject``
    (string). A string to be used as the subject line of the message.
    ``%(builder)s`` will be replaced with the name of the builder which
    provoked the message.

``mode``
    (list of strings). A combination of:

    ``change``
        Send mail about builds which change status.
    
    ``failing``
        Send mail about builds which fail.

    ``passing``
        Send mail about builds which succeed.
        
    ``problem``
        Send mail about a build which failed when the previous build has passed.

    ``warnings``
        Send mail about builds which generate warnings.

    ``exception``
        Send mail about builds which generate exceptions.

    ``all``
        Always send mail about builds.
        
    Defaults to (``failing``, ``passing``, ``warnings``).

``builders``
    (list of strings). A list of builder names for which mail should be
    sent. Defaults to ``None`` (send mail for all builds). Use either builders
    or categories, but not both.

``categories``
    (list of strings). A list of category names to serve status
    information for. Defaults to ``None`` (all categories). Use either
    builders or categories, but not both.

``addLogs``
    (boolean). If ``True``, include all build logs as attachments to the
    messages. These can be quite large. This can also be set to a list of
    log names, to send a subset of the logs. Defaults to ``False``.

``addPatch``
    (boolean). If ``True``, include the patch content if a patch was present.
    Patches are usually used on a :class:`Try` server.
    Defaults to ``True``.

``buildSetSummary``
    (boolean). If ``True``, send a single summary email consisting of the
    concatenation of all build completion messages rather than a
    completion message for each build.  Defaults to ``False``.

``relayhost``
    (string). The host to which the outbound SMTP connection should be
    made. Defaults to 'localhost'

``smtpPort``
    (int). The port that will be used on outbound SMTP
    connections. Defaults to 25.

``useTls``
    (boolean). When this argument is ``True`` (default is ``False``)
    ``MailNotifier`` sends emails using TLS and authenticates with the
    ``relayhost``. When using TLS the arguments ``smtpUser`` and
    ``smtpPassword`` must also be specified.

``smtpUser``
    (string). The user name to use when authenticating with the
    ``relayhost``. 

``smtpPassword``
    (string). The password that will be used when authenticating with the
    ``relayhost``.

``lookup``
    (implementor of :class:`IEmailLookup`). Object which provides
    :class:`IEmailLookup`, which is responsible for mapping User names (which come
    from the VC system) into valid email addresses.

    If the argument is not provided, the ``MailNotifier`` will attempt to build
    the ``sendToInterestedUsers`` from the authors of the Changes that led to
    the Build via :ref:`User-Objects`.  If the author of one of the Build's
    Changes has an email address stored, it will added to the recipients list.
    With this method, ``owners`` are still added to the recipients.  Note that,
    in the current implementation of user objects, email addresses are not
    stored; as a result, unless you have specifically added email addresses to
    the user database, this functionality is unlikely to actually send any
    emails.

    Most of the time you can use a simple Domain instance. As a shortcut, you
    can pass as string: this will be treated as if you had provided
    ``Domain(str)``. For example, ``lookup='twistedmatrix.com'`` will allow
    mail to be sent to all developers whose SVN usernames match their
    twistedmatrix.com account names. See :file:`buildbot/status/mail.py` for
    more details.

    Regardless of the setting of ``lookup``, ``MailNotifier`` will also send
    mail to addresses in the ``extraRecipients`` list.
    
``messageFormatter``
    This is a optional function that can be used to generate a custom mail message.
    A :func:`messageFormatter` function takes the mail mode (``mode``), builder
    name (``name``), the build status (``build``), the result code
    (``results``), and the BuildMaster status (``master_status``).  It
    returns a dictionary. The ``body`` key gives a string that is the complete
    text of the message. The ``type`` key is the message type ('plain' or
    'html'). The 'html' type should be used when generating an HTML message.  The
    ``subject`` key is optional, but gives the subject for the email.

``extraHeaders``
    (dictionary) A dictionary containing key/value pairs of extra headers to add
    to sent e-mails. Both the keys and the values may be a `Interpolate` instance.

``previousBuildGetter``
    An optional function to calculate the previous build to the one at hand. A
    :func:`previousBuildGetter` takes a :class:`BuildStatus` and returns a
    :class:`BuildStatus`. This function is useful when builders don't process
    their requests in order of arrival (chronologically) and therefore the order
    of completion of builds does not reflect the order in which changes (and
    their respective requests) arrived into the system. In such scenarios,
    status transitions in the chronological sequence of builds within a builder
    might not reflect the actual status transition in the topological sequence
    of changes in the tree. What's more, the latest build (the build at hand)
    might not always be for the most recent request so it might not make sense
    to send a "change" or "problem" email about it. Returning None from this
    function will prevent such emails from going out.

As a help to those writing :func:`messageFormatter` functions, the following
table describes how to get some useful pieces of information from the various
status objects:

Name of the builder that generated this event
    ``name``

Title of the buildmaster
    :meth:`master_status.getTitle()`

MailNotifier mode
    ``mode`` (a combination of ``change``, ``failing``, ``passing``, ``problem``, ``warnings``,
        ``exception``, ``all``)

Builder result as a string ::
    
    from buildbot.status.builder import Results
    result_str = Results[results]
    # one of 'success', 'warnings', 'failure', 'skipped', or 'exception'

URL to build page
    ``master_status.getURLForThing(build)``

URL to buildbot main page.
    ``master_status.getBuildbotURL()``

Build text
    ``build.getText()``

Mapping of property names to values
    ``build.getProperties()`` (a :class:`Properties` instance)

Slave name
    ``build.getSlavename()``

Build reason (from a forced build)
    ``build.getReason()``

List of responsible users
    ``build.getResponsibleUsers()``

Source information (only valid if ss is not ``None``)

    A build has a set of sourcestamps::
        
        for ss in build.getSourceStamp():
            branch = ss.branch
            revision = ss.revision
            patch = ss.patch
            changes = ss.changes # list

    A change object has the following useful information:

    ``who``
        (str) who made this change
        
    ``revision``
        (str) what VC revision is this change
        
    ``branch``
        (str) on what branch did this change occur
        
    ``when``
        (str) when did this change occur
        
    ``files``
        (list of str) what files were affected in this change
        
    ``comments``
        (str) comments reguarding the change.

    The ``Change`` methods :meth:`asText` and :meth:`asDict` can be used to format the
    information above.  :meth:`asText` returns a list of strings and :meth:`asDict` returns
    a dictionary suitable for html/mail rendering.
    
Log information ::
    
    logs = list()
    for log in build.getLogs():
        log_name = "%s.%s" % (log.getStep().getName(), log.getName())
        log_status, dummy = log.getStep().getResults()
        log_body = log.getText().splitlines() # Note: can be VERY LARGE
        log_url = '%s/steps/%s/logs/%s' % (master_status.getURLForThing(build),
                                           log.getStep().getName(),
                                           log.getName())
        logs.append((log_name, log_url, log_body, log_status))

.. bb:status:: IRC

.. index:: IRC

IRC Bot
~~~~~~~

.. py:class:: buildbot.status.words.IRC


The :class:`buildbot.status.words.IRC` status target creates an IRC bot
which will attach to certain channels and be available for status
queries. It can also be asked to announce builds as they occur, or be
told to shut up. ::

    from buildbot.status import words
    irc = words.IRC("irc.example.org", "botnickname",
                    useColors=False,
                    channels=[{"channel": "#example1"},
                              {"channel": "#example2",
                               "password": "somesecretpassword"}],
                    password="mysecretnickservpassword",
                    notify_events={
                      'exception': 1,
                      'successToFailure': 1,
                      'failureToSuccess': 1,
                    })
    c['status'].append(irc)

Take a look at the docstring for :class:`words.IRC` for more details on
configuring this service. Note that the ``useSSL`` option requires
`PyOpenSSL`_.  The ``password`` argument, if provided, will be sent to
Nickserv to claim the nickname: some IRC servers will not allow clients to send
private messages until they have logged in with a password. We can also specify
a different ``port`` number. Default value is 6667.

To use the service, you address messages at the buildbot, either
normally (``botnickname: status``) or with private messages
(``/msg botnickname status``). The buildbot will respond in kind.

The bot will add color to some of its messages. This is enabled by default,
you might turn it off with ``useColors=False`` argument to words.IRC().

If you issue a command that is currently not available, the buildbot
will respond with an error message. If the ``noticeOnChannel=True``
option was used, error messages will be sent as channel notices instead
of messaging. The default value is ``noticeOnChannel=False``.

Some of the commands currently available:

``list builders``
    Emit a list of all configured builders
    
:samp:`status {BUILDER}`
    Announce the status of a specific Builder: what it is doing right now.
    
``status all``
    Announce the status of all Builders
    
:samp:`watch {BUILDER}`
    If the given :class:`Builder` is currently running, wait until the :class:`Build` is
    finished and then announce the results.
    
:samp:`last {BUILDER}`
    Return the results of the last build to run on the given :class:`Builder`.
    
:samp:`join {CHANNEL}`
    Join the given IRC channel
    
:samp:`leave {CHANNEL}`
    Leave the given IRC channel
    
:samp:`notify on|off|list {EVENT}`
    Report events relating to builds.  If the command is issued as a
    private message, then the report will be sent back as a private
    message to the user who issued the command.  Otherwise, the report
    will be sent to the channel.  Available events to be notified are:

    ``started``
        A build has started
        
    ``finished``
        A build has finished
        
    ``success``
        A build finished successfully
        
    ``failure``
        A build failed
        
    ``exception``
        A build generated and exception
        
    ``xToY``
        The previous build was x, but this one is Y, where x and Y are each
        one of success, warnings, failure, exception (except Y is
        capitalized).  For example: ``successToFailure`` will notify if the
        previous build was successful, but this one failed

:samp:`help {COMMAND}`
    Describe a command. Use :command:`help commands` to get a list of known
    commands.

:samp:`shutdown {ARG}`
    Control the shutdown process of the buildbot master.
    Available arguments are:

    ``check``
        Check if the buildbot master is running or shutting down

    ``start``
        Start clean shutdown

    ``stop``
        Stop clean shutdown

    ``now``
        Shutdown immediately without waiting for the builders to finish
    
``source``
    Announce the URL of the Buildbot's home page.
    
``version``
    Announce the version of this Buildbot.

Additionally, the config file may specify default notification options
as shown in the example earlier.

If the ``allowForce=True`` option was used, some additional commands
will be available:

.. index:: Properties; from forced build

:samp:`force build [--branch={BRANCH}] [--revision={REVISION}] [--props=PROP1=VAL1,PROP2=VAL2...] {BUILDER} {REASON}`
    Tell the given :class:`Builder` to start a build of the latest code. The user
    requesting the build and *REASON* are recorded in the :class:`Build` status. The
    buildbot will announce the build's status when it finishes.The
    user can specify a branch and/or revision with the optional
    parameters :samp:`--branch={BRANCH}` and :samp:`--revision={REVISION}`. The user
    can also give a list of properties with :samp:`--props={PROP1=VAL1,PROP2=VAL2..}`.


:samp:`stop build {BUILDER} {REASON}`
    Terminate any running build in the given :class:`Builder`. *REASON* will be added
    to the build status to explain why it was stopped. You might use this
    if you committed a bug, corrected it right away, and don't want to
    wait for the first build (which is destined to fail) to complete
    before starting the second (hopefully fixed) build.

If the `categories` is set to a category of builders (see the categories
option in :ref:`Builder-Configuration`) changes related to only that 
category of builders will be sent to the channel.

If the `useRevisions` option is set to `True`, the IRC bot will send status messages
that replace the build number with a list of revisions that are contained in that
build. So instead of seeing `build #253 of ...`, you would see something like
`build containing revisions [a87b2c4]`. Revisions that are stored as hashes are
shortened to 7 characters in length, as multiple revisions can be contained in one
build and may exceed the IRC message length limit.

Two additional arguments can be set to control how fast the IRC bot tries to
reconnect when it encounters connection issues. ``lostDelay`` is the number of
of seconds the bot will wait to reconnect when the connection is lost, where as
``failedDelay`` is the number of seconds until the bot tries to reconnect when
the connection failed. ``lostDelay`` defaults to a random number between 1 and 5,
while ``failedDelay`` defaults to a random one between 45 and 60. Setting random
defaults like this means multiple IRC bots are less likely to deny each other
by flooding the server.

.. bb:status:: PBListener

PBListener
~~~~~~~~~~

.. @cindex PBListener
.. py:class:: buildbot.status.client.PBListener

::

    import buildbot.status.client
    pbl = buildbot.status.client.PBListener(port=int, user=str,
                                            passwd=str)
    c['status'].append(pbl)

This sets up a PB listener on the given TCP port, to which a PB-based
status client can connect and retrieve status information.
:command:`buildbot statusgui` (:bb:cmdline:`statusgui`) is an example of such a
status client. The ``port`` argument can also be a strports
specification string.

.. bb:status:: StatusPush

StatusPush
~~~~~~~~~~

.. @cindex StatusPush
.. py:class:: buildbot.status.status_push.StatusPush

::

    def Process(self):
      print str(self.queue.popChunk())
      self.queueNextServerPush()
    
    import buildbot.status.status_push
    sp = buildbot.status.status_push.StatusPush(serverPushCb=Process,
                                                bufferDelay=0.5,
                                                retryDelay=5)
    c['status'].append(sp)

:class:`StatusPush` batches events normally processed and sends it to the
:func:`serverPushCb` callback every ``bufferDelay`` seconds. The callback
should pop items from the queue and then queue the next callback.
If no items were popped from ``self.queue``, ``retryDelay`` seconds will be
waited instead.

.. bb:status:: HttpStatusPush

HttpStatusPush
~~~~~~~~~~~~~~

.. @cindex HttpStatusPush
.. @stindex buildbot.status.status_push.HttpStatusPush

::

    import buildbot.status.status_push
    sp = buildbot.status.status_push.HttpStatusPush(
            serverUrl="http://example.com/submit")
    c['status'].append(sp)

:class:`HttpStatusPush` builds on :class:`StatusPush` and sends HTTP requests to
``serverUrl``, with all the items json-encoded. It is useful to create a
status front end outside of buildbot for better scalability.

.. bb:status:: GerritStatusPush

GerritStatusPush
~~~~~~~~~~~~~~~~

.. py:class:: buildbot.status.status_gerrit.GerritStatusPush

::

    from buildbot.status.status_gerrit import GerritStatusPush
    from buildbot.status.builder import Results, SUCCESS, RETRY

    def gerritReviewCB(builderName, build, result, status, arg):
        if result == RETRY:
            return None, 0, 0

        message =  "Buildbot finished compiling your patchset\n"
        message += "on configuration: %s\n" % builderName
        message += "The result is: %s\n" % Results[result].upper()

        if arg:
            message += "\nFor more details visit:\n"
            message += status.getURLForThing(build) + "\n"

        # message, verified, reviewed
        return message, (result == SUCCESS or -1), 0

    def gerritStartCB(builderName, build, arg):
        message = "Buildbot started compiling your patchset\n"
        message += "on configuration: %s\n" % builderName

        if arg:
            message += "\nFor more details visit:\n"
            message += status.getURLForThing(build) + "\n"

        return message

    c['buildbotURL'] = 'http://buildbot.example.com/'
    c['status'].append(GerritStatusPush('127.0.0.1', 'buildbot',
                                        reviewCB=gerritReviewCB,
                                        reviewArg=c['buildbotURL'],
                                        startCB=gerritStartCB,
                                        startArg=c['buildbotURL']))

GerritStatusPush sends review of the :class:`Change` back to the Gerrit server,
optionally also sending a message when a build is started.
``reviewCB`` should return a tuple of message, verified, reviewed. If message
is ``None``, no review will be sent.
``startCB`` should return a message.

.. bb:status:: GitHubStatus

GitHubStatus
~~~~~~~~~~~~

.. @cindex GitHubStatus
.. py:class:: buildbot.status.github.GitHubStatus

::

    from buildbot.status.github import GitHubStatus

    repoOwner = Interpolate("%(prop:github_repo_owner)s"
    repoName = Interpolate("%(prop:github_repo_name)s"
    sha = Interpolate("%(src::revision)s")
    gs = GitHubStatus(token='githubAPIToken',
                      repoOwner=repoOwner,
                      repoName=repoName)
                      sha=sha,
                      startDescription='Build started.',
                      endDescription='Build done.',
                      )
    buildbot_bbtools = BuilderConfig(
        name='builder-name',
        slavenames=['slave1'],
        factory=BuilderFactory(),
        properties={
            "github_repo_owner": "buildbot",
            "github_repo_name": "bbtools",
            },
        )
    c['builders'].append(buildbot_bbtools)
    c['status'].append(gs)

:class:`GitHubStatus` publishes a build status using
`GitHub Status API <http://developer.github.com/v3/repos/statuses>`_.

It requires `txgithub <https://pypi.python.org/pypi/txgithub>` package to
allow interaction with GitHub API.

It is configured with at least a GitHub API token, repoOwner and repoName
arguments.

You can create a token from you own
`GitHub - Profile - Applications - Register new application
<https://github.com/settings/applications>`_ or use an external tool to
generate one.

`repoOwner`, `repoName` are used to inform the plugin where
to send status for build. This allow using a single :class:`GitHubStatus` for
multiple projects.
`repoOwner`, `repoName` can be passes as a static `string` (for single
project) or :class:`Interpolate` for dynamic substitution in multiple
project.

`sha` argument is use to define the commit SHA for which to send the status.
By default `sha` is defined as: `%(src::revision)s`.

In case any of `repoOwner`, `repoName` or `sha` returns `None`, `False` or
empty string, the plugin will skip sending the status.

You can define custom start and end build messages using the
`startDescription` and `endDescription` optional interpolation arguments.


.. [#] Apparently this is the same way http://buildd.debian.org displays build status

.. [#] It may even be possible to provide SSL access by using a
    specification like ``"ssl:12345:privateKey=mykey.pen:certKey=cert.pem"``,
    but this is completely untested

.. _PyOpenSSL: http://pyopenssl.sourceforge.net/

