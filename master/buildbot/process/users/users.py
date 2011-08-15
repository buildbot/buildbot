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

from twisted.python import log
from twisted.internet import defer

srcs = ['git', 'svn', 'hg', 'cvs', 'darcs', 'bzr']

@defer.deferredGenerator
def createUserObject(master, author, src=None):
    """
    Take a Change author and source and translate them into a User Object,
    storing the user in master.db, or returning None if the src is not
    specified.

    @param master: link to Buildmaster for database operations
    @type master: master.Buildmaster instance

    @param authors: Change author if string or Authz instance
    @type authors: string or status.web.authz instance

    @param src: source from which the User Object will be created
    @type src: string
    """

    if not src:
        log.msg("No vcs information found, unable to create User Object")
        return

    if src in srcs:
        log.msg("checking for User Object from %s Change for: %s" % (src,
                                                                     author))
        usdict = dict(identifier=author, attr_type=src, attr_data=author)
    else:
        log.msg("Unrecognized source argument: %s" % src)
        return

    d = master.db.users.addUser(identifier=usdict['identifier'],
                                attr_type=usdict['attr_type'],
                                attr_data=usdict['attr_data'])
    wfd = defer.waitForDeferred(d)
    yield wfd
    uid = wfd.getResult()

    yield uid

def getUserContact(master, contact_type=None, uid=None):
    """
    This is a simple getter function that returns a user attribute
    that matches the contact_type argument, or returns None if no
    uid/match is found.

    @param master: BuildMaster used to query the database
    @type master: BuildMaster instance

    @param contact_type: type of contact attribute to look for in
                         in a given user, such as 'email' or 'nick'
    @type contact_type: string

    @param uid: user that is searched for the contact_type match
    @type uid: integer

    @returns: string of contact information or None via deferred
    """
    d = master.db.users.getUser(uid)
    d.addCallback(lambda usdict: usdict and usdict.get(contact_type))
    return d
