Implement github change hook ci skipping (:issue:`3443`).

New parameter for github change hook: ``skips``
(default ``[r'\[ *skip *ci *\]', r'\[ *ci *skip *\]']``).

It's a list of regex pattern makes buildbot ignore the push event.
For instance, if user push 3 commits and the commit message of branch head
contains a key string ``[ci skip]``, buildbot will ignore this push event.
If you want to disable the skip checking, please set it to ``[]``.
