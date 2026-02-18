Migrating from `BuildStatusGenerator` to `Gerrit*Generator` with Callbacks
==========================================================================

This section shows how to migrate from the older `BuildStatusGenerator` setup to the newer
`Gerrit*Generator` classes that support callback functions in Buildbot.

Old configuration using `BuildStatusGenerator`:

```python
from buildbot.plugins import reporters

reporter = reporters.GerritStatusPush(
    gerrit_url="https://gerrit.example.com",
    project="my/project",
    builderName="my-builder",
    statusGenerators=[
        reporters.BuildStatusGenerator(),
        reporters.BuildStartEndStatusGenerator(),
        reporters.BuildSetStatusGenerator(),
    ],
)
c['services'].append(reporter)


from buildbot.plugins import reporters

def my_status_callback(event):
    if event['type'] == 'buildStarted':
        return f"👷 Build {event['builderName']} started for change {event['change']['id']}."
    elif event['type'] == 'buildFinished':
        status = event['buildStatus']
        return f"🏁 Build finished with status: {status}"
    return None

reporter = reporters.GerritStatusPush(
    gerrit_url="https://gerrit.example.com",
    project="my/project",
    builderName="my-builder",
    statusGenerators=[
        reporters.GerritBuildStartStatusGenerator(callback=my_status_callback),
        reporters.GerritBuildEndStatusGenerator(callback=my_status_callback),
        reporters.GerritBuildSetStatusGenerator(callback=my_status_callback),
    ],
)
c['services'].append(reporter)
