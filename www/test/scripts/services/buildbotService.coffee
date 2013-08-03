beforeEach module 'app'

describe 'buildbot service', ->
    mockEventSource()
    buildbotService = {}
    EventSourceMock = {}
    $scope = {}
    $httpBackend = {}

    injected = ($injector) ->
        $httpBackend = $injector.get('$httpBackend')
        $scope = $injector.get('$rootScope').$new()
        buildbotService = $injector.get('buildbotService')

    beforeEach(inject(injected))

    it 'should query for changes at /changes and receive an empty array', ->
        $httpBackend.expectGET('api/v2/changes').respond([])
        p = buildbotService.all("changes").bind($scope, "changes")
        p.then((res) ->
            expect(res.length).toBe(0)
            )
        $httpBackend.flush()

    it 'should query for build/1/step/2 and receive a SUCCESS result', ->
        $httpBackend.expectGET('api/v2/build/1/step/2').respond({res: "SUCCESS"})
        r = buildbotService.one("build", 1).one("step", 2)
        p = r.bind($scope, "step_scope")
        p.then((res) ->
            expect(res.res).toBe("SUCCESS")
            )
        $httpBackend.flush()

    it 'should query default scope_key to route key', ->
        $httpBackend.expectGET('api/v2/build/1/step/2').respond({res: "SUCCESS"})
        p = buildbotService.one("build", 1).one("step", 2).bind($scope)
        expect($scope.step).toBe(p)
        $httpBackend.flush()
        expect($scope.step).toBe(p)

    it 'should close the eventsource on scope.$destroy()', ->
        $httpBackend.expectGET('api/v2/build/1/step/2').respond({res: "SUCCESS"})
        r = buildbotService.one("build", 1).one("step", 2)
        p = r.bind($scope)
        expect($scope.step).toBe(p)
        $httpBackend.flush()
        expect(r.source.readyState).toBe(1)
        $scope.$destroy()
        expect(r.source.readyState).toBe(2)

    it 'should close the eventsource on unbind()', ->
        $httpBackend.expectGET('api/v2/build/1/step/2').respond({res: "SUCCESS"})
        r = buildbotService.one("build", 1).one("step", 2)
        p = r.bind($scope)
        expect($scope.step).toBe(p)
        $httpBackend.flush()
        expect(r.source.readyState).toBe(1)
        r.unbind()
        expect(r.source.readyState).toBe(2)

    it 'should update the $scope when event received', ->
        $httpBackend.expectGET('api/v2/build/1/step/2').respond({res: "PENDING", otherfield: "FOO"})
        r = buildbotService.one("build", 1).one("step", 2)
        p = r.bind($scope)
        expect($scope.step).toBe(p)
        p.then((res) ->
            $scope.step=res  # this is done automatically by ng in real environment but not in test
            )
        $httpBackend.flush()
        expect(r.source.url).toBe("sse/build/1/step/2")
        expect($scope.step.res).toBe("PENDING")
        r.source.fakeEvent("update", {event: "update", msg: {res: "SUCCESS"}})
        expect($scope.step.res).toBe("SUCCESS")
        # should not override other fields
        expect($scope.step.otherfield).toBe("FOO")

    it 'should update the $scope when event received for collections', ->
        $httpBackend.expectGET('api/v2/build/1/step').respond([])
        r = buildbotService.one("build", 1).all("step")
        p = r.bind($scope)
        expect($scope.step).toBe(p)
        p.then((res) ->
            $scope.step=res  # this is done automatically by ng in real environment but not in test
            )
        $httpBackend.flush()
        expect(r.source.url).toBe("sse/build/1/step")
        expect($scope.step.length).toBe(0)
        r.source.fakeEvent("new", {event: "new", msg: {res: "SUCCESS"}})
        expect($scope.step.length).toBe(1)
        expect($scope.step[0].res).toBe("SUCCESS")
