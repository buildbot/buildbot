/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS205: Consider reworking code to avoid use of IIFEs
 * DS206: Consider reworking classes to avoid initClass
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('Socket service', function() {

    let $location, socket, socketService;
    var WebSocketBackend = (function() {
        let self = undefined;
        let MockWebSocket = undefined;
        WebSocketBackend = class WebSocketBackend {
            static initClass() {
                this.prototype.sendQueue = [];
                this.prototype.receiveQueue = [];

                self = null;

                // mocked WebSocket
                MockWebSocket = (function() {
                    MockWebSocket = class MockWebSocket {
                        static initClass() {
                            this.prototype.OPEN = 1;
                        }
                        send(message) {
                            return self.receiveQueue.push(message);
                        }
                    };
                    MockWebSocket.initClass();
                    return MockWebSocket;
                })();
            }
            constructor() {
                self = this;
                this.webSocket = new MockWebSocket();
            }

            send(message) {
                const data = {data: message};
                return this.sendQueue.push(data);
            }

            flush() {
                let message;
                while ((message = this.sendQueue.shift())) {
                    this.webSocket.onmessage(message);
                }
            }

            getWebSocket() {
                return this.webSocket;
            }
        };
        WebSocketBackend.initClass();
        return WebSocketBackend;
    })();

    const webSocketBackend = new WebSocketBackend();
    beforeEach(function() {
        angular.mock.module('bbData');
        angular.mock.module($provide => $provide.constant('webSocketService', webSocketBackend));
    });

    let $rootScope = (socketService = (socket = ($location = null)));
    const injected = function($injector) {
        $rootScope = $injector.get('$rootScope');
        $location = $injector.get('$location');
        socketService = $injector.get('socketService');
        ({ socket } = socketService);
        spyOn(socket, 'send').and.callThrough();
        spyOn(socket, 'onmessage').and.callThrough();
    };

    beforeEach(inject(injected));

    it('should be defined', () => expect(socketService).toBeDefined());

    it('should send the data, when the WebSocket is open', function() {
        // socket is opening
        socket.readyState = 0;
        // 2 message to be sent
        const msg1 = {a: 1};
        const msg2 = {b: 2};
        const msg3 = {c: 3};
        socketService.send(msg1);
        socketService.send(msg2);
        expect(socket.send).not.toHaveBeenCalled();
        // open the socket
        socket.onopen();
        expect(socket.send).toHaveBeenCalled();
        expect(webSocketBackend.receiveQueue).toContain(angular.toJson(msg1));
        expect(webSocketBackend.receiveQueue).toContain(angular.toJson(msg2));
        expect(webSocketBackend.receiveQueue).not.toContain(angular.toJson(msg3));
    });

    it('should add an _id to each message', function() {
        socket.readyState = 1;
        expect(socket.send).not.toHaveBeenCalled();
        socketService.send({});
        expect(socket.send).toHaveBeenCalledWith(jasmine.any(String));
        const argument = socket.send.calls.argsFor(0)[0];
        expect(angular.fromJson(argument)._id).toBeDefined();
    });

    it('should resolve the promise when a response message is received with code 200', function() {
        socket.readyState = 1;
        const msg = {cmd: 'command'};
        const promise = socketService.send(msg);
        const handler = jasmine.createSpy('handler');
        promise.then(handler);
        // the promise should not be resolved
        expect(handler).not.toHaveBeenCalled();

        // get the id from the message
        const argument = socket.send.calls.argsFor(0)[0];
        const id = angular.fromJson(argument)._id;
        // create a response message with status code 200
        const response = angular.toJson({_id: id, code: 200});

        // send the message
        webSocketBackend.send(response);
        $rootScope.$apply(() => webSocketBackend.flush());
        // the promise should be resolved
        expect(handler).toHaveBeenCalled();
    });

    it('should reject the promise when a response message is received, but the code is not 200', function() {
        socket.readyState = 1;
        const msg = {cmd: 'command'};
        const promise = socketService.send(msg);
        const handler = jasmine.createSpy('handler');
        const errorHandler = jasmine.createSpy('errorHandler');
        promise.then(handler, errorHandler);
        // the promise should not be rejected
        expect(handler).not.toHaveBeenCalled();
        expect(errorHandler).not.toHaveBeenCalled();

        // get the id from the message
        const argument = socket.send.calls.argsFor(0)[0];
        const id = angular.fromJson(argument)._id;
        // create a response message with status code 500
        const response = angular.toJson({_id: id, code: 500});

        // send the message
        webSocketBackend.send(response);
        $rootScope.$apply(() => webSocketBackend.flush());
        // the promise should be rejected
        expect(handler).not.toHaveBeenCalled();
        expect(errorHandler).toHaveBeenCalled();
    });


    describe('getUrl()', function() {

        it('should return the WebSocket url based on the host and port (localhost)', function() {
            const host = 'localhost';
            const port = 8080;
            spyOn($location, 'host').and.returnValue(host);
            spyOn($location, 'port').and.returnValue(port);
            spyOn(socketService, 'getRootPath').and.returnValue('/');

            const url = socketService.getUrl();
            expect(url).toBe('ws://localhost:8080/ws');
        });

        it('should return the WebSocket url based on the host and port', function() {
            const host = 'buildbot.test';
            const port = 80;
            spyOn($location, 'host').and.returnValue(host);
            spyOn($location, 'port').and.returnValue(port);
            spyOn(socketService, 'getRootPath').and.returnValue('/');

            const url = socketService.getUrl();
            expect(url).toBe('ws://buildbot.test/ws');
        });

        it('should return the WebSocket url based on the host and port and protocol', function() {
            const host = 'buildbot.test';
            const port = 443;
            const protocol = 'https';
            spyOn($location, 'host').and.returnValue(host);
            spyOn($location, 'port').and.returnValue(port);
            spyOn($location, 'protocol').and.returnValue(protocol);
            spyOn(socketService, 'getRootPath').and.returnValue('/');

            const url = socketService.getUrl();
            expect(url).toBe('wss://buildbot.test/ws');
        });

        it('should return the WebSocket url based on the host and port and protocol and basedir', function() {
            const host = 'buildbot.test';
            const port = 443;
            const protocol = 'https';
            const path = '/travis/';
            spyOn($location, 'host').and.returnValue(host);
            spyOn($location, 'port').and.returnValue(port);
            spyOn($location, 'protocol').and.returnValue(protocol);
            spyOn(socketService, 'getRootPath').and.returnValue(path);

            const url = socketService.getUrl();
            expect(url).toBe('wss://buildbot.test/travis/ws');
        });
    });
});
