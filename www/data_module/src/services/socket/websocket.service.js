/*
 * decaffeinate suggestions:
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class WebSocket {
    constructor($window) {
        let WebSocketProvider;
        return new (WebSocketProvider = class WebSocketProvider {
            constructor() {}

            // this function will be mocked in the tests
            getWebSocket(url) {
                const match = /wss?:\/\//.exec(url);

                if (!match) {
                    throw new Error('Invalid url provided');
                }

                // use ReconnectingWebSocket if available
                // TODO write own implementation?
                if ($window.ReconnectingWebSocket != null) {
                    return new $window.ReconnectingWebSocket(url);
                } else {
                    return new $window.WebSocket(url);
                }
            }
        });
    }
}


angular.module('bbData')
.service('webSocketService', ['$window', WebSocket]);
