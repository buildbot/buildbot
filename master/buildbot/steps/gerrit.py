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

from buildbot.steps.master import CancelRelatedBuilds
from buildbot.steps.master import StopRelatedBuilds

_EVENT_TYPE = 'event.type'
_CHANGE_NO_PROP = 'event.change.number'
_PATCHSET_NO_PROP = 'event.patchSet.number'


def _get_change_spec(properties):
    if _EVENT_TYPE not in properties:
        return None

    change_no = properties.getProperty(_CHANGE_NO_PROP)
    patchset_no = properties.getProperty(_PATCHSET_NO_PROP)

    if change_no is not None and patchset_no is not None:
        return change_no, patchset_no
    else:
        return None


def pre_process(source_stamps):
    result = dict()

    for source_stamp in source_stamps:
        for change in source_stamp.changes:
            change_spec = _get_change_spec(change.properties)

            if change_spec is not None:
                result[change.codebase] = change_spec

    if not result:
        return None

    return result


def is_relevant(ours, theirs):
    if ours is None:
        return False

    result = dict()

    for source_stamp in theirs:
        for change in source_stamp.changes:
            our_change_spec = ours.get(change.codebase)
            if our_change_spec is None:
                continue

            change_spec = _get_change_spec(change.properties)

            if change_spec is not None:
                result[change.codebase] = (
                    our_change_spec[0] == change_spec[0] and
                    our_change_spec[1] > change_spec[1])

    return all([result.get(key, False) for key in ours.keys()])


class CancelGerritRelatedBuilds(CancelRelatedBuilds):
    def __init__(self, **kwargs):
        CancelRelatedBuilds.__init__(self, preProcess=pre_process,
                                     isRelevant=is_relevant, **kwargs)


class StopGerritRelatedBuilds(StopRelatedBuilds):
    def __init__(self, **kwargs):
        StopRelatedBuilds.__init__(self, preProcess=pre_process,
                                   isRelevant=is_relevant,
                                   reason='A new patch set for the same change'
                                          'is submitted', **kwargs)
