# Buildbot repository instructions for Copilot

- Base code changes on `buildbot/buildbot@master`, but do not submit new Copilot-created branches or pull requests directly to `buildbot/buildbot`.
- Publish them to a fork unless explicitly told otherwise, and keep each branch focused on one distinct change.
- Keep commits single-purpose when possible.
- For non-trivial patches, include relevant tests and user-facing documentation in the same branch.
- Preserve backward and forward compatibility where possible.
- Minimize behavior changes that would surprise existing users.
- Follow repository style expectations: four-space indentation, no tabs, and wrap Python lines before column 100.
- Feature and behavior changes must include a Towncrier newsfragment in
  `newsfragments/` using one of these suffixes:
  `.feature`, `.change`, `.bugfix`, `.doc`, `.removal`, `.misc`.
- Add the newsfragment in the same branch as the code change, and prefer including it in the same commit when practical.
- Do not edit `master/docs/relnotes/index.rst` by hand for normal feature work.
- Add a newsfragment instead.
- The filename stem can be an issue number or any unique work-specific text.
- In newsfragments, prefer Buildbot's documented formatting conventions such as `(:issue:\`NNN\`)` for GitHub issues and backticks for class names.
- Format newsfragments as one sentence per line.
- When validating locally, prefer the repository-supported workflow from the contributor docs:
  `pip install -r requirements-ci.txt` for Python checks,
  `pip install -r requirements-ciworker.txt` for worker tests,
  `pip install -r requirements-cidocs.txt` for docs,
  and `make docs` for documentation builds.
- Prefer `common/validate.sh` when its coverage matches the change.
- Run it from an activated virtualenv with the current Buildbot installed.
- If docs under `master/docs/` change, run the docs build.
- If it fails because of an existing repository issue, report the blocker clearly instead of claiming the docs were verified.
- Treat `.rst` files under `master/docs/` as Sphinx documentation: keep the wording, markup, and examples consistent with surrounding docs, and validate Sphinx changes with the docs build rather than by inspection alone.
- The pull request checklist expects updated unit tests, appropriate documentation updates, and a newsfragment when applicable.
- Preserve existing user changes in the worktree.
- Do not revert unrelated modifications.
