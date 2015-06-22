class Socket extends Service
    constructor: ($log, $q, $rootScope, $location, Stream, webSocketService) ->
        return new class SocketService
            # subscribe to event stream to get WebSocket messages
            eventStream: null

            constructor: ->
                # waiting queue
                @queue = []
                # deferred object for resolving response promises
                # map of id: promise
                @deferred = {}
                # open socket
                @open()

            open: ->
                @socket ?= webSocketService.getWebSocket(@getUrl())

                # flush queue on open
                @socket.onopen = => @flush()

                @setupEventStream()

            setupEventStream: ->
                @eventStream ?= new Stream()

                @socket.onmessage = (message) =>
                    try
                        data = angular.fromJson(message.data)
                        $log.debug('WS message', data)

                        # response message
                        if data.code?
                            id = data._id
                            if data.code is 200 then @deferred[id]?.resolve(true)
                            else @deferred[id]?.reject(data)
                        # status update message
                        else
                            $rootScope.$applyAsync =>
                                @eventStream.push(data)
                    catch e
                        @deferred[id]?.reject(e)

            close: ->
                @socket.close()

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
                while data = @queue.pop()
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
