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


from collections import deque
import os
import cPickle as pickle

from zope.interface import implements, Interface


def ReadFile(path):
    f = open(path, 'rb')
    try:
        return f.read()
    finally:
        f.close()


def WriteFile(path, buf):
    f = open(path, 'wb')
    try:
        f.write(buf)
    finally:
        f.close()


class IQueue(Interface):
    """Abstraction of a queue."""
    def pushItem(item):
        """Adds an individual item to the end of the queue.

        Returns an item if it was overflowed."""

    def insertBackChunk(items):
        """Adds a list of items as the oldest entries.

        Normally called in case of failure to process the data, queue the data
        back so it can be retrieved at a later time.

        Returns a list of items if it was overflowed."""

    def popChunk(nbItems=None):
        """Pop many items at once. Defaults to self.maxItems()."""

    def save():
        """Save the queue to storage if implemented."""

    def items():
        """Returns items in the queue.

        Warning: Can be extremely slow for queue on disk."""

    def nbItems():
        """Returns the number of items in the queue."""

    def maxItems():
        """Returns the maximum number of items this queue can hold."""


class MemoryQueue(object):
    """Simple length bounded queue using deque.

    list.pop(0) operation is O(n) so for a 10000 items list, it can start to
    be real slow. On the contrary, deque.popleft() is O(1) most of the time.
    See http://docs.python.org/library/collections.html for more
    information.
    """
    implements(IQueue)

    def __init__(self, maxItems=None):
        self._maxItems = maxItems
        if self._maxItems is None:
            self._maxItems = 10000
        self._items = deque()

    def pushItem(self, item):
        ret = None
        if len(self._items) == self._maxItems:
            ret = self._items.popleft()
        self._items.append(item)
        return ret

    def insertBackChunk(self, chunk):
        ret = None
        excess = len(self._items) + len(chunk) - self._maxItems
        if excess > 0:
            ret = chunk[0:excess]
            chunk = chunk[excess:]
        self._items.extendleft(reversed(chunk))
        return ret

    def popChunk(self, nbItems=None):
        if nbItems is None:
            nbItems = self._maxItems
        if nbItems > len(self._items):
            items = list(self._items)
            self._items = deque()
        else:
            items = []
            for i in range(nbItems):
                items.append(self._items.popleft())
        return items

    def save(self):
        pass

    def items(self):
        return list(self._items)

    def nbItems(self):
        return len(self._items)

    def maxItems(self):
        return self._maxItems


class DiskQueue(object):
    """Keeps a list of abstract items and serializes it to the disk.

    Use pickle for serialization."""
    implements(IQueue)

    def __init__(self, path, maxItems=None, pickleFn=pickle.dumps,
                 unpickleFn=pickle.loads):
        """
        @path: directory to save the items.
        @maxItems: maximum number of items to keep on disk, flush the
        older ones.
        @pickleFn: function used to pack the items to disk.
        @unpickleFn: function used to unpack items from disk.
        """
        self.path = path
        self._maxItems = maxItems
        if self._maxItems is None:
            self._maxItems = 100000
        if not os.path.isdir(self.path):
            os.mkdir(self.path)
        self.pickleFn = pickleFn
        self.unpickleFn = unpickleFn

        # Total number of items.
        self._nbItems = 0
        # The actual items id start at one.
        self.firstItemId = 0
        self.lastItemId = 0
        self._loadFromDisk()

    def pushItem(self, item):
        ret = None
        if self._nbItems == self._maxItems:
            id = self._findNext(self.firstItemId)
            path = os.path.join(self.path, str(id))
            ret = self.unpickleFn(ReadFile(path))
            os.remove(path)
            self.firstItemId = id + 1
        else:
            self._nbItems += 1
        self.lastItemId += 1
        path = os.path.join(self.path, str(self.lastItemId))
        if os.path.exists(path):
            raise IOError('%s already exists.' % path)
        WriteFile(path, self.pickleFn(item))
        return ret

    def insertBackChunk(self, chunk):
        ret = None
        excess = self._nbItems + len(chunk) - self._maxItems
        if excess > 0:
            ret = chunk[0:excess]
            chunk = chunk[excess:]
        for i in reversed(chunk):
            self.firstItemId -= 1
            path = os.path.join(self.path, str(self.firstItemId))
            if os.path.exists(path):
                raise IOError('%s already exists.' % path)
            WriteFile(path, self.pickleFn(i))
            self._nbItems += 1
        return ret

    def popChunk(self, nbItems=None):
        if nbItems is None:
            nbItems = self._maxItems
        ret = []
        for i in range(nbItems):
            if self._nbItems == 0:
                break
            id = self._findNext(self.firstItemId)
            path = os.path.join(self.path, str(id))
            ret.append(self.unpickleFn(ReadFile(path)))
            os.remove(path)
            self._nbItems -= 1
            self.firstItemId = id + 1
        return ret

    def save(self):
        pass

    def items(self):
        """Warning, very slow."""
        ret = []
        for id in range(self.firstItemId, self.lastItemId + 1):
            path = os.path.join(self.path, str(id))
            if os.path.exists(path):
                ret.append(self.unpickleFn(ReadFile(path)))
        return ret

    def nbItems(self):
        return self._nbItems

    def maxItems(self):
        return self._maxItems

    #### Protected functions

    def _findNext(self, id):
        while True:
            path = os.path.join(self.path, str(id))
            if os.path.isfile(path):
                return id
            id += 1
        return None

    def _loadFromDisk(self):
        """Loads the queue from disk upto self.maxMemoryItems items into
        self.items.
        """
        def SafeInt(item):
            try:
                return int(item)
            except ValueError:
                return None

        files = filter(None, [SafeInt(x) for x in os.listdir(self.path)])
        files.sort()
        self._nbItems = len(files)
        if self._nbItems:
            self.firstItemId = files[0]
            self.lastItemId = files[-1]


