Implement GitHub change hook CI skipping (:issue:`3443`).
Now buildbot will ignore the event, if the ``[ci skip]`` keyword (configurable)
in commit message. For more info, please check out the ``skip`` parameter of
:bb:chsrc:`GitHub` hook.
