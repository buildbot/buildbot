class Socket extends Service
    constructor: ($log, $q, $location, $window) ->
        return new class SocketService
            # waiting queue
            queue: []
            # deferred object for resolving response promises
            # map of id: promise
            deferred: {}
            # the onMessage(key, message) function will be called to handle an update message
            onMessage: null
            # the onClose() function will be called to handle the close event
            onClose: null

            open: ->
                @socket ?= @getWebSocket()
                # flush queue on open
                @socket.onopen = => @flush()

                @socket.onmessage = (message) =>
                    try
                        data = angular.fromJson(message.data)
                        $log.debug('WS message', data)

                        # response message
                        if data._id?
                            [message, error, id, code] = [data.msg, data.error, data._id, data.code]
                            if code is 200 then @deferred[id]?.resolve(message)
                            else @deferred[id]?.reject(error)
                        # update message
                        else
                            [key, message] = [data.k, data.m]
                            @onMessage?(key, message)

                    catch e
                        $log.error(e)

                @socket.onclose = =>
                    @onClose?()

            close: ->
                @socket?.close()

            send: (data) ->
                # add _id to each message
                id = @nextId()
                data._id = id
                @deferred[id] ?= $q.defer()

                data = angular.toJson(data)
                # ReconnectingWebSocket does not put status constants on instance
                if @socket.readyState is (@socket.OPEN or 1)
                    $log.debug 'WS send', angular.fromJson(data)
                    @socket.send(data)
                else
                    # if the WebSocket is not open yet, add the data to the queue
                    @queue.push(data)

                # return promise, which will be resolved once a response message has the same id
                return @deferred[id].promise

            flush: ->
                # send all the data waiting in the queue
                while data = @queue.shift()
                    $log.debug 'WS send', angular.fromJson(data)
                    @socket.send(data)

            nextId: ->
                @id ?= 0
                @id = if @id < 1000 then @id + 1 else 0
                return @id

            getUrl: ->
                host = $location.host()
                port = if $location.port() is 80 then '' else ':' + $location.port()
                return "ws://#{host}#{port}/ws"

            # this function will be mocked in the tests
            getWebSocket: ->
                url = @getUrl()
                # use ReconnectingWebSocket if available
                # TODO write own implementation?
                if $window.ReconnectingWebSocket?
                    new $window.ReconnectingWebSocket(url)
                else
                    new $window.WebSocket(url)
