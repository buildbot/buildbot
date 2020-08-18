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


class RevlinkMatch:

    def __init__(self, repo_urls, revlink):
        if isinstance(repo_urls, str):
            repo_urls = [repo_urls]
        self.repo_urls = [re.compile(url) for url in repo_urls]
        self.revlink = revlink

    def __call__(self, rev, repo):
        for url in self.repo_urls:
            m = url.match(repo)
            if m:
                return m.expand(self.revlink) % rev
        return None


GithubRevlink = RevlinkMatch(
    repo_urls=[r'https://github.com/([^/]*)/([^/]*?)(?:\.git)?$',
               r'git://github.com/([^/]*)/([^/]*?)(?:\.git)?$',
               r'git@github.com:([^/]*)/([^/]*?)(?:\.git)?$',
               r'ssh://git@github.com/([^/]*)/([^/]*?)(?:\.git)?$'
               ],
    revlink=r'https://github.com/\1/\2/commit/%s')


BitbucketRevlink = RevlinkMatch(
        repo_urls=[r'https://[^@]*@bitbucket.org/([^/]*)/([^/]*?)(?:\.git)?$',
                   r'git@bitbucket.org:([^/]*)/([^/]*?)(?:\.git)?$'],
        revlink=r'https://bitbucket.org/\1/\2/commits/%s')


class GitwebMatch(RevlinkMatch):

    def __init__(self, repo_urls, revlink):
        super().__init__(repo_urls=repo_urls,
                         revlink=revlink + r'?p=\g<repo>;a=commit;h=%s')


SourceforgeGitRevlink = GitwebMatch(
    repo_urls=[r'^git://([^.]*).git.sourceforge.net/gitroot/(?P<repo>.*)$',
               r'[^@]*@([^.]*).git.sourceforge.net:gitroot/(?P<repo>.*)$',
               r'ssh://(?:[^@]*@)?([^.]*).git.sourceforge.net/gitroot/(?P<repo>.*)$',
               ],
    revlink=r'http://\1.git.sourceforge.net/git/gitweb.cgi')

# SourceForge recently upgraded to another platform called Allura
# See introduction:
# https://sourceforge.net/p/forge/documentation/Classic%20vs%20New%20SourceForge%20projects/
# And as reference:
# https://sourceforge.net/p/forge/community-docs/SVN%20and%20project%20upgrades/
SourceforgeGitRevlink_AlluraPlatform = RevlinkMatch(
    repo_urls=[r'git://git.code.sf.net/p/(?P<repo>.*)$',
               r'http://git.code.sf.net/p/(?P<repo>.*)$',
               r'ssh://(?:[^@]*@)?git.code.sf.net/p/(?P<repo>.*)$'
               ],
    revlink=r'https://sourceforge.net/p/\1/ci/%s/')


class RevlinkMultiplexer:

    def __init__(self, *revlinks):
        self.revlinks = revlinks

    def __call__(self, rev, repo):
        for revlink in self.revlinks:
            url = revlink(rev, repo)
            if url:
                return url
        return None


default_revlink_matcher = RevlinkMultiplexer(GithubRevlink,
                                             BitbucketRevlink,
                                             SourceforgeGitRevlink,
                                             SourceforgeGitRevlink_AlluraPlatform)
