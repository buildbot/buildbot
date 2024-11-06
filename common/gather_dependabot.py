#!/usr/bin/env python3

# this script takes all the PR created by dependabot and gather them into one

import os

import requests
import yaml


def main():
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

    pr_text = "This PR collects dependabot PRs:\n\n"
    for pr in prs:
        if 'dependabot' in pr['user']['login']:
            print(pr['number'], pr['title'])
            pr_text += f"#{pr['number']}: {pr['title']}\n"
            os.system(
                f"git fetch https://github.com/buildbot/buildbot refs/pull/{pr['number']}/head"
            )
            os.system("git cherry-pick FETCH_HEAD")

    print("===========")
    print(pr_text)


if __name__ == '__main__':
    main()
