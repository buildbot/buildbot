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

from buildbot.test.util import verifier

def verifyDbDict(testcase, type, value):
    return verifier.verifyDict(testcase, value, 'bsdict', dict(
        bsid='integer',
        external_idstring='string:none',
        reason='string',
        sourcestampsetid='integer',
        submitted_at='datetime',
        complete='boolean',
        complete_at='datetime:none',
        results='integer:none',
        ))

def verifyData(testcase, type, options, value):
    testcase.assertEqual(options, {})
    return verifier.verifyDict(testcase, value, 'buildset', dict(
        bsid='integer',
        external_idstring='string:none',
        reason='string',
        sourcestampsetid='integer',
        submitted_at='integer',
        complete='boolean',
        complete_at='integer:none',
        results='integer:none',
        link='Link',
        ))

def verifyMessage(testcase, routingKey, message):
    attrs=dict(
        bsid='integer',
        external_idstring='string:none',
        reason='string',
        sourcestampsetid='integer',
        submitted_at='integer',
        complete='boolean',
        complete_at='integer:none',
        results='integer:none')

    # only new buildsets specifify the scheduler
    if routingKey[-1] == 'new':
        attrs['scheduler'] = 'string'

    return verifier.verifyMessage(testcase, routingKey, message,
            'buildset',
            keyFields=[ 'bsid' ],
            events=set([ 'new', 'complete' ]),
            attrs=attrs)
