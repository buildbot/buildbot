Avatars
=======

Buildbot's avatar support associates a small image with each user.

.. py:module:: buildbot.www.avatar

.. py:class:: AvatarBase

    This class can be used to get the avatars for the users.
    It can be used for authenticated users, but also for the users referenced in changes.

    .. py:method:: getUserAvatar(self, email, size, defaultAvatarUrl)

        :returns: the user's avatar, from the user's email (via Deferred).

        If the data is directly available, this function returns a tuple ``(mime_type, picture_raw_data)``.
        If the data is available in another URL, this function can raise ``resource.Redirect(avatar_url)``, and the web server will redirect to the avatar_url.
