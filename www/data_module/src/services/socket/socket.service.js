/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS205: Consider reworking code to avoid use of IIFEs
 * DS206: Consider reworking classes to avoid initClass
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class Socket {
    constructor($log, $q, $rootScope, $location, Stream, webSocketService, $timeout) {
        let SocketService;
        return new ((SocketService = (function() {
            SocketService = class SocketService {
                static initClass() {
                    // subscribe to event stream to get WebSocket messages
                    this.prototype.eventStream = null;
                }

                constructor() {
                    // waiting queue
                    this.queue = [];
                    // deferred object for resolving response promises
                    // map of id: promise
                    this.deferred = {};
                    this.subscribers = {};
                    // open socket
                    this.open();
                }

                open() {
                    if (this.socket == null) { this.socket = webSocketService.getWebSocket(this.getUrl()); }

                    // flush queue on open
                    this.socket.onopen = () => this.flush();

                    return this.setupEventStream();
                }

                setupEventStream() {
                    if (this.eventStream == null) { this.eventStream = new Stream(); }

                    return this.socket.onmessage = message => {
                        let id;
                        try {
                            const data = angular.fromJson(message.data);

                            // response message
                            if (data.code != null) {
                                id = data._id;
                                if (data.code === 200) { return (this.deferred[id] != null ? this.deferred[id].resolve(true) : undefined);
                                } else { return (this.deferred[id] != null ? this.deferred[id].reject(data) : undefined); }
                            // status update message
                            } else {
                                return $rootScope.$applyAsync(() => {
                                    return this.eventStream.push(data);
                                });
                            }
                        } catch (e) {
                            return (this.deferred[id] != null ? this.deferred[id].reject(e) : undefined);
                        }
                    };
                }

                close() {
                    return this.socket.close();
                }

                send(data) {
                    // add _id to each message
                    const id = this.nextId();
                    data._id = id;
                    if (this.deferred[id] == null) { this.deferred[id] = $q.defer(); }

                    data = angular.toJson(data);
                    // ReconnectingWebSocket does not put status constants on instance
                    if (this.socket.readyState === (this.socket.OPEN || 1)) {
                        this.socket.send(data);
                    } else {
                        // if the WebSocket is not open yet, add the data to the queue
                        this.queue.push(data);
                    }
                    // socket is not watched by protractor, so we need to
                    // create a timeout while we are using the socket so that protractor waits for it
                    const to = $timeout( ()=> {}, 20000)
                    // return promise, which will be resolved once a response message has the same id
                    return this.deferred[id].promise.then((r) => {
                        $timeout.cancel(to);
                        return r;
                    })
                }

                flush() {
                    // send all the data waiting in the queue
                    let data;
                    while ((data = this.queue.pop())) {
                        this.socket.send(data);
                    }
                }

                nextId() {
                    if (this.id == null) { this.id = 0; }
                    this.id = this.id < 1000 ? this.id + 1 : 0;
                    return this.id;
                }

                getRootPath() {
                    return location.pathname;
                }

                getUrl() {
                    const host = $location.host();
                    const protocol = $location.protocol() === 'https' ? 'wss' : 'ws';
                    const defaultport = $location.protocol() === 'https' ? 443 : 80;
                    const path = this.getRootPath();
                    const port = $location.port() === defaultport ? '' : `:${$location.port()}`;
                    return `${protocol}://${host}${port}${path}ws`;
                }

                // High level api. Maintain a list of subscribers for one event path
                subscribe(eventPath, collection) {
                    const l = this.subscribers[eventPath] != null ? this.subscribers[eventPath] : (this.subscribers[eventPath] = []);
                    l.push(collection);
                    if (l.length === 1) {
                        return this.send({
                            cmd: "startConsuming",
                            path: eventPath
                        });
                    }
                    return $q.resolve();
                }

                unsubscribe(eventPath, collection) {
                    const l = this.subscribers[eventPath] != null ? this.subscribers[eventPath] : (this.subscribers[eventPath] = []);
                    const pos = l.indexOf(collection);
                    if (pos >= 0) {
                        l.splice(pos, 1);
                        if (l.length === 0) {
                            return this.send({
                                cmd: "stopConsuming",
                                path: eventPath
                            });
                        }
                    }
                    return $q.resolve();
                }
            };
            SocketService.initClass();
            return SocketService;
        })()));
    }
}


angular.module('bbData')
.service('socketService', ['$log', '$q', '$rootScope', '$location', 'Stream', 'webSocketService', '$timeout', Socket]);
