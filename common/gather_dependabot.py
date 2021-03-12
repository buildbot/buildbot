#!/usr/bin/env python3

# this script takes all the PR created by dependabot and gather them into one

import argparse
import os

import requests
import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--remote', type=str, default=None,
                        help='The name of the remote to use for pull request. ' +
                             'Uses hub default if not specified')
    args = parser.parse_args()

    with open(os.path.expanduser("~/.config/hub")) as f:
        conf = yaml.safe_load(f)
        token = conf['github.com'][0]['oauth_token']

    os.system("git fetch https://github.com/buildbot/buildbot master")
    os.system("git checkout FETCH_HEAD -B gather_dependabot")
    s = requests.Session()
    s.headers.update({'Authorization': 'token ' + token})
    r = s.get("https://api.github.com/repos/buildbot/buildbot/pulls")
    r.raise_for_status()
    prs = r.json()
    with open("/tmp/hub_pr_message", 'w') as f:
        f.write("gather dependabot PRs\n\n")
        for pr in prs:
            if 'dependabot' in pr['user']['login']:
                print(pr['number'], pr['title'])
                f.write(f"#{pr['number']}: {pr['title']}\n")
                os.system(
                    "git fetch https://github.com/buildbot/buildbot "
                    f"refs/pull/{pr['number']}/head")
                os.system("git cherry-pick FETCH_HEAD")

    if args.remote is not None:
        os.system(f'git push {args.remote} gather_dependabot')
    os.system("hub pull-request -b buildbot:master -p -F /tmp/hub_pr_message -l dependencies")


if __name__ == '__main__':
    main()
