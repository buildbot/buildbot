class WebSocketBackend extends Service
    self = null
    constructor: ->
        self = @
        @webSocket = new MockWebSocket()

    sendQueue: []
    receiveQueue: []
    send: (message) ->
        data = {data: message}
        @sendQueue.push(data)

    flush: ->
        while message = @sendQueue.shift()
            @webSocket.onmessage(message)

    getWebSocket: ->
        return @webSocket

    # mocked WebSocket
    class MockWebSocket
        OPEN: 1
        send: (message) ->
            self.receiveQueue.push(message)
        close: -> @onclose?()
