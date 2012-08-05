Release Notes for Buildbot |version|
====================================

..
    Any change that adds a feature or fixes a bug should have an entry here.
    Most simply need an additional bulleted list item, but more significant
    changes can be given a subsection of their own.

The following are the release notes for Buildbot |version|.

Master
------

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Buildbot master now requires at least Python-2.5 and Twisted-9.0.0.

* Buildbot master requires ``python-dateutil`` version 1.5 to support the
  Nightly scheduler.

* ``ForceScheduler`` has been updated to support multiple :ref:`codebases<Attr-Codebase>`.
  The branch/revision/repository/project are deprecated; if you have customized these
  values, simply provide them as ``codebases=[CodebaseParameter(name='', ...)]``.

* The POST URL names for ``AnyPropertyParameter`` fields have changed. For example,
  'property1name' is now 'property1_name', and 'property1value' is now 'property1_value'.
  Please update any bookmarked or saved URL's that used these fields.

* ``forcesched.BaseParameter`` API has changed quite a bit and is no longer backwards
  compatible. Updating guidelines:
  
  * ``get_from_post`` is renamed to ``getFromKwargs``
  * ``update_from_post`` is renamed to ``updateFromKwargs``. This function's parameters
    are now called via named parameters to allow subclasses to ignore values it doesnt use.
    Subclasses should add ``**unused`` for future compatibility. A new parameter
    ``sourcestampset`` to provided to allow subclasses to modify the sourcestamp set, and
    will probably require you to add the ``**unused`` field.

* The configurable callable build.workdir has changed his parameterlist. Instead
  of a single sourcestamp a list of sourcestamps is passed. Each sourcestamp in 
  the list has a different :ref:`codebase<Attr-Codebase>`

* BK support has been removed in this release - see :bb:bug:`2198`.

* The undocumented renderable ``_ComputeRepositoryURL`` is no longer imported to
  :py:mod:`buildbot.steps.source`. It is still available at
  :py:mod:`buildbot.steps.source.oldsource`.

* ``IProperties.render`` now returns a deferred, so any code rendering properties
  by hand will need to take this into account.

* ``baseURL`` has been removed in :bb:step:`SVN` to use just ``repourl`` - see
  :bb:bug:`2066`. Branch info should be provided with ``Interpolate``. ::

    from buildbot.steps.source.svn import SVN
    factory.append(SVN(baseURL="svn://svn.example.org/svn/"))

  can be replaced with ::

    from buildbot.process.properties import Interpolate
    from buildbot.steps.source.svn import SVN
    factory.append(SVN(repourl=Interpolate("svn://svn.example.org/svn/%(src::branch)s")))

  and ::

    from buildbot.steps.source.svn import SVN
    factory.append(SVN(baseURL="svn://svn.example.org/svn/%%BRANCH%%/project"))

  can be replaced with ::

    from buildbot.process.properties import Interpolate
    from buildbot.steps.source.svn import SVN
    factory.append(SVN(repourl=Interpolate("svn://svn.example.org/svn/%(src::branch)s/project")))

  and ::

    from buildbot.steps.source.svn import SVN
    factory.append(SVN(baseURL="svn://svn.example.org/svn/", defaultBranch="branches/test"))

  can be replaced with ::

    from buildbot.process.properties import Interpolate
    from buildbot.steps.source.svn import SVN
    factory.append(SVN(repourl=Interpolate("svn://svn.example.org/svn/%(src::branch:-branches/test)s")))

* The ``P4Sync`` step, deprecated since 0.8.5, has been removed.  The ``P4`` step remains.


* The ``fetch_spec`` argument to ``GitPoller`` is no longer supported.
  ``GitPoller`` now only downloads branches that it is polling, so specifies a refspec itself.

* The format of the changes produced by :bb:chsrc:`SVNPoller` has changed: directory pathnames end with a forward slash.
  This allows the ``split_file`` function to distinguish between files and directories.
  Customized split functions may need to be adjusted accordingly.

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

* ``BuildStep.start`` can now optionally return a deferred and any errback will
  be handled gracefully. If you use inlineCallbacks, this means that unexpected
  exceptions and failures raised will be captured and logged and the build shut
  down normally.

* The helper methods ``getState`` and ``setState`` from ``BaseScheduler`` have
  been factored into ``buildbot.util.state.StateMixin`` for use elsewhere.

Features
~~~~~~~~

* Buildbot now supports building projects composed of multiple codebases.  New
  schedulers can aggregate changes to multiple codebases into source stamp sets
  (with one source stamp for each codebase).  Source steps then check out each
  codebase as required, and the remainder of the build process proceeds
  normally.  See the :ref:`Multiple-Codebase-Builds` for details.

* ``Source`` and ``ShellCommand`` steps now have an optional ``descriptionSuffix``, a suffix to the
   ``description``/``descriptionDone`` values. For example this can help distinguish between
    multiple ``Compile`` steps that are applied to different codebases.

* ``Git`` has a new ``getDescription`` option, which will run `git describe` after checkout
  normally.  See the documentation for details.

* A new ternary substitution operator ``:?:`` and ``:#?:`` to use with the ``Interpolate``
  and ``WithProperties`` classes.

* The mercurial hook now supports multple masters.  See :bb:pull:`436`.

* There's a new poller for Mercurial: :bb:chsrc:`HgPoller`. 

* The new ``HTPasswdAprAuth`` use libaprutil through ctypes to validate
  the password against the hash from the .htpasswd file. This adds support for
  all hash types htpasswd can generate.

* ``GitPoller`` has been rewritten.
  It now supports multiple branches and can share a directory between multiple pollers.
  It is also more resilient to changes in configuration, or in the underlying repository.

* Added a new property ``httpLoginUrl`` to ``buildbot.status.web.authz.Authz``
  to render a nice Login link in WebStatus for unauthenticated users if
  ``useHttpHeader`` and ``httpLoginUrl`` are set.
  
* ``ForceScheduler`` has been updated:

  * support for multiple :ref:`codebases<Attr-Codebase>` via the ``codebases`` parameter
  * ``NestedParameter`` to provide a logical grouping of parameters.
  * ``CodebaseParameter`` to set the branch/revision/repository/project for a codebase
  * new HTML/CSS customization points. Each parameter is contained in a ``row`` with multiple
    'class' attributes associated with them (eg, 'force-string' and 'force-nested') as well as a unique
    id to use with Javascript. Explicit line-breaks have been removed from the HTML generator and
    are now controlled using CSS. 

Slave
-----

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Features
~~~~~~~~

* ``IRenderable.getRenderingFor`` can now return a deferred.

Details
-------

For a more detailed description of the changes made in this version, see the
git log itself:

   git log v0.8.6..master

Older Versions
--------------

Release notes for older versions of Buildbot are available in the :bb:src:`master/docs/release-notes/` directory of the source tree.
Starting with version 0.8.6, they are also available under the appropriate version at http://buildbot.net/buildbot/docs.
