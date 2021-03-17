
.. index:: File Transfer

.. bb:step:: FileUpload
.. bb:step:: FileDownload

.. _Step-FileTransfer:

Transferring Files
------------------

.. py:class:: buildbot.steps.transfer.FileUpload
.. py:class:: buildbot.steps.transfer.FileDownload

Most of the work involved in a build will take place on the worker.
But occasionally it is useful to do some work on the buildmaster side.
The most basic way to involve the buildmaster is simply to move a file from the worker to the master, or vice versa.
There are a pair of steps named :bb:step:`FileUpload` and :bb:step:`FileDownload` to provide this functionality.
:bb:step:`FileUpload` moves a file *up to* the master, while :bb:step:`FileDownload` moves a file *down from* the master.

As an example, let's assume that there is a step which produces an HTML file within the source tree that contains some sort of generated project documentation.
And let's assume that we run nginx web server on the buildmaster host for serving static files.
We want to move this file to the buildmaster, into a :file:`/usr/share/nginx/www/` directory, so it can be visible to developers.
This file will wind up in the worker-side working directory under the name :file:`docs/reference.html`.
We want to put it into the master-side :file:`/usr/share/nginx/www/ref.html`, and add a link to the HTML status to the uploaded file.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.ShellCommand(command=["make", "docs"]))
    f.addStep(steps.FileUpload(workersrc="docs/reference.html",
                               masterdest="/usr/share/nginx/www/ref.html",
                               url="http://somesite/~buildbot/ref.html"))

The ``masterdest=`` argument will be passed to :meth:`os.path.expanduser`, so things like ``~`` will be expanded properly.
Non-absolute paths will be interpreted relative to the buildmaster's base directory.
Likewise, the ``workersrc=`` argument will be expanded and interpreted relative to the builder's working directory.

.. note::

   The copied file will have the same permissions on the master as on the worker, look at the ``mode=`` parameter to set it differently.

To move a file from the master to the worker, use the :bb:step:`FileDownload` command.
For example, let's assume that some step requires a configuration file that, for whatever reason, could not be recorded in the source code repository or generated on the worker side:

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.FileDownload(mastersrc="~/todays_build_config.txt",
                                 workerdest="build_config.txt"))
    f.addStep(steps.ShellCommand(command=["make", "config"]))

Like :bb:step:`FileUpload`, the ``mastersrc=`` argument is interpreted relative to the buildmaster's base directory, and the ``workerdest=`` argument is relative to the builder's working directory.
If the worker is running in :file:`~worker`, and the builder's ``builddir`` is something like :file:`tests-i386`, then the workdir is going to be :file:`~worker/tests-i386/build`, and a ``workerdest=`` of :file:`foo/bar.html` will get put in :file:`~worker/tests-i386/build/foo/bar.html`.
Both of these commands will create any missing intervening directories.

Other Parameters
++++++++++++++++

The ``maxsize=`` argument lets you set a maximum size for the file to be transferred.
This may help to avoid surprises: transferring a 100MB coredump when you were expecting to move a 10kB status file might take an awfully long time.
The ``blocksize=`` argument controls how the file is sent over the network: larger blocksizes are slightly more efficient but also consume more memory on each end, and there is a hard-coded limit of about 640kB.

The ``mode=`` argument allows you to control the access permissions of the target file, traditionally expressed as an octal integer.
The most common value is probably ``0o755``, which sets the `x` executable bit on the file (useful for shell scripts and the like).
The default value for ``mode=`` is ``None``, which means the permission bits will default to whatever the umask of the writing process is.
The default umask tends to be fairly restrictive, but at least on the worker you can make it less restrictive with a ``--umask`` command-line option at creation time (:ref:`Worker-Options`).

The ``keepstamp=`` argument is a boolean that, when ``True``, forces the modified and accessed time of the destination file to match the times of the source file.
When ``False`` (the default), the modified and accessed times of the destination file are set to the current time on the buildmaster.

The ``url=`` argument allows you to specify an url that will be displayed in the HTML status.
The title of the url will be the name of the item transferred (directory for :class:`DirectoryUpload` or file for :class:`FileUpload`).
This allows the user to add a link to the uploaded item if that one is uploaded to an accessible place.

For :bb:step:`FileUpload`, the ``urlText=`` argument allows you to specify the url title that will be displayed in the web UI.

.. bb:step:: DirectoryUpload

Transferring Directories
++++++++++++++++++++++++

.. py:class:: buildbot.steps.transfer.DirectoryUpload

To transfer complete directories from the worker to the master, there is a :class:`BuildStep` named :bb:step:`DirectoryUpload`.
It works like :bb:step:`FileUpload`, just for directories.
However it does not support the ``maxsize``, ``blocksize`` and ``mode`` arguments.
As an example, let's assume an generated project documentation, which consists of many files (like the output of :command:`doxygen` or :command:`epydoc`).
And let's assume that we run nginx web server on buildmaster host for serving static files.
We want to move the entire documentation to the buildmaster, into a :file:`/usr/share/nginx/www/docs` directory, and add a link to the uploaded documentation on the HTML status page.
On the worker-side the directory can be found under :file:`docs`:

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.ShellCommand(command=["make", "docs"]))
    f.addStep(steps.DirectoryUpload(workersrc="docs",
                                    masterdest="/usr/share/nginx/www/docs",
                                    url="~buildbot/docs"))

