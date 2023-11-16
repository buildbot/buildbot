.. _SourceStampFilter:

SourceStampFilter
+++++++++++++++++

.. py:class:: buildbot.util.SourceStampFilter

This class is used to filter source stamps.
It is conceptually very similar to ``ChangeFilter`` except that it operates on source stamps.
It accepts a set of conditions.
A source stamp is considered *accepted* if all conditions are satisfied.
The conditions are specified via the constructor arguments.

The following parameters are supported by the :py:class:`SourceStampFilter`:

``project_eq``, ``codebase_eq``, ``repository_eq``, ``branch_eq``
    (optional, a string or a list of strings)
    The corresponding property of the source stamp must match exactly to at least one string from the value supplied by the argument.

    ``branch`` uses ``util.NotABranch`` as its default value which indicates that no checking should be done, because the branch may actually have ``None`` value to be checked.

``project_not_eq``, ``codebase_not_eq``, ``repository_not_eq``, ``branch_not_eq``
    (optional, a string or a list of strings)
    The corresponding property of the source stamp must not match exactly to any string from the value supplied by the argument.

``project_re``, ``codebase_re``, ``repository_re``, ``branch_re``
    (optional, a string or a list of strings or regex pattern objects)
    The corresponding property of the source stamp must match to at least one regex from the value supplied by the argument.
    Any strings passed via this parameter are converted to a regex via ``re.compile``.

``project_not_re``, ``codebase_not_re``, ``repository_not_re``, ``branch_not_re``
    (optional, a string or a list of strings or regex pattern objects)
    The corresponding property of the source stamp must not match to any regex from the value supplied by the argument.
    Any strings passed via this parameter are converted to a regex via ``re.compile``.

``filter_fn``
    (optional, a callable accepting a dictionary and returning a boolean)
    The given function will be passed the source stamp.
    It is expected to return ``True`` if the source stamp is matched, ``False`` otherwise.
    In case of a match, all other conditions will still be evaluated.

