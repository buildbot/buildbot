.. bb:step:: GitDiffInfo

.. _Step-GitDiffInfo:

GitDiffInfo
+++++++++++

The `GitDiffInfo` step gathers information about differences between the current revision and the last common ancestor of this revision and another commit or branch.
This information is useful for various reporters to be able to identify new warnings that appear in newly modified code.
The diff information is stored as a custom json as transient build data via ``setBuildData`` function.

Currently only git repositories are supported.

The class inherits the arguments accepted by ``ShellMixin`` except ``command``.

Additionally, it accepts the following arguments:

``compareToRef``
    (Optional, string, defaults to ``master``)
    The commit or branch identifying the revision to get the last common ancestor to.
    In most cases, this will be the target branch of a pull or merge request.

``dataName``
    (Optional, string, defaults to ``diffinfo-master``)
    The name of the build data to save the diff json to.

Build data specification
------------------------

This section documents the format of the data produced by the ``GitDiffInfo`` step and put into build data.
Any future steps performing the same operation on different version control systems should produce data in the same format.
Likewise, all consumers should expect the input data to be in the format as documented here.

Conceptually, the diffinfo data is a list of file changes, each of which itself contain a list of diff hunks within that file.

This data is stored as a JSON document.

The root element is a list of objects, each of which represent a file where changes have been detected.
Each of these **file** objects has the following keys:

- ``source_file`` - a string representing path to the source file.
  This does not include any prefixes such as ``a/``.
  When there is no source file, e.g. when a new file is created, ``/dev/null`` is used.

- ``target_file`` - a string representing path to the target file.
  This does not include any prefixes such as ``b/``.
  When there is no target file, e.g. when a file has been deleted, ``/dev/null`` is used.

- ``is_binary`` - a boolean specifying whether this is a binary file or not.
  Changes in binary files are not interpreted as hunks.

- ``is_rename`` - a boolean specifying whether this file has been renamed

- ``hunks`` - a list of objects (described below) specifying individual changes within the file.

Each of the **hunk** objects has the following keys:

- ``ss`` - an integer specifying the start line of the diff hunk in the source file

- ``sl`` - an integer specifying the length of the hunk in the source file as a number of lines

- ``ts`` - an integer specifying the start line of the diff hunk in the target file

- ``tl`` - an integer specifying the length of the hunk in the target file as a number lines

Example of produced build data
------------------------------

The following shows build data that is produced for a deleted file, a changed file and a new file.

.. code-block:: python

    [
      {
        "source_file": "file1",
        "target_file": "/dev/null",
        "is_binary": false,
        "is_rename": false,
        "hunks": [
          {
            "ss": 1,
            "sl": 3,
            "ts": 0,
            "tl": 0
          }
        ]
      },
      {
        "source_file": "file2",
        "target_file": "file2",
        "is_binary": false,
        "is_rename": false,
        "hunks": [
          {
            "ss": 4,
            "sl": 0,
            "ts": 5,
            "tl": 3
          },
          {
            "ss": 15,
            "sl": 0,
            "ts": 19,
            "tl": 3
          }
        ]
      },
      {
        "source_file": "/dev/null",
        "target_file": "file3",
        "is_binary": false,
        "is_rename": false,
        "hunks": [
          {
            "ss": 0,
            "sl": 0,
            "ts": 1,
            "tl": 3
          }
        ]
      }
    ]
