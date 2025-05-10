.. _Customizing-SVNPoller:

Customizing SVNPoller
---------------------

Each source file that is tracked by a Subversion repository has a fully-qualified SVN URL in the
following form: :samp:`({REPOURL})({PROJECT-plus-BRANCH})({FILEPATH})`. When you create the
:bb:chsrc:`SVNPoller`, you give it a ``repourl`` value that includes all of the :samp:`{REPOURL}`
and possibly some portion of the :samp:`{PROJECT-plus-BRANCH}` string. The :bb:chsrc:`SVNPoller` is
responsible for producing Changes that contain a branch name and a :samp:`{FILEPATH}` (which is
relative to the top of a checked-out tree). The details of how these strings are split up depend
upon how your repository names its branches.

:samp:`{PROJECT}/{BRANCHNAME}/{FILEPATH}` repositories
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One common layout is to have all the various projects that share a repository get a single
top-level directory each, with ``branches``, ``tags``, and ``trunk`` subdirectories:

.. code-block:: none

    amanda/trunk
          /branches/3_2
                   /3_3
          /tags/3_2_1
               /3_2_2
               /3_3_0

To set up a :bb:chsrc:`SVNPoller` that watches the Amanda trunk (and nothing else), we would use
the following, using the default ``split_file``:

.. code-block:: python

    from buildbot.plugins import changes
    c['change_source'] = changes.SVNPoller(
       repourl="https://svn.amanda.sourceforge.net/svnroot/amanda/amanda/trunk")

In this case, every Change that our :bb:chsrc:`SVNPoller` produces will have its branch attribute
set to ``None``, to indicate that the Change is on the trunk. No other sub-projects or branches
will be tracked.

If we want our ChangeSource to follow multiple branches, we have to do two things. First we have to
change our ``repourl=`` argument to watch more than just ``amanda/trunk``. We will set it to
``amanda`` so that we'll see both the trunk and all the branches. Second, we have to tell
:bb:chsrc:`SVNPoller` how to split the :samp:`({PROJECT-plus-BRANCH})({FILEPATH})` strings it gets
from the repository out into :samp:`({BRANCH})` and :samp:`({FILEPATH})`.

We do the latter by providing a ``split_file`` function. This function is responsible for splitting
something like ``branches/3_3/common-src/amanda.h`` into ``branch='branches/3_3'`` and
``filepath='common-src/amanda.h'``. The function is always given a string that names a file
relative to the subdirectory pointed to by the :bb:chsrc:`SVNPoller`\'s ``repourl=`` argument. It
is expected to return a dictionary with at least the ``path`` key. The splitter may optionally set
``branch``, ``project`` and ``repository``. For backwards compatibility it may return a tuple of
``(branchname, path)``. It may also return ``None`` to indicate that the file is of no interest.

.. note::

   The function should return ``branches/3_3`` rather than just ``3_3`` because the SVN checkout
   step, will append the branch name to the ``baseURL``, which requires that we keep the
   ``branches`` component in there. Other VC schemes use a different approach towards branches and
   may not require this artifact.

If your repository uses this same ``{PROJECT}/{BRANCH}/{FILEPATH}`` naming scheme, the following
function will work:

.. code-block:: python

    def split_file_branches(path):
        pieces = path.split('/')
        if len(pieces) > 1 and pieces[0] == 'trunk':
            return (None, '/'.join(pieces[1:]))
        elif len(pieces) > 2 and pieces[0] == 'branches':
            return ('/'.join(pieces[0:2]),
                    '/'.join(pieces[2:]))
        else:
            return None

In fact, this is the definition of the provided ``split_file_branches`` function.
So to have our Twisted-watching :bb:chsrc:`SVNPoller` follow multiple branches, we would use this:

.. code-block:: python

    from buildbot.plugins import changes, util
    c['change_source'] = changes.SVNPoller("svn://svn.twistedmatrix.com/svn/Twisted",
                                           split_file=util.svn.split_file_branches)

Changes for all sorts of branches (with names like ``"branches/1.5.x"``, and ``None`` to indicate
the trunk) will be delivered to the Schedulers. Each Scheduler is then free to use or ignore each
branch as it sees fit.

