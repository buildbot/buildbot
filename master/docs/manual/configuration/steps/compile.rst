.. bb:step:: Compile

.. _Step-Compile:

Compile
+++++++

.. index:: Properties; warnings-count

This is meant to handle compiling or building a project written in C.
The default command is ``make all``.
When the compilation is finished, the log file is scanned for GCC warning messages, a summary log is created with any problems that were seen, and the step is marked as WARNINGS if any were discovered.
Through the :class:`WarningCountingShellCommand` superclass, the number of warnings is stored in a Build Property named `warnings-count`, which is accumulated over all :bb:step:`Compile` steps (so if two warnings are found in one step, and three are found in another step, the overall build will have a `warnings-count` property of 5).
Each step can be optionally given a maximum number of warnings via the maxWarnCount parameter.
If this limit is exceeded, the step will be marked as a failure.

The default regular expression used to detect a warning is ``'.*warning[: ].*'`` , which is fairly liberal and may cause false-positives.
To use a different regexp, provide a ``warningPattern=`` argument, or use a subclass which sets the ``warningPattern`` attribute:

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.Compile(command=["make", "test"],
                            warningPattern="^Warning: "))

The ``warningPattern=`` can also be a pre-compiled Python regexp object: this makes it possible to add flags like ``re.I`` (to use case-insensitive matching).

If ``warningPattern`` is set to ``None`` then warning counting is disabled.

Note that the compiled ``warningPattern`` will have its :meth:`match` method called, which is subtly different from a :meth:`search`.
Your regular expression must match the from the beginning of the line.
This means that to look for the word "warning" in the middle of a line, you will need to prepend ``'.*'`` to your regular expression.

The ``suppressionFile=`` argument can be specified as the (relative) path of a file inside the workdir defining warnings to be suppressed from the warning counting and log file.
The file will be uploaded to the master from the worker before compiling, and any warning matched by a line in the suppression file will be ignored.
This is useful to accept certain warnings (e.g. in some special module of the source tree or in cases where the compiler is being particularly stupid), yet still be able to easily detect and fix the introduction of new warnings.

The file must contain one line per pattern of warnings to ignore.
Empty lines and lines beginning with ``#`` are ignored.
Other lines must consist of a regexp matching the file name, followed by a colon (``:``), followed by a regexp matching the text of the warning.
Optionally this may be followed by another colon and a line number range.
For example:

.. code-block:: none

    # Sample warning suppression file

    mi_packrec.c : .*result of 32-bit shift implicitly converted to 64 bits.* : 560-600
    DictTabInfo.cpp : .*invalid access to non-static.*
    kernel_types.h : .*only defines private constructors and has no friends.* : 51

If no line number range is specified, the pattern matches the whole file; if only one number is given it matches only on that line.

The ``suppressionList=`` argument can be specified as a list of four-tuples as addition or instead of ``suppressionFile=``.
The tuple should be ``[ FILE-RE, WARNING-RE, START, END ]``.
If ``FILE-RE`` is ``None``, then the suppression applies to any file.
``START`` and ``END`` can be specified as in suppression file, or ``None``.

The default warningPattern regexp only matches the warning text, so line numbers and file names are ignored.
To enable line number and file name matching, provide a different regexp and provide a function (callable) as the argument of ``warningExtractor=``.
The function is called with three arguments: the :class:`BuildStep` object, the line in the log file with the warning, and the ``SRE_Match`` object of the regexp search for ``warningPattern``.
It should return a tuple ``(filename, linenumber, warning_test)``.
For example:

.. code-block:: python

    f.addStep(Compile(command=["make"],
                      warningPattern="^(.\*?):([0-9]+): [Ww]arning: (.\*)$",
                      warningExtractor=Compile.warnExtractFromRegexpGroups,
                      suppressionFile="support-files/compiler_warnings.supp"))

(``Compile.warnExtractFromRegexpGroups`` is a pre-defined function that returns the filename, linenumber, and text from groups (1,2,3) of the regexp match).

In projects with source files in multiple directories, it is possible to get full path names for file names matched in the suppression file, as long as the build command outputs the names of directories as they are entered into and left again.
For this, specify regexps for the arguments ``directoryEnterPattern=`` and ``directoryLeavePattern=``.
The ``directoryEnterPattern=`` regexp should return the name of the directory entered into in the first matched group.
The defaults, which are suitable for GNU Make, are these:

.. code-block:: python

    directoryEnterPattern="make.*: Entering directory [\"`'](.*)['`\"]"
    directoryLeavePattern="make.*: Leaving directory"

(TODO: this step needs to be extended to look for GCC error messages as well, and collect them into a separate logfile, along with the source code filenames involved).
