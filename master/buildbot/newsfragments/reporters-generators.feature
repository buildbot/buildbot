A new report generator API has been implemented to abstract generation of various reports that are then sent via the reporters.
The ``BitbucketServerPRCommentPush``, ``MailNotifier``, ``PushjetNotifier`` and ``PushoverNotifier`` support this new API via their new ``generators`` parameter.
