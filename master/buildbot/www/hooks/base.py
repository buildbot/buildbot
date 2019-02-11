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
#
# code inspired/copied from contrib/github_buildbot
#  and inspired from code from the Chromium project
# otherwise, Andrew Melo <andrew.melo@gmail.com> wrote the rest
# but "the rest" is pretty minimal


import json

from buildbot.util import bytes2unicode


class BaseHookHandler:
    def __init__(self, master, options):
        self.master = master
        self.options = options

    def getChanges(self, request):
        """
        Consumes a naive build notification (the default for now)
        basically, set POST variables to match commit object parameters:
        revision, revlink, comments, branch, who, files, links

        files, links and properties will be de-json'd, the rest are interpreted as strings
        """

        def firstOrNothing(value):
            """
            Small helper function to return the first value (if value is a list)
            or return the whole thing otherwise.

            Make sure to properly decode bytes to unicode strings.
            """
            if (isinstance(value, type([]))):
                value = value[0]
            return bytes2unicode(value)

        args = request.args
        # first, convert files, links and properties
        files = None
        if args.get(b'files'):
            files = json.loads(firstOrNothing(args.get(b'files')))
        else:
            files = []

        properties = None
        if args.get(b'properties'):
            properties = json.loads(firstOrNothing(args.get(b'properties')))
        else:
            properties = {}

        revision = firstOrNothing(args.get(b'revision'))
        when = firstOrNothing(args.get(b'when_timestamp'))
        if when is None:
            when = firstOrNothing(args.get(b'when'))
        if when is not None:
            when = float(when)
        author = firstOrNothing(args.get(b'author'))
        if not author:
            author = firstOrNothing(args.get(b'who'))
        comments = firstOrNothing(args.get(b'comments'))
        branch = firstOrNothing(args.get(b'branch'))
        category = firstOrNothing(args.get(b'category'))
        revlink = firstOrNothing(args.get(b'revlink'))
        repository = firstOrNothing(args.get(b'repository')) or ''
        project = firstOrNothing(args.get(b'project')) or ''
        codebase = firstOrNothing(args.get(b'codebase'))

        chdict = dict(author=author, files=files, comments=comments,
                      revision=revision, when_timestamp=when,
                      branch=branch, category=category, revlink=revlink,
                      properties=properties, repository=repository,
                      project=project, codebase=codebase)
        return ([chdict], None)


base = BaseHookHandler  # alternate name for buildbot plugin
