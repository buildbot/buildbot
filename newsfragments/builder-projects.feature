Introduce a way to group builders by project.
A new ``projects`` list is added to the configuration dictionary.
Builders can be associated to the entries in that list by the new ``project`` argument.

Grouping builders by project allows to significantly clean up the UI in larger Buildbot installations that contain hundreds or thousands of builders for a smaller number of unrelated codebases.
