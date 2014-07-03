import json
import logging
import sys
from threading import Lock, Thread
import urllib2
import time
from autobahn.twisted.websocket import WebSocketServerProtocol, WebSocketServerFactory, listenWS
from twisted.web.client import Agent
from twisted.internet import reactor
from twisted.python import log
from twisted.web.server import Site
from twisted.web.static import File


PORT = 8010
POLL_INTERVAL = 5
MAX_POLL_INTERVAL = 30
POLL_INTERVAL_STEP = 5
MAX_ERRORS = 5
updateLock = Lock()

#Server Messages
KRT_JSON_DATA = "krtJSONData"
KRT_URL_DROPPED = "krtURLDropped"
KRT_REGISTER_URL = "krtRegisterURL"
KRT_PUSH_DATA = "krtPushData"

agent = Agent(reactor)


def dict_compare(d1, d2):
    d1_keys = set(d1.keys())
    d2_keys = set(d2.keys())
    intersect_keys = d1_keys.intersection(d2_keys)
    added = d1_keys - d2_keys
    removed = d2_keys - d1_keys
    modified = {o : (d1[o], d2[o]) for o in intersect_keys if d1[o] != d2[o]}
    same = set(o for o in intersect_keys if d1[o] == d2[o])
    return added, removed, modified, same


class CachedURL():
    """
    Caches the data found on a URL for future references
    """
    def __init__(self, url):
        self.url = url
        self.cachedJSON = None
        self.clients = []
        self.lastChecked = 0
        self.errorCount = 0
        self.pollInterval = POLL_INTERVAL
        self.currentPollInterval = POLL_INTERVAL
        self.locked = False
        self.waitForPush = False
        self.pushFilters = {}
        self.newData = False

    def pollNeeded(self):
        past_interval = (time.time() - self.lastChecked) > self.currentPollInterval
        if self.waitForPush:
            if self.newData:
                return past_interval
            return False

        return past_interval

    def pollSuccess(self):
        self.lastChecked = time.time()
        self.locked = False
        self.errorCount = 0
        self.newData = False

        if self.currentPollInterval > self.pollInterval:
            self.currentPollInterval -= POLL_INTERVAL_STEP

        if self.currentPollInterval < self.pollInterval:
            self.currentPollInterval = self.pollInterval

    def pollFailure(self):
        self.locked = False
        self.lastChecked = time.time()
        self.errorCount += 1

        self.currentPollInterval += POLL_INTERVAL_STEP

        if self.currentPollInterval > MAX_POLL_INTERVAL:
            self.currentPollInterval = MAX_POLL_INTERVAL

class BroadcastServerProtocol(WebSocketServerProtocol):
    def __init__(self):
        self.peerstr = ""

    def onOpen(self):
        self.factory.register(self)

    def onMessage(self, msg, binary):
        if not binary:
            self.factory.clientMessage(msg, self)

    def connectionLost(self, reason):
        WebSocketServerProtocol.connectionLost(self, reason)
        self.factory.unregister(self)


