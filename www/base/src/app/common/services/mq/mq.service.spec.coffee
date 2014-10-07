beforeEach module 'app'

describe 'mq service', ->
    mqService = $scope = $httpBackend = null
    es =
        addEventListener: (event, cb) ->
            this["on#{event}"] = cb

    # common event receiver
    event_receiver =
        receiver1: ->
        receiver2: ->

    injected = ($injector) ->
        $httpBackend = $injector.get('$httpBackend')
        decorateHttpBackend($httpBackend)
        $scope = $injector.get('$rootScope').$new()
        mqService = $injector.get('mqService')
        # stub out the actual backend of mqservice
        spyOn(mqService,"getEventSource").and.returnValue(es)
        spyOn(event_receiver,"receiver1").and.returnValue(null)
        spyOn(event_receiver,"receiver2").and.returnValue(null)

    beforeEach(inject(injected))

    it 'match function should be correct', ->
        expect(mqService._match("a/b/*", "a/b/c")).toBe(true)
        expect(mqService._match("a/b/*", "a/b/c/d")).toBe(false)
        expect(mqService._match("a/b/*/*", "a/b/c/d")).toBe(true)
        expect(mqService._match("a/b/*/*", "a/b/c/d/e")).toBe(false)

    it 'should setup everything in setBaseURL', ->
        expect(es.onopen).toBeUndefined()
        mqService.setBaseUrl("sse/")
        expect(mqService.getEventSource).toHaveBeenCalled()
        expect(es.onopen).toBeDefined()
        expect(es.onerror).toBeDefined()
        expect(es.onmessage).toBeDefined()
        expect(es.onhandshake).toBeDefined()
        expect(es.onevent).toBeDefined()

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
        $httpBackend.expectGET('sse/add/<cid>/1/bla').respond("")
        $httpBackend.expectGET('sse/add/<cid>/*/bla').respond("")
        mqService.setBaseUrl("sse/")
        mqService.on("1/bla", event_receiver.receiver1)
        mqService.on("*/bla", event_receiver.receiver2)
        es.onopen()
        $httpBackend.verifyNoOutstandingRequest()
        es.onhandshake({data:"<cid>"})
        $httpBackend.flush()

    it 'should unregister on scope close', ->
        $httpBackend.expectGET('sse/add/<cid>/1/bla').respond("")
        $httpBackend.expectGET('sse/add/<cid>/*/bla').respond("")
        mqService.setBaseUrl("sse/")
        mqService.on("1/bla", event_receiver.receiver1, $scope)
        mqService.on("*/bla", event_receiver.receiver2, $scope)
        es.onopen()
        $httpBackend.verifyNoOutstandingRequest()
        es.onhandshake({data:"<cid>"})
        $httpBackend.flush()
        $httpBackend.expectGET('sse/remove/<cid>/1/bla').respond("")
        $httpBackend.expectGET('sse/remove/<cid>/*/bla').respond("")
        $scope.$destroy()
        $httpBackend.flush()
        expect ->
            mqService.broadcast("1/bla", {"msg":true})
        .toThrow()
        expect(event_receiver.receiver1).not.toHaveBeenCalled()
