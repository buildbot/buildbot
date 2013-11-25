if window.__karma__?
    beforeEach module 'app'

    describe 'buildbot service', ->
        mockEventSource()
        buildbotService = {}
        EventSourceMock = {}
        $scope = {}
        $httpBackend = {}

        injected = ($injector) ->
            $httpBackend = $injector.get('$httpBackend')
            decorateHttpBackend($httpBackend)
            $scope = $injector.get('$rootScope').$new()
            buildbotService = $injector.get('buildbotService')

        beforeEach(inject(injected))

        it 'should query for changes at /changes and receive an empty array', ->
            $httpBackend.expectGET('api/v2/changes').respond({changes:[]})
            buildbotService.all("changes").bind($scope, "changes")
            $httpBackend.flush()
            expect($scope.changes.length).toBe(0)

        it 'should query for build/1/step/2 and receive a SUCCESS result', ->
            $httpBackend.expectGET('api/v2/build/1/step/2').respond({steps:[{res: "SUCCESS"}]})
            r = buildbotService.one("build", 1).one("step", 2)
            r.bind($scope, "step_scope")
            $httpBackend.flush()
            expect($scope.step_scope.res).toBe("SUCCESS")

        it 'should query for build/1/step/2 mocked via dataspec', ->
            $httpBackend.expectDataGET('build/1/step/2')
            r = buildbotService.one("build", 1).one("step", 2)
            r.bind($scope)
            $httpBackend.flush()
            expect($scope.step.state_strings).toEqual(["mystate_strings"])

        it 'should query default scope_key to route key', ->
            $httpBackend.expectGET('api/v2/build/1/step/2').respond({steps:[{res: "SUCCESS"}]})
            buildbotService.one("build", 1).one("step", 2).bind($scope)
            $httpBackend.flush()
            expect($scope.step.res).toBe("SUCCESS")

        it 'should close the eventsource on scope.$destroy()', ->
            $httpBackend.expectGET('api/v2/build/1/step/2').respond({steps:[{res: "SUCCESS"}]})
            r = buildbotService.one("build", 1).one("step", 2)
            r.bind($scope)
            $httpBackend.flush()
            expect(r.source.readyState).toBe(1)
            $scope.$destroy()
            expect(r.source.readyState).toBe(2)

        it 'should close the eventsource on unbind()', ->
            $httpBackend.expectGET('api/v2/build/1/step/2').respond({steps:[{res: "SUCCESS"}]})
            r = buildbotService.one("build", 1).one("step", 2)
            r.bind($scope)
            $httpBackend.flush()
            expect(r.source.readyState).toBe(1)
            r.unbind()
            expect(r.source.readyState).toBe(2)

        it 'should update the $scope when event received', ->
            $httpBackend.expectGET('api/v2/build/1/step/2').respond({steps:[{res: "PENDING", otherfield: "FOO"}]})
            r = buildbotService.one("build", 1).one("step", 2)
            r.bind($scope)
            $httpBackend.flush()
            expect(r.source.url).toBe("sse/build/1/step/2")
            expect($scope.step.res).toBe("PENDING")
            r.source.fakeEvent("update", {event: "update", data: '{"res": "SUCCESS"}'})
            expect($scope.step.res).toBe("SUCCESS")
            # should not override other fields
            expect($scope.step.otherfield).toBe("FOO")

        it 'should update the $scope when event received for collections', ->
            $httpBackend.expectGET('api/v2/build/1/step').respond({steps:[]})
            r = buildbotService.one("build", 1).all("step")
            r.bind($scope)
            $httpBackend.flush()
            expect(r.source.url).toBe("sse/build/1/step")
            expect($scope.step.length).toBe(0)
            r.source.fakeEvent("new", {event: "new", data: '{"res": "SUCCESS"}'})
            expect($scope.step.length).toBe(1)
            expect($scope.step[0].res).toBe("SUCCESS")
