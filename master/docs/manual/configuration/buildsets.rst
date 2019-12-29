.. _BuildSet:

Build Sets
==========

A :class:`BuildSet` represents a set of :class:`Build`\s that all compile and/or test the same version of the source tree.
Usually, these builds are created by multiple :class:`Builder`\s and will thus execute different steps.

The :class:`BuildSet` is tracked as a single unit, which fails if any of the component :class:`Build`\s have failed, and therefore can succeed only if *all* of the component :class:`Build`\s have succeeded.
There are two kinds of status notification messages that can be emitted for a :class:`BuildSet`: the ``firstFailure`` type (which fires as soon as we know the :class:`BuildSet` will fail), and the ``Finished`` type (which fires once the :class:`BuildSet` has completely finished, regardless of whether the overall set passed or failed).

A :class:`BuildSet` is created with set of one or more *source stamp* tuples of ``(branch, revision, changes, patch)``, some of which may be ``None``, and a list of :class:`Builder`\s on which it is to be run.
They are then given to the BuildMaster, which is responsible for creating a separate :class:`BuildRequest` for each :class:`Builder`.

There are a couple of different likely values for the ``SourceStamp``:

:samp:`(revision=None, changes={CHANGES}, patch=None)`
    This is a :class:`SourceStamp` used when a series of :class:`Change`\s have triggered a build.
    The VC step will attempt to check out a tree that contains *CHANGES* (and any changes that occurred before *CHANGES*, but not any that occurred after them.)

:samp:`(revision=None, changes=None, patch=None)`
    This builds the most recent code on the default branch.
    This is the sort of :class:`SourceStamp` that would be used on a :class:`Build` that was triggered by a user request, or a :bb:sched:`Periodic` scheduler.
    It is also possible to configure the VC Source Step to always check out the latest sources rather than paying attention to the :class:`Change`\s in the :class:`SourceStamp`, which will result in same behavior as this.

:samp:`(branch={BRANCH}, revision=None, changes=None, patch=None)`
    This builds the most recent code on the given *BRANCH*.
    Again, this is generally triggered by a user request or a :bb:sched:`Periodic` scheduler.

:samp:`(revision={REV}, changes=None, patch=({LEVEL}, {DIFF}, {SUBDIR_ROOT}))`
    This checks out the tree at the given revision *REV*, then applies a patch (using ``patch -pLEVEL <DIFF``) from inside the relative directory *SUBDIR_ROOT*.
    Item *SUBDIR_ROOT* is optional and defaults to the builder working directory.
    The :bb:cmdline:`try` command creates this kind of :class:`SourceStamp`.
    If ``patch`` is ``None``, the patching step is bypassed.

The buildmaster is responsible for turning the :class:`BuildSet` into a set of :class:`BuildRequest` objects and queueing them on the appropriate :class:`Builder`\s.
