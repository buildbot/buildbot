beforeEach module 'app'

describe 'mq service', ->
    mqService = $scope = $httpBackend = $rootScope = null
    ws =
        send: ->

    # common event receiver
    event_receiver =
        receiver1: ->
        receiver2: ->

    injected = ($injector) ->
        $rootScope = $injector.get('$rootScope')
        $scope = $rootScope.$new()
        mqService = $injector.get('mqService')
        # stub out the actual backend of mqservice
        spyOn(mqService,"getWebSocket").and.returnValue(ws)
        spyOn(ws,"send").and.returnValue(null)
        spyOn(event_receiver,"receiver1").and.returnValue(null)
        spyOn(event_receiver,"receiver2").and.returnValue(null)

    beforeEach(inject(injected))

    it 'match function should be correct', ->
        expect(mqService._match("a/b/*", "a/b/c")).toBe(true)
        expect(mqService._match("a/b/*", "a/b/c/d")).toBe(false)
        expect(mqService._match("a/b/*/*", "a/b/c/d")).toBe(true)
        expect(mqService._match("a/b/*/*", "a/b/c/d/e")).toBe(false)

    it 'should setup everything in setBaseURL', ->
        expect(ws.onopen).toBeUndefined()
        mqService.setBaseUrl("ws")
        expect(mqService.getWebSocket).toHaveBeenCalled()
        expect(ws.onopen).toBeDefined()
        expect(ws.onerror).toBeDefined()
        expect(ws.onmessage).toBeDefined()

    it 'should work with simple pub/sub usecase', ->
        mqService.setBaseUrl("sse/")
        mqService.on("bla", event_receiver.receiver1)
        mqService.broadcast("bla", {"msg":true})
        expect(event_receiver.receiver1).toHaveBeenCalledWith({"msg": true}, "bla")

    it 'should work with generic pub/sub usecase', ->
        mqService.setBaseUrl("sse/")
        mqService.on("*/bla", event_receiver.receiver1)
        mqService.broadcast("1/bla", {"msg":true})
        expect(event_receiver.receiver1).toHaveBeenCalledWith({"msg": true}, "1/bla")
        mqService.broadcast("2/bla", {"msg":true})
        expect(event_receiver.receiver1).toHaveBeenCalledWith({"msg": true}, "2/bla")

    it 'should send to several receivers', ->
        mqService.setBaseUrl("sse/")
        mqService.on("1/bla", event_receiver.receiver1)
        mqService.on("*/bla", event_receiver.receiver2)
        mqService.broadcast("1/bla", {"msg":true})
        expect(event_receiver.receiver1).toHaveBeenCalledWith({"msg": true}, "1/bla")
        expect(event_receiver.receiver2).toHaveBeenCalledWith({"msg": true}, "1/bla")

    it 'should filter to several receivers', ->
        mqService.setBaseUrl("sse/")
        mqService.on("1/bla", event_receiver.receiver1)
        mqService.on("*/bla", event_receiver.receiver2)
        mqService.broadcast("2/bla", {"msg":true})
        expect(event_receiver.receiver2).toHaveBeenCalledWith({"msg": true}, "2/bla")
        expect(event_receiver.receiver1).not.toHaveBeenCalled()

    it 'should use the backend to register to messages', ->
        mqService.setBaseUrl("ws/")
        called = []
        unregs = []
        p1 = mqService.on("1/bla", event_receiver.receiver1)
        p2 = mqService.on("*/bla", event_receiver.receiver2)
        p1.then (unreg) ->
            called.push('p1')
            unregs.push(unreg)
        p2.then (unreg) ->
            called.push('p2')
            unregs.push(unreg)
        ws.readyState = 1
        ws.onopen()
        expect(ws.send).toHaveBeenCalledWith('{"cmd":"startConsuming","path":"1/bla","_id":2}')
        expect(ws.send).toHaveBeenCalledWith('{"cmd":"startConsuming","path":"*/bla","_id":3}')
        # fake the response
        ws.onmessage(data: '{"msg":"OK","code":200,"_id":3}')
        ws.onmessage(data: '{"msg":"OK","code":200,"_id":2}')
        $rootScope.$apply()
        expect(called).toEqual(["p1", "p2"])

        # fake the message
        msg = '{"m": {"buildid": 1}, "k": "1/bla"}'
        ws.onmessage(data: msg)
        expect(event_receiver.receiver1).toHaveBeenCalledWith({"buildid": 1}, "1/bla")
        expect(event_receiver.receiver2).toHaveBeenCalledWith({"buildid": 1}, "1/bla")

        # unregister
        called = []
        p1 = unregs[0]()
        p2 = unregs[1]()
        $rootScope.$apply()
        expect(ws.send).toHaveBeenCalledWith('{"cmd":"stopConsuming","path":"1/bla","_id":4}')
        expect(ws.send).toHaveBeenCalledWith('{"cmd":"stopConsuming","path":"*/bla","_id":5}')
        p1.then (unreg) ->
            called.push('p1')
        p2.then (unreg) ->
            called.push('p2')
        expect(called).toEqual([])
        ws.onmessage(data: '{"msg":"OK","code":200,"_id":4}')
        ws.onmessage(data: '{"msg":"OK","code":200,"_id":5}')
        $rootScope.$apply()
        expect(called).toEqual(["p1", "p2"])