The :bb:step:`DirectoryUpload` step will create all necessary directories and transfers empty directories, too.

The ``maxsize`` and ``blocksize`` parameters are the same as for :bb:step:`FileUpload`, although note that the size of the transferred data is implementation-dependent, and probably much larger than you expect due to the encoding used (currently tar).

The optional ``compress`` argument can be given as ``'gz'`` or ``'bz2'`` to compress the datastream.

For :bb:step:`DirectoryUpload` the ``urlText=`` argument allows you to specify the url title that will be displayed in the web UI.

.. note::

   The permissions on the copied files will be the same on the master as originally on the worker, see option ``buildbot-worker create-worker --umask`` to change the default one.

.. bb:step:: MultipleFileUpload

Transferring Multiple Files At Once
+++++++++++++++++++++++++++++++++++

.. py:class:: buildbot.steps.transfer.MultipleFileUpload

In addition to the :bb:step:`FileUpload` and :bb:step:`DirectoryUpload` steps there is the :bb:step:`MultipleFileUpload` step for uploading a bunch of files (and directories) in a single :class:`BuildStep`.
The step supports all arguments that are supported by :bb:step:`FileUpload` and :bb:step:`DirectoryUpload`, but instead of a the single ``workersrc`` parameter it takes a (plural) ``workersrcs`` parameter.
This parameter should either be a list, something that can be rendered as a list or a string which will be converted to a list.
Additionally it supports the ``glob`` parameter if this parameter is set to ``True`` all arguments in ``workersrcs`` will be parsed through ``glob`` and the results will be uploaded to ``masterdest``.:

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.ShellCommand(command=["make", "test"]))
    f.addStep(steps.ShellCommand(command=["make", "docs"]))
    f.addStep(steps.MultipleFileUpload(workersrcs=["docs", "test-results.html"],
                                       masterdest="/usr/share/nginx/www/",
                                       url="~buildbot"))

The ``url=`` parameter, can be used to specify a link to be displayed in the HTML status of the step.

The way URLs are added to the step can be customized by extending the :bb:step:`MultipleFileUpload` class.
The `allUploadsDone` method is called after all files have been uploaded and sets the URL.
The `uploadDone` method is called once for each uploaded file and can be used to create file-specific links.

.. code-block:: python

    import os

    from buildbot.plugins import steps

    class CustomFileUpload(steps.MultipleFileUpload):
        linkTypes = ('.html', '.txt')

        def linkFile(self, basename):
            name, ext = os.path.splitext(basename)
            return ext in self.linkTypes

        def uploadDone(self, result, source, masterdest):
            if self.url:
                basename = os.path.basename(source)
                if self.linkFile(basename):
                    self.addURL(self.url + '/' + basename, basename)

        def allUploadsDone(self, result, sources, masterdest):
            if self.url:
                notLinked = [src for src in sources if not self.linkFile(src)]
                numFiles = len(notLinked)
                if numFiles:
                    self.addURL(self.url, '... %d more' % numFiles)

For :bb:step:`MultipleFileUpload` the ``urlText=`` argument allows you to specify the url title that will be displayed in the web UI.

.. bb:step:: StringDownload
.. bb:step:: JSONStringDownload
.. bb:step:: JSONPropertiesDownload

Transferring Strings
--------------------

.. py:class:: buildbot.steps.transfer.StringDownload
.. py:class:: buildbot.steps.transfer.JSONStringDownload
.. py:class:: buildbot.steps.transfer.JSONPropertiesDownload

Sometimes it is useful to transfer a calculated value from the master to the worker.
Instead of having to create a temporary file and then use FileDownload, you can use one of the string download steps.

.. code-block:: python

    from buildbot.plugins import steps, util

    f.addStep(steps.StringDownload(util.Interpolate("%(src::branch)s-%(prop:got_revision)s\n"),
            workerdest="buildid.txt"))

:bb:step:`StringDownload` works just like :bb:step:`FileDownload` except it takes a single argument, ``s``, representing the string to download instead of a ``mastersrc`` argument.

.. code-block:: python

    from buildbot.plugins import steps

    buildinfo = {
        'branch': Property('branch'),
        'got_revision': Property('got_revision')
    }
    f.addStep(steps.JSONStringDownload(buildinfo, workerdest="buildinfo.json"))

:bb:step:`JSONStringDownload` is similar, except it takes an ``o`` argument, which must be JSON serializable, and transfers that as a JSON-encoded string to the worker.

.. index:: Properties; JSONPropertiesDownload

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.JSONPropertiesDownload(workerdest="build-properties.json"))

:bb:step:`JSONPropertiesDownload` transfers a json-encoded string that represents a dictionary where properties maps to a dictionary of build property ``name`` to property ``value``; and ``sourcestamp`` represents the build's sourcestamp.
