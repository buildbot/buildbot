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

# garbage-collection rules: the following rows can be GCed:
#  a patch that isn't referenced by any sourcestamps
#  a sourcestamp that isn't referenced by any buildsets
#  a buildrequest that isn't referenced by any buildsets
#  a buildset which is complete and isn't referenced by anything in
#   scheduler_upstream_buildsets
#  a scheduler_upstream_buildsets row that is not active
#  a build that references a non-existent buildrequest

