Patches
=======

.. bb:rtype:: patch

    :attr integer patchid: the unique ID of this patch
    :attr binary body: patch body as a binary string
    :attr integer level: patch level - the number of directory names to strip from filenames in the patch
    :attr string subdir: subdirectory in which patch should be applied
    :attr string author: patch author, or None
    :attr string comment: patch comment, or None

    This resource type describes a patch.
    Patches have unique IDs, but only appear embedded in sourcestamps, so those IDs are not especially useful.


Update Methods
--------------

All update methods are available as attributes of ``master.data.updates``.

.. py:class:: buildbot.data.patches.PatchResourceType

    (no update methods)
