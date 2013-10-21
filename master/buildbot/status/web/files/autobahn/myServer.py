import sys

import urllib2

import re

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
      self.clients_urls = {}
      self.tick()

   def tick(self):
      self.tickcount += 1
      self.broadcast()
      reactor.callLater(1, self.tick)

   def register(self, client):
      if not client in self.clients:
         print "registered client " + client.peerstr
         self.clients.append(client)

   def unregister(self, client):
      if client in self.clients:
         print "unregistered client " + client.peerstr
         self.clients.remove(client)
         if client.peerstr in self.clients_urls:
            del self.clients_urls[client.peerstr]

   def clientbroadcast(self, msg):
      print "message from client %s" % msg
      if isinstance(msg, str) and "http://" in msg:
         _re_client = re.compile(r"'(http://.*)' from (.*)")
         m = _re_client.search(msg)
         if m:
            url = m.group(1).strip()
            client = m.group(2).strip()
            print "url %s client %s" % (url,client)
            self.clients_urls[client] = url
            response = urllib2.urlopen(url)
            data = response.read();

   def serverbroadcast(self, msg):
      for c in self.clients:
         if c.peerstr in self.clients_urls:
            print "url %s peerstr %s" %(self.clients_urls[c.peerstr], c.peerstr)
            response = urllib2.urlopen(self.clients_urls[c.peerstr])
            data = response.read();        
            c.sendMessage(data)

   def broadcast(self, msg=None):
      print "msg %s" % msg
      print "clients_urls %s" % self.clients_urls
      if isinstance(msg, str) and "http://" in msg:
         self.clientbroadcast(msg)
      else:
         self.serverbroadcast(msg)

   '''
   def broadcast(self, msg=None):

      data = ""
      if isinstance(msg, str) and "http://" in msg:
         _re_url = re.compile(r"'(http://.*)'")
         url = ""
         m = _re_url.search(msg)
         if m:
            url = m.group(1)
            #if url not in urls:
            #   urls.append(url)
            response = urllib2.urlopen(url)
            data = response.read();

      else:
         for url in urls:
            response = urllib2.urlopen(url)
            data = response.read();
      
      #datastate = responsestate.read();
      print "broadcasting message '%s' .." % msg
      for c in self.clients:
         c.sendMessage(data)

         #print "message sent to " + c.peerstr
      '''

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