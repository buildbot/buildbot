.. _ChangeFilter:

ChangeFilter
++++++++++++

.. py:class:: buildbot.util.ChangeFilter

This class is used to filter changes.
It is conceptually very similar to ``SourceStampFilter`` except that it operates on changes.
The class accepts a set of conditions.
A change is considered *acepted* if all conditions are satisfied.
The conditions are specified via the constructor arguments.

The following parameters are supported by the :py:class:`ChangeFilter`:


``project``, ``repository``, ``branch``, ``category``, ``codebase``
    (optional, a string or a list of strings)
    The corresponding attribute of the change must match exactly to at least one string from the value supplied by the argument.

    ``branch`` uses ``util.NotABranch`` as its default value which indicates that no checking should be done, because the branch may actually have ``None`` value to be checked.

``project_not_eq``, ``repository_not_eq``, ``branch_not_eq``, ``category_not_eq``, ``codebase_not_eq``
    (optional, a string or a list of strings)
    The corresponding attribute of the change must not match exactly to any of the strings from the value supplied by the argument.

    ``branch`` uses ``util.NotABranch`` as its default value which indicates that no checking should be done, because the branch may actually have ``None`` value to be checked.

``project_re``, ``repository_re``, ``branch_re``, ``category_re``, ``codebase_re``
    (optional, a string or a list of strings or regex pattern objects)
    The corresponding attribute of the change must match to at least one regex from the value supplied by the argument.
    Any strings passed via this parameter are converted to a regex via ``re.compile``.

``project_not_re``, ``repository_not_re``, ``branch_not_re``, ``category_not_re``, ``codebase_not_re``
    (optional, a string or a list of strings or regex pattern objects)
    The corresponding attribute of the change must not match to at least any regex from the value supplied by the argument.
    Any strings passed via this parameter are converted to a regex via ``re.compile``.

``property_eq``
    (optional, a dictionary containing string keys and values each of which with a string or a list of strings)
    The property of the change with corresponding name must match exactly to at least one string from the value supplied by the argument.

``property_not_eq``
    (optional, a string or a list of strings)
    The property of the change with corresponding name must not be present or not match exactly to at least one string from the value supplied by the argument.

``property_re``
    (optional, a string or a list of strings or regex pattern objects)
    The property of the change with corresponding name must match to at least one regex from the value supplied by the argument.
    Any strings passed via this parameter are converted to a regex via ``re.compile``.

``property_not_re``
    (optional, a string or a list of strings or regex pattern objects)
    The property of the change with corresponding name must not be present or not match to at least one regex from the value supplied by the argument.
    Any strings passed via this parameter are converted to a regex via ``re.compile``.

``project_fn``, ``repository_fn``, ``branch_fn``, ``category_fn``, ``codebase_fn``
    (optional, a callable accepting a string and returning a boolean)
    The given function will be passed the value from the change that corresponds to the parameter name.
    It is expected to return ``True`` if the change is matched, ``False`` otherwise.
    In case of a match, all other conditions will still be evaluated.

``filter_fn``
    (optional, a callable accepting a ``Change`` object and returning a boolean)
    The given function will be passed the change.
    It is expected to return ``True`` if the change is matched, ``False`` otherwise.
    In case of a match, all other conditions will still be evaluated.

Examples
~~~~~~~~

:class:`ChangeFilter` can be setup like this:

.. code-block:: python

    from buildbot.plugins import util
    my_filter = util.ChangeFilter(project_re="^baseproduct/.*", branch="devel")

and then assigned to a scheduler with the ``change_filter`` parameter:

.. code-block:: python

    sch = SomeSchedulerClass(..., change_filter=my_filter)


:class:`buildbot.www.hooks.github.GitHubEventHandler` has a special ``github_distinct`` property that can be used to specify whether or not non-distinct changes should be considered.
For example, if a commit is pushed to a branch that is not being watched and then later pushed to a watched branch, by default, this will be recorded as two separate changes.
In order to record a change only the first time the commit appears, you can use a custom :class:`ChangeFilter` like this:

.. code-block:: python

    ChangeFilter(filter_fn=lambda c: c.properties.getProperty('github_distinct'))

For anything more complicated, a Python function can be defined to recognize the wanted strings:

.. code-block:: python

    def my_branch_fn(branch):
        return branch in branches_to_build and branch not in branches_to_ignore
    my_filter = util.ChangeFilter(branch_fn=my_branch_fn)