class BroadcastServerFactory(WebSocketServerFactory):
    """
    Checks given JSON URLs by clients and broadcasts back to them
    if the JSON has changed
    """

    def __init__(self, url, debug=False, debugCodePaths=False):
        WebSocketServerFactory.__init__(self, url, debug=debug, debugCodePaths=debugCodePaths)
        self.urlCacheDict = {}
        self.clients = []
        self.clients_urls = {}
        self.tick()

    def tick(self):
        self.checkURLs()
        reactor.callLater(0.1, self.tick)

    def sendClientCommand(self, clients, command, data):
        msg = {"cmd": command, "data": data}
        msg = json.dumps(msg)

        for client in clients:
            client.sendMessage(msg)

    def jsonChanged(self, json, cachedJSON):
        if cachedJSON is None:
            return True
        else:
            if isinstance(cachedJSON, dict):
                added, removed, modified, same = dict_compare(json, cachedJSON)
                if len(added) > 0 or len(removed) > 0 or len(modified) > 0:
                    return True
            else:
                return cachedJSON != json

        return False

    def checkURLs(self):
        for urlCache in self.urlCacheDict.values():
            #Thread each of these
            try:
                if urlCache.locked is False and urlCache.pollNeeded():
                    urlCache.locked = True

                    p = Thread(target=self.checkURL, args=(urlCache, ))
                    p.start()
            except Exception as e:
                logging.error("{0}".format(e))

    def checkURL(self, urlCache):
        url = urlCache.url
        cachedURL = self.urlCacheDict[url]
        if cachedURL.errorCount > MAX_ERRORS:
            logging.info("Removing cached URL as it has too many errors {0}".format(url))
            self.sendClientCommand(cachedURL.clients, KRT_URL_DROPPED, url)
            updateLock.acquire()
            del self.urlCacheDict[url]
            updateLock.release()
            return
        if urlCache.pollNeeded():
            try:
                #logging.info("Polling: {0}".format(url))
                response = urllib2.urlopen(url, timeout=cachedURL.currentPollInterval-1)
                updateLock.acquire()
                cachedURL.pollSuccess()
                jsonObj = json.load(response)
                if self.jsonChanged(jsonObj, cachedURL.cachedJSON):
                    cachedURL.cachedJSON = jsonObj
                    clients = cachedURL.clients
                    logging.info("JSON at {1} Changed, informing {0} client(s)".format(len(clients), url))
                    data = {"url": url, "data": jsonObj}
                    self.sendClientCommand(clients, KRT_JSON_DATA, data)

                #Reset error count to reduce cutting of many users
                #in busy times
                cachedURL.errorCount = 0
            except Exception as e:
                logging.error("{0}: {1}".format(e, url))
                cachedURL.pollFailure()
            finally:
                cachedURL.locked = False

                if updateLock.locked():
                    updateLock.release()

    def register(self, client):
        if not client in self.clients:
            logging.info("registered client " + client.peerstr)
            self.clients.append(client)

    def unregister(self, client):
        if client in self.clients:
            logging.info("unregistered client " + client.peerstr)
            self.clients.remove(client)
            for items in self.urlCacheDict.items():
                url = items[0]
                urlCache = items[1]
                if client in urlCache.clients:
                    urlCache.clients.remove(client)

                if len(urlCache.clients) == 0:
                    del self.urlCacheDict[url]
                    logging.info("Removed stale cached URL {0}".format(url))


    def clientMessage(self, msg, client):
        try:
            data = json.loads(msg)
            if data["cmd"] == KRT_REGISTER_URL:
                if isinstance(data["data"], basestring):
                    url = data["data"]
                else:
                    url = data["data"]["url"]
                if not url in self.urlCacheDict:
                    logging.info("Created new url {0} for {1}".format(url, client.peer))
                    self.urlCacheDict[url] = CachedURL(url)
                    self.urlCacheDict[url].clients = [client, ]
                else:
                    logging.info("Added {1} to url {0}".format(url, client.peer))
                    self.urlCacheDict[url].clients.append(client)

                if not isinstance(data["data"], basestring) and "waitForPush" in data["data"] and data["data"]["waitForPush"]:
                    self.urlCacheDict[url].waitForPush = True
                    if "pushFilters" in data["data"]:
                        filters = data["data"]["pushFilters"]
                        if isinstance(filters, basestring):
                            self.urlCacheDict[url].pushFilters = json.loads(filters)
                        else:
                            self.urlCacheDict[url].pushFilters = filters
                    logging.info("URL {0} is waiting for push data with these filters {1}".format(url, self.urlCacheDict[url].pushFilters))
            elif data["cmd"] == KRT_PUSH_DATA:
                logging.info("Data pushed from server {0}".format(data["server"]))
                self.update_push_urls(data)

        except AttributeError as e:
            pass
        except ValueError as e:
            pass

    def update_push_urls(self, data):

        def filter_dict_compare(f_dict, v_dict):
            for n, f in f_dict.iteritems():
                if n in v_dict and v_dict[n] != f:
                    return False

            return True

        def matches_filter(urlCache, events):
            if len(urlCache.pushFilters) == 0:
                return True

            for event in events:
                if "event" in event and event["event"] in urlCache.pushFilters:
                    event_name = event["event"]
                    filter_dict = urlCache.pushFilters[event_name]
                    if len(filter_dict) == 0:
                        return True

                    payload = event["payload"]
                    for filterName, f in filter_dict.iteritems():
                        if filterName in payload:
                            v = payload[filterName]
                            if isinstance(f, dict):
                                return filter_dict_compare(f, v)
                            else:
                                return f == v

            return False

        events = data["data"]
        for url, obj in self.urlCacheDict.iteritems():
            if obj.waitForPush:
                if "server" in data and data["server"] in url:
                    if matches_filter(obj, events):
                        obj.newData = True

def createDeamon():
    import os, sys
    fpid = os.fork()
    if fpid is not 0:
        f = open('autobahnServer.pid','w')
        f.write(str(fpid))
        f.close()
        sys.exit(0)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'debug':
        log.startLogging(sys.stdout)
        debug = True
    elif len(sys.argv) > 1 and sys.argv[1] == 'daemon':
        createDeamon()
        debug = False
    else:
        debug = False

    logFormat = '%(asctime)s %(levelname)s: %(message)s'
    dateFormat = '%m/%d/%Y %I:%M:%S %p'
    logging.basicConfig(format=logFormat, filename='autobahnServer.log', level=logging.INFO, datefmt=dateFormat)

    if len(sys.argv) == 1 or (len(sys.argv) > 1 and sys.argv[1] != 'daemon'):
        #Add console logging
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter(logFormat, datefmt=dateFormat)
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)

    ServerFactory = BroadcastServerFactory

    factory = ServerFactory("ws://localhost:{0}".format(PORT),
                            debug=debug,
                            debugCodePaths=debug)

    factory.protocol = BroadcastServerProtocol
    factory.setProtocolOptions(allowHixie76=True)
    listenWS(factory)

    webdir = File(".")
    sweb = Site(webdir)
    reactor.listenTCP(8080, factory)
    reactor.run()
    logging.info("Starting autobahn server on port {0}".format(PORT))