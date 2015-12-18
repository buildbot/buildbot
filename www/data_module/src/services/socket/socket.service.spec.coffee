describe 'Socket service', ->

    class WebSocketBackend
        sendQueue: []
        receiveQueue: []

        self = null
        constructor: ->
            self = @
            @webSocket = new MockWebSocket()

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

    webSocketBackend = new WebSocketBackend()
    beforeEach ->
        module 'bbData'
        module ($provide) ->
            $provide.constant('webSocketService', webSocketBackend)

    $rootScope = socketService = socket = $location = null
    injected = ($injector) ->
        $rootScope = $injector.get('$rootScope')
        $location = $injector.get('$location')
        socketService = $injector.get('socketService')
        socket = socketService.socket
        spyOn(socket, 'send').and.callThrough()
        spyOn(socket, 'onmessage').and.callThrough()

    beforeEach(inject(injected))

    it 'should be defined', ->
        expect(socketService).toBeDefined()

    it 'should send the data, when the WebSocket is open', ->
        # socket is opening
        socket.readyState = 0
        # 2 message to be sent
        msg1 = {a: 1}
        msg2 = {b: 2}
        msg3 = {c: 3}
        socketService.send(msg1)
        socketService.send(msg2)
        expect(socket.send).not.toHaveBeenCalled()
        # open the socket
        socket.onopen()
        expect(socket.send).toHaveBeenCalled()
        expect(webSocketBackend.receiveQueue).toContain(angular.toJson(msg1))
        expect(webSocketBackend.receiveQueue).toContain(angular.toJson(msg2))
        expect(webSocketBackend.receiveQueue).not.toContain(angular.toJson(msg3))

    it 'should add an _id to each message', ->
        socket.readyState = 1
        expect(socket.send).not.toHaveBeenCalled()
        socketService.send({})
        expect(socket.send).toHaveBeenCalledWith(jasmine.any(String))
        argument = socket.send.calls.argsFor(0)[0]
        expect(angular.fromJson(argument)._id).toBeDefined()

    it 'should resolve the promise when a response message is received with code 200', ->
        socket.readyState = 1
        msg = {cmd: 'command'}
        promise = socketService.send(msg)
        handler = jasmine.createSpy('handler')
        promise.then(handler)
        # the promise should not be resolved
        expect(handler).not.toHaveBeenCalled()

        # get the id from the message
        argument = socket.send.calls.argsFor(0)[0]
        id = angular.fromJson(argument)._id
        # create a response message with status code 200
        response = angular.toJson({_id: id, code: 200})

        # send the message
        webSocketBackend.send(response)
        $rootScope.$apply ->
            webSocketBackend.flush()
        # the promise should be resolved
        expect(handler).toHaveBeenCalled()

    it 'should reject the promise when a response message is received, but the code is not 200', ->
        socket.readyState = 1
        msg = {cmd: 'command'}
        promise = socketService.send(msg)
        handler = jasmine.createSpy('handler')
        errorHandler = jasmine.createSpy('errorHandler')
        promise.then(handler, errorHandler)
        # the promise should not be rejected
        expect(handler).not.toHaveBeenCalled()
        expect(errorHandler).not.toHaveBeenCalled()

        # get the id from the message
        argument = socket.send.calls.argsFor(0)[0]
        id = angular.fromJson(argument)._id
        # create a response message with status code 500
        response = angular.toJson({_id: id, code: 500})

        # send the message
        webSocketBackend.send(response)
        $rootScope.$apply ->
            webSocketBackend.flush()
        # the promise should be rejected
        expect(handler).not.toHaveBeenCalled()
        expect(errorHandler).toHaveBeenCalled()


    describe 'getUrl()', ->

        it 'should return the WebSocket url based on the host and port (localhost)', ->
            host = 'localhost'
            port = 8080
            spyOn($location, 'host').and.returnValue(host)
            spyOn($location, 'port').and.returnValue(port)
            spyOn(socketService, 'getRootPath').and.returnValue('/')

            url = socketService.getUrl()
            expect(url).toBe('ws://localhost:8080/ws')

        it 'should return the WebSocket url based on the host and port', ->
            host = 'buildbot.test'
            port = 80
            spyOn($location, 'host').and.returnValue(host)
            spyOn($location, 'port').and.returnValue(port)
            spyOn(socketService, 'getRootPath').and.returnValue('/')

            url = socketService.getUrl()
            expect(url).toBe('ws://buildbot.test/ws')

        it 'should return the WebSocket url based on the host and port and protocol', ->
            host = 'buildbot.test'
            port = 443
            protocol = 'https'
            spyOn($location, 'host').and.returnValue(host)
            spyOn($location, 'port').and.returnValue(port)
            spyOn($location, 'protocol').and.returnValue(protocol)
            spyOn(socketService, 'getRootPath').and.returnValue('/')

            url = socketService.getUrl()
            expect(url).toBe('wss://buildbot.test/ws')

        it 'should return the WebSocket url based on the host and port and protocol and basedir', ->
            host = 'buildbot.test'
            port = 443
            protocol = 'https'
            path = '/travis/'
            spyOn($location, 'host').and.returnValue(host)
            spyOn($location, 'port').and.returnValue(port)
            spyOn($location, 'protocol').and.returnValue(protocol)
            spyOn(socketService, 'getRootPath').and.returnValue(path)

            url = socketService.getUrl()
            expect(url).toBe('wss://buildbot.test/travis/ws')
