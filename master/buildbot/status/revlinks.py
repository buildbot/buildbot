# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import re

class RevlinkMatch(object):
    def __init__(self, repo_urls, revlink):
        self.repo_urls = map(re.compile, repo_urls)
        self.revlink = revlink
    def __call__(self, rev, repo):
        for url in self.repo_urls:
            m = url.match(repo)
            if m:
                return m.expand(self.revlink) % rev

GithubRevlink = RevlinkMatch(
        repo_urls = [ 'https://github.com/([^/]*)/([^/]*?)(?:\.git)?$',
            'git://github.com/([^/]*)/([^/]*?)(?:\.git)?$',
            'git@github.com:([^/]*)/([^/]*?)(?:\.git)?$',
            'ssh://git@github.com/([^/]*)/([^/]*?)(?:\.git)?$'
            ],
        revlink = 'https://github.com/\\1/\\2/commit/%s')

SourceforgeGitRevlink = RevlinkMatch(
        repo_urls = [ '^git://([^.]*).git.sourceforge.net/gitroot/(.*)$',
            '[^@]*@([^.]*).git.sourceforge.net:gitroot/(.*)$',
            'ssh://(?:[^@]*@)?([^.]*).git.sourceforge.net/gitroot/(.*)$',
            ],
        revlink = 'http://\\1.git.sourceforge.net/git/gitweb.cgi?p=\\2;a=commit;h=%s')

class RevlinkMultiplexer(object):
    def __init__(self, *revlinks):
        self.revlinks = revlinks
    def __call__(self, rev, repo):
        print repo
        for revlink in self.revlinks:
            url = revlink(rev, repo)
            if url:
                return url

default_revlink_matcher = RevlinkMultiplexer(GithubRevlink, SourceforgeGitRevlink)
