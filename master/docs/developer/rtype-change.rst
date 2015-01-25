Changes
=======

.. bb:rtype:: change

    :attr integer changeid: the ID of this change
    :attr integer parent_changeid: the ID of the parent
    :attr string author: the author of the change in "name", "name <email>" or just "email" (with @) format
    :attr files: source-code filenames changed
    :type files: list of strings
    :attr string comments: user comments
    :attr string revision: revision for this change, or none if unknown
    :attr timestamp when_timestamp: time of the change
    :attr string branch: branch on which the change took place, or none for the "default branch", whatever that might mean
    :attr string category: user-defined category of this change, or none
    :attr string revlink: link to a web view of this change, or none
    :attr object properties: user-specified properties for this change, represented as an object mapping keys to tuple (value, source)
    :attr string repository: repository where this change occurred
    :attr string project: user-defined project to which this change corresponds
    :attr string codebase: codebase in this repository
    :attr sourcestamp sourcestamp: the sourcestamp resouce for this change

    ..:
        TODO: uid

    A change resource represents a change to the source code monitored by Buildbot.

    .. bb:event:: change.$changeid.new

        This message indicates the addition of a new change.

    .. bb:rpath:: /changes

        This path lists changes.

        Consuming from this path selects :bb:event:`change.$changeid.new` events.

    .. bb:rpath:: /builds/:buildid/changes

        :pathkey integer buildid: the ID of the build

        This path lists all changes related to a build

    .. bb:rpath:: /sourcestamps/:ssid/changes

        :pathkey integer ssid: the ID of the sourcestamp

        This path lists all changes related to a sourcestamp


    .. bb:rpath:: /changes/:changeid

        :pathkey integer changeid: the ID of the change

        This path selects a specific change, identified by ID.

Update Methods
--------------

All update methods are available as attributes of ``master.data.updates``.

.. py:class:: buildbot.data.changes.ChangeResourceType

    .. py:method:: addChange(files=None, comments=None, author=None, revision=None, when_timestamp=None, branch=None, category=None, revlink='', properties={}, repository='', codebase=None, project='', src=None)

        :param files: a list of filenames that were changed
        :type files: list of unicode strings
        :param unicode comments: user comments on the change
        :param unicode author: the author of this change
        :param unicode revision: the revision identifier for this change
        :param integer when_timestamp: when this change occurred (seconds since the epoch), or the current time if None
        :param unicode branch: the branch on which this change took place
        :param unicode category: category for this change
        :param string revlink: link to a web view of this revision
        :param properties: properties to set on this change.  Note that the property source is *not* included in this dictionary.
        :type properties: dictionary with unicode keys and simple values (JSON-able).
        :param unicode repository: the repository in which this change took place
        :param unicode project: the project this change is a part of
        :param unicode src: source of the change (vcs or other)
        :returns: the ID of the new change, via Deferred

        Add a new change to Buildbot.
        This method is the interface between change sources and the rest of Buildbot.

        All parameters should be passed as keyword arguments.

        All parameters labeled 'unicode' must be unicode strings and not bytestrings.
        Filenames in ``files``, and property names, must also be unicode strings.
        This is tested by the fake implementation.
