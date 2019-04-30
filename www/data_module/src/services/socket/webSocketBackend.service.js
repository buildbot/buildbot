/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS205: Consider reworking code to avoid use of IIFEs
 * DS206: Consider reworking classes to avoid initClass
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
var WebSocketBackend = (function() {
    let self = undefined;
    let MockWebSocket = undefined;
    WebSocketBackend = class WebSocketBackend {
        static initClass() {
            self = null;

            this.prototype.sendQueue = [];
            this.prototype.receiveQueue = [];

            // mocked WebSocket
            MockWebSocket = (function() {
                MockWebSocket = class MockWebSocket {
                    static initClass() {
                        this.prototype.OPEN = 1;
                    }
                    send(message) {
                        return self.receiveQueue.push(message);
                    }
                    close() { return (typeof this.onclose === 'function' ? this.onclose() : undefined); }
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


angular.module('bbData')
.service('webSocketBackendService', [WebSocketBackend]);
