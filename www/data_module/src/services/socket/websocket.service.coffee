class WebSocket extends Service
    constructor: ($window) ->
        return new class WebSocketProvider
            constructor: ->

            # this function will be mocked in the tests
            getWebSocket: (url) ->
                match = /wss?:\/\//.exec(url)

                if not match
                    throw new Error('Invalid url provided')

                # use ReconnectingWebSocket if available
                # TODO write own implementation?
                if $window.ReconnectingWebSocket?
                    new $window.ReconnectingWebSocket(url)
                else
                    new $window.WebSocket(url)
