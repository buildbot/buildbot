Allow the buildbot master initial start timeout to be configurable.

On big setups, with a lot of workers or a lot of builders, buildbot will take way more than 10 seconds to start.
The result is that buildbot stop's itself in the middle of the start process.

This change allows for the initial start timeout to be configurable so that these big setups can adjust.