If you have multiple projects in the same repository your split function can attach a project name
to the Change to help the Scheduler filter out unwanted changes:

.. code-block:: python

    from buildbot.plugins import util
    def split_file_projects_branches(path):
        if not "/" in path:
            return None
        project, path = path.split("/", 1)
        f = util.svn.split_file_branches(path)
        if f:
            info = {"project": project, "path": f[1]}
            if f[0]:
                info['branch'] = f[0]
            return info
        return f

Again, this is provided by default.
To use it you would do this:

.. code-block:: python

    from buildbot.plugins import changes, util
    c['change_source'] = changes.SVNPoller(
       repourl="https://svn.amanda.sourceforge.net/svnroot/amanda/",
       split_file=util.svn.split_file_projects_branches)

Note here that we are monitoring at the root of the repository, and that within that repository is
a ``amanda`` subdirectory which in turn has ``trunk`` and ``branches``. It is that ``amanda``
subdirectory whose name becomes the ``project`` field of the Change.


:samp:`{BRANCHNAME}/{PROJECT}/{FILEPATH}` repositories
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Another common way to organize a Subversion repository is to put the branch name at the top, and
the projects underneath. This is especially frequent when there are a number of related
sub-projects that all get released in a group.

For example, ``Divmod.org`` hosts a project named `Nevow` as well as one named `Quotient`. In a
checked-out Nevow tree there is a directory named `formless` that contains a Python source file
named :file:`webform.py`. This repository is accessible via webdav (and thus uses an `http:`
scheme) through the divmod.org hostname. There are many branches in this repository, and they use a
``({BRANCHNAME})/({PROJECT})`` naming policy.

The fully-qualified SVN URL for the trunk version of :file:`webform.py` is
``http://divmod.org/svn/Divmod/trunk/Nevow/formless/webform.py``. The 1.5.x branch version of this
file would have a URL of ``http://divmod.org/svn/Divmod/branches/1.5.x/Nevow/formless/webform.py``.
The whole Nevow trunk would be checked out with ``http://divmod.org/svn/Divmod/trunk/Nevow``, while
the Quotient trunk would be checked out using ``http://divmod.org/svn/Divmod/trunk/Quotient``.

Now suppose we want to have an :bb:chsrc:`SVNPoller` that only cares about the Nevow trunk. This
case looks just like the :samp:`{PROJECT}/{BRANCH}` layout described earlier:

.. code-block:: python

    from buildbot.plugins import changes
    c['change_source'] = changes.SVNPoller("http://divmod.org/svn/Divmod/trunk/Nevow")

But what happens when we want to track multiple Nevow branches? We have to point our ``repourl=``
high enough to see all those branches, but we also don't want to include Quotient changes (since
we're only building Nevow). To accomplish this, we must rely upon the ``split_file`` function to
help us tell the difference between files that belong to Nevow and those that belong to Quotient,
as well as figuring out which branch each one is on.

.. code-block:: python

    from buildbot.plugins import changes
    c['change_source'] = changes.SVNPoller("http://divmod.org/svn/Divmod",
                                           split_file=my_file_splitter)

The ``my_file_splitter`` function will be called with repository-relative pathnames like:

:file:`trunk/Nevow/formless/webform.py`
    This is a Nevow file, on the trunk.
    We want the Change that includes this to see a filename of :file:`formless/webform.py`, and a branch of ``None``

:file:`branches/1.5.x/Nevow/formless/webform.py`
    This is a Nevow file, on a branch.
    We want to get ``branch='branches/1.5.x'`` and ``filename='formless/webform.py'``.

:file:`trunk/Quotient/setup.py`
    This is a Quotient file, so we want to ignore it by having :meth:`my_file_splitter` return ``None``.

:file:`branches/1.5.x/Quotient/setup.py`
    This is also a Quotient file, which should be ignored.

The following definition for :meth:`my_file_splitter` will do the job:

.. code-block:: python

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
        return {"branch": branch, "path": "/".join(pieces)}

If you later decide you want to get changes for Quotient as well you could replace the last 3 lines with simply:

.. code-block:: python

    return {"project": projectname, "branch": branch, "path": '/'.join(pieces)}
