Creating a release
==================

This document is documentation intended for Buildbot maintainers.
It documents the release process of Buildbot.

Step 1: Verify that external dependants can be built
----------------------------------------------------

Verify that the following resources can be built from the latest master.
This can be checked by looking into the dashboards (maintainer access may be needed).

 - Docker Hub (buildbot-master) (https://hub.docker.com/repository/docker/buildbot/buildbot-master/general)

 - Docker Hub (buildbot-worker) (https://hub.docker.com/repository/docker/buildbot/buildbot-worker/general)

 - Read the Docs (https://readthedocs.org/projects/buildbot/builds/)

These external dependencies build only by git tag.
Thus if a release is done with broken build process, it would be impossible to fix without releasing a new version.

Step 2: Release notes PR
------------------------

Open a new branch (e.g. `release`) and run the following:

    . .venv/bin/activate && make release_notes VERSION=x.y.z

This collects the release notes using the `towncrier` tool and then commits the result.
This step is done as a PR so that CI can check for spelling errors and similar issues.
Local checks are insufficient as spelling check in particular depends on what dictionaries are installed.

It's best to run `make docs-release` afterwards and check `master/docs/_build/html/relnotes/index.html` file for obvious rendering errors.
This will have much faster turnaround compared to if the error is noticed after the CI runs.
If any errors are found, just amend the commit created by `make release_notes`.

Certain file names are not properly supported by the `towncrier` tool and it ignores them.
Check `newsfragments` directory for any forgotten release notes

Step 3: Merge the release notes PR
----------------------------------

Step 4: Perform actual release
------------------------------

This step requires the Buildbot git repository to contain `buildbot` remote that points to https://github.com/buildbot/buildbot and can be pushed to.

Additionally, the Buildbot docs repository (https://github.com/buildbot/bbdocs) must be checked out at `../bbdocs` path.

Pull the merge commit created on the `master` branch during the step 2.
Then run:

    make release VERSION=x.y.z

This will create the required tags, make documentation, copy it to bbdocs repo and push everything.

Step 5: Draft a new release and wait for CircleCi to create release tarballs
----------------------------------------------------------------------------

The push of tags created during step 3 will activate CircleCi configuration that generates tarballs and uploads them to GitHub.
CircleCi will automatically publish a new release when uploading assets.
The release notes must be added manually by drafting a release on the GitHub UI at https://github.com/buildbot/buildbot/releases.

If you draft the release and publish it before CircleCi, make sure the release name matches the git tag.
This is a requirement for subsequent release scripts to work.
Manual publishing is preferred, because the releases created by CircleCi don't contain release notes, thus GitHub notifications are not informative.

Step 6: Upload release to pypi
------------------------------

This step requires GitHub Hub tool to be installed and authorized to GitHub (https://github.com/github/hub).
Additionally you have to have access to GPG key that is used to sign the releases.
Finally, you have to be added as a maintainer to all Buildbot PyPi projects.

To complete the release just run the following:

    make finishrelease

The above will download the releases from GitHub and upload them using twine.
If you get bytes-related error after entering Pypi password, you'll need to upgrade Twine.

Step 7: Announce the release
----------------------------

This step involves announcing the release of the new Buildbot version on several channels.
Write an email to the BuildBot mailing lists: announce@buildbot.net, devel@buildbot.net, users@buildbot.net.
Write a blog post on the Buildbot Medium account: https://medium.com/buildbot.
The blog post should include the highlights of the release in less monotonous style than the release notes.
Any extra important remarks can be added there.
Lastly, include the output of `git shortlog --no-merges -ns v<prev_version>...v<curr_version>` to recognize the contributors.
