import sys

import urllib2

from twisted.web.client import Agent, getPage

from twisted.internet import reactor
from twisted.python import log
from twisted.web.server import Site
from twisted.web.static import File

from autobahn.websocket import WebSocketServerFactory, \
                               WebSocketServerProtocol, \
                               listenWS

agent = Agent(reactor)
class BroadcastServerProtocol(WebSocketServerProtocol):

   def onOpen(self):
      self.factory.register(self)

   def onMessage(self, msg, binary):
      if not binary:
         self.factory.broadcast("'%s' from %s" % (msg, self.peerstr))

   def connectionLost(self, reason):
      WebSocketServerProtocol.connectionLost(self, reason)
      self.factory.unregister(self)


class BroadcastServerFactory(WebSocketServerFactory):
   """
Simple broadcast server broadcasting any message it receives to all
currently connected clients.
"""

   def __init__(self, url, debug = False, debugCodePaths = False):
      WebSocketServerFactory.__init__(self, url, debug = debug, debugCodePaths = debugCodePaths)
      self.clients = []
      self.tickcount = 0
      self.tick()

   def tick(self):
      self.tickcount += 1
      self.broadcast(self.tickcount)
      reactor.callLater(1, self.tick)

   def register(self, client):
      if not client in self.clients:
         print "registered client " + client.peerstr
         self.clients.append(client)

   def unregister(self, client):
      if client in self.clients:
         print "unregistered client " + client.peerstr
         self.clients.remove(client)

   def broadcast(self, msg):
      response = urllib2.urlopen('http://localhost:8001/json?as_text=1')
      if msg:
         print msg
         responsestate = urllib2.urlopen('http://localhost:8001/json?as_text=1')
      else:
         responsestate = urllib2.urlopen(msg) 
         
         
         

      data = response.read();
      datares = responsestate.read();
      #datastate = responsestate.read();
      print "broadcasting message '%s' .." % msg
      for c in self.clients:
         c.sendMessage(data)
      for c in self.clients:
         c.sendMessage(datares)

         #print "message sent to " + c.peerstr


class BroadcastPreparedServerFactory(BroadcastServerFactory):
   """
Functionally same as above, but optimized broadcast using
prepareMessage and sendPreparedMessage.
"""

   def broadcast(self, msg):
      print "broadcasting prepared message '%s' .." % msg
      preparedMsg = self.prepareMessage(msg)
      for c in self.clients:
         c.sendPreparedMessage(preparedMsg)
         print "prepared message sent to " + c.peerstr


if __name__ == '__main__':

   if len(sys.argv) > 1 and sys.argv[1] == 'debug':
      log.startLogging(sys.stdout)
      debug = True
   else:
      debug = False

   ServerFactory = BroadcastServerFactory
   #ServerFactory = BroadcastPreparedServerFactory

   factory = ServerFactory("ws://localhost:9000",
                           debug = debug,
                           debugCodePaths = debug)

   factory.protocol = BroadcastServerProtocol
   factory.setProtocolOptions(allowHixie76 = True)
   listenWS(factory)

   webdir = File(".")
   web = Site(webdir)
   reactor.listenTCP(8080, web)

   reactor.run()