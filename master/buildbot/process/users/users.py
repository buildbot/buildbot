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

from __future__ import absolute_import
from __future__ import print_function

import os
from binascii import hexlify
from hashlib import sha1

from twisted.internet import defer
from twisted.python import log

from buildbot.util import bytes2NativeString
from buildbot.util import flatten
from buildbot.util import unicode2bytes

srcs = ['git', 'svn', 'hg', 'cvs', 'darcs', 'bzr']
salt_len = 8


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
        return defer.succeed(None)

    if src in srcs:
        usdict = dict(identifier=author, attr_type=src, attr_data=author)
    else:
        log.msg("Unrecognized source argument: %s" % src)
        return defer.succeed(None)

    return master.db.users.findUserByAttr(
        identifier=usdict['identifier'],
        attr_type=usdict['attr_type'],
        attr_data=usdict['attr_data'])


def _extractContact(usdict, contact_types, uid):
    if usdict:
        for type in contact_types:
            contact = usdict.get(type)
            if contact:
                break
    else:
        contact = None
    if contact is None:
        log.msg(format="Unable to find any of %(contact_types)r for uid: %(uid)r",
                contact_types=contact_types, uid=uid)
    return contact


def getUserContact(master, contact_types, uid):
    """
    This is a simple getter function that returns a user attribute
    that matches the contact_types argument, or returns None if no
    uid/match is found.

    @param master: BuildMaster used to query the database
    @type master: BuildMaster instance

    @param contact_types: list of contact attributes to look for in
                         in a given user, such as 'email' or 'nick'
    @type contact_types: list of strings

    @param uid: user that is searched for the contact_types match
    @type uid: integer

    @returns: string of contact information or None via deferred
    """
    d = master.db.users.getUser(uid)
    d.addCallback(_extractContact, contact_types, uid)
    return d


def _filter(contacts):
    def notNone(c):
        return c is not None
    return filter(notNone, contacts)


def getUsersContacts(master, contact_types, uids):
    d = defer.gatherResults(
        [getUserContact(master, contact_types, uid) for uid in uids])
    d.addCallback(_filter)
    return d


def getChangeContacts(master, change, contact_types):
    d = master.db.changes.getChangeUids(change.number)
    d.addCallback(lambda uids: getUsersContacts(master, contact_types, uids))
    return d


def getSourceStampContacts(master, ss, contact_types):
    dl = [getChangeContacts(master, change, contact_types)
          for change in ss.changes]
    if False and ss.patch_info:
        d = master.db.users.getUserByUsername(ss.patch_into[0])
        d.addCallback(_extractContact, contact_types, ss.patch_info[0])
        d.addCallback(lambda contact: filter(None, [contact]))
        dl.append(d)
    d = defer.gatherResults(dl)
    d.addCallback(flatten)
    return d


def getBuildContacts(master, build, contact_types):
    dl = []
    ss_list = build.getSourceStamps()
    for ss in ss_list:
        dl.append(getSourceStampContacts(master, ss, contact_types))
    d = defer.gatherResults(dl)
    d.addCallback(flatten)

    @d.addCallback
    def addOwners(recipients):
        dl = []
        for owner in build.getInterestedUsers():
            d = master.db.users.getUserByUsername(owner)
            d.addCallback(_extractContact, contact_types, owner)
            dl.append(d)
        d = defer.gatherResults(dl)
        d.addCallback(_filter)
        d.addCallback(lambda owners: recipients + owners)
        return d
    return d


def encrypt(passwd):
    """
    Encrypts the incoming password after adding some salt to store
    it in the database.

    @param passwd: password portion of user credentials
    @type passwd: string

    @returns: encrypted/salted string
    """
    m = sha1()
    salt = hexlify(os.urandom(salt_len))
    m.update(unicode2bytes(passwd) + salt)
    crypted = bytes2NativeString(salt) + m.hexdigest()
    return crypted


def check_passwd(guess, passwd):
    """
    Tests to see if the guess, after salting and hashing, matches the
    passwd from the database.

    @param guess: incoming password trying to be used for authentication
    @param passwd: already encrypted password from the database

    @returns: boolean
    """
    m = sha1()
    salt = passwd[:salt_len * 2]  # salt_len * 2 due to encode('hex_codec')
    m.update(unicode2bytes(guess) + unicode2bytes(salt))
    crypted_guess = bytes2NativeString(salt) + m.hexdigest()

    return (crypted_guess == bytes2NativeString(passwd))