class PersistentQueue(object):
    """Keeps a list of abstract items and serializes it to the disk.

    It has 2 layers of queue, normally an in-memory queue and an on-disk queue.
    When the number of items in the primary queue gets too large, the new items
    are automatically saved to the secondary queue. The older items are kept in
    the primary queue.
    """
    implements(IQueue)

    def __init__(self, primaryQueue=None, secondaryQueue=None, path=None):
        """
        @primaryQueue: memory queue to use before buffering to disk.
        @secondaryQueue: disk queue to use as permanent buffer.
        @path: path is a shortcut when using default DiskQueue settings.
        """
        self.primaryQueue = primaryQueue
        if self.primaryQueue is None:
            self.primaryQueue = MemoryQueue()
        self.secondaryQueue = secondaryQueue
        if self.secondaryQueue is None:
            self.secondaryQueue = DiskQueue(path)
        # Preload data from the secondary queue only if we know we won't start
        # using the secondary queue right away.
        if self.secondaryQueue.nbItems() < self.primaryQueue.maxItems():
            self.primaryQueue.insertBackChunk(
                self.secondaryQueue.popChunk(self.primaryQueue.maxItems()))

    def pushItem(self, item):
        # If there is already items in secondaryQueue, we'd need to pop them
        # all to start inserting them into primaryQueue so don't bother and
        # just push it in secondaryQueue.
        if (self.secondaryQueue.nbItems() or
            self.primaryQueue.nbItems() == self.primaryQueue.maxItems()):
            item = self.secondaryQueue.pushItem(item)
            if item is None:
                return item
            # If item is not None, secondaryQueue overflowed. We need to push it
            # back to primaryQueue so the oldest item is dumped.
        # Or everything fit in the primaryQueue.
        return self.primaryQueue.pushItem(item)

    def insertBackChunk(self, chunk):
        ret = None
        # Overall excess
        excess = self.nbItems() + len(chunk) - self.maxItems()
        if excess > 0:
            ret = chunk[0:excess]
            chunk = chunk[excess:]
        # Memory excess
        excess = (self.primaryQueue.nbItems() + len(chunk) -
                  self.primaryQueue.maxItems())
        if excess > 0:
            chunk2 = []
            for i in range(excess):
                chunk2.append(self.primaryQueue.items().pop())
            chunk2.reverse()
        x = self.primaryQueue.insertBackChunk(chunk)
        assert x is None, "primaryQueue.insertBackChunk did not return None"
        if excess > 0:
            x = self.secondaryQueue.insertBackChunk(chunk2)
            assert x is None, ("secondaryQueue.insertBackChunk did not return "
                               " None")
        return ret

    def popChunk(self, nbItems=None):
        if nbItems is None:
            nbItems = self.primaryQueue.maxItems()
        ret = self.primaryQueue.popChunk(nbItems)
        nbItems -= len(ret)
        if nbItems and self.secondaryQueue.nbItems():
            ret.extend(self.secondaryQueue.popChunk(nbItems))
        return ret

    def save(self):
        self.secondaryQueue.insertBackChunk(self.primaryQueue.popChunk())

    def items(self):
        return self.primaryQueue.items() + self.secondaryQueue.items()

    def nbItems(self):
        return self.primaryQueue.nbItems() + self.secondaryQueue.nbItems()

    def maxItems(self):
        return self.primaryQueue.maxItems() + self.secondaryQueue.maxItems()


class IndexedQueue(object):
    """Adds functionality to a IQueue object to track its usage.

    Adds a new member function getIndex() and modify popChunk() and
    insertBackChunk() to keep a virtual pointer to the queue's first entry
    index."""
    implements(IQueue)

    def __init__(self, queue):
        # Copy all the member functions from the other object that this class
        # doesn't already define.
        assert IQueue.providedBy(queue)
        def Filter(m):
            return (m[0] != '_' and callable(getattr(queue, m))
                    and not hasattr(self, m))
        for member in filter(Filter, dir(queue)):
            setattr(self, member, getattr(queue, member))
        self.queue = queue
        self._index = 0

    def getIndex(self):
        return self._index

    def popChunk(self, *args, **kwargs):
        items = self.queue.popChunk(*args, **kwargs)
        if items:
            self._index += len(items)
        return items

    def insertBackChunk(self, items):
        self._index -= len(items)
        ret = self.queue.insertBackChunk(items)
        if ret:
            self._index += len(ret)
        return ret


def ToIndexedQueue(queue):
    """If the IQueue wasn't already a IndexedQueue, makes it an IndexedQueue."""
    if not IQueue.providedBy(queue):
        raise TypeError("queue doesn't implement IQueue", queue)
    if isinstance(queue, IndexedQueue):
        return queue
    return IndexedQueue(queue)

# vim: set ts=4 sts=4 sw=4 et:
