
from zope.interface import implements
from twisted.application import service

from buildbot.interfaces import IChangeSource
from buildbot import util

class ChangeSource(service.Service, util.ComparableMixin):
    implements(IChangeSource)

