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
# Copyright 2013 (c) Mamba Developers

"""Simple PNG build status banner
"""

import os

from twisted.web import resource

from buildbot.status import results


class PngStatusResource(resource.Resource):

    """Describe a single builder result as a PNG image
    """

    isLeaf = True
    status = None
    content_type = 'image/png'

    def __init__(self, status):
        self.status = status

    def getChild(self, name, request):
        """Just return itself
        """
        return self

    def render(self, request):
        """
        Renders a given build status as PNG file

        We don't care about pre or post paths here so we skip them, we only
        care about parameters passed in the URL, those are:

        :param builder: the builder name
        :param size: the size of the PNG than can be 'small', 'normal', 'large'
        :returns: a binary PNG
        """

        data = self.content(request)
        request.setHeader('content-type', self.content_type)
        request.setHeader('cache-control', 'no-cache')
        request.setHeader(
            'content-disposition', 'inline; filename="%s"' % (data['filename'])
        )
        return data['image']

    def content(self, request):
        """Renders the PNG data
        """
        # png size
        size = request.args.get('size', ['normal'])[0]
        if size not in ('small', 'normal', 'large'):
            size = 'normal'

        # build number
        b = int(request.args.get('number', [-1])[0])

        # revision hash
        rev = request.args.get("revision", [None])[0]

        # default data
        png_file = (
            os.path.dirname(os.path.abspath(__file__)) +
            '/files/unknown_' + size + '.png'
        )
        data = {'filename': 'unkwnown_' + size + '.png', 'image': None}
        builder = request.args.get('builder', [None])[0]

        if builder is not None and builder in self.status.getBuilderNames():
            # get the last build result from this builder
            build = self.status.getBuilder(builder).getBuild(b, rev)
            if build is not None:
                result = build.getResults()
                if result is not None:
                    data['filename'] = (
                        results.Results[result] + '_' + size + '.png')

                    # read the png file from the disc
                    png_file = (os.path.dirname(os.path.abspath(__file__)) +
                                '/files/' + data['filename'])

        # load the png file from the file system
        png = open(png_file, 'rb')
        data['image'] = png.read()
        png.close()

        return data
