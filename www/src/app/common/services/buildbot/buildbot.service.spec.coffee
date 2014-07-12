if window.__karma__?
    beforeEach module 'app'

    describe 'buildbot service', ->
        buildbotService = mqService = $scope = $httpBackend = $rootScope = $timeout = null

        injected = ($injector) ->
            $httpBackend = $injector.get('$httpBackend')
            decorateHttpBackend($httpBackend)
            $rootScope = $injector.get('$rootScope')
            $scope = $rootScope.$new()
            mqService = $injector.get('mqService')
            $timeout = $injector.get('$timeout')
            $q = $injector.get('$q')
            # stub out the actual backend of mqservice
            spyOn(mqService,"setBaseUrl").and.returnValue(null)
            spyOn(mqService,"startConsuming").and.returnValue($q.when( -> ))
            spyOn(mqService,"stopConsuming").and.returnValue(null)
            buildbotService = $injector.get('buildbotService')

        beforeEach(inject(injected))

        it 'should query for changes at /changes and receive an empty array', ->
            $httpBackend.expectDataGET 'changes',
                nItems:1
            buildbotService.all("changes").bind($scope)
            $httpBackend.flush()
            expect($scope.changes.length).toBe(1)

        it 'should query for builds/1/steps/2 and receive a SUCCESS result', ->
            $httpBackend.expectDataGET 'builds/1/steps/2',
                override: (res) ->
                    res.steps[0].res = "SUCCESS"
            r = buildbotService.one("builds", 1).one("steps", 2)
            r.bind $scope,
                dest_key: "step_scope"
            $httpBackend.flush()
            expect($scope.step_scope.res).toBe("SUCCESS")

        it 'should query for builds/1/steps/2 mocked via dataspec', ->
            $httpBackend.expectDataGET('builds/1/steps/2')
            r = buildbotService.one("builds", 1).one("steps", 2)
            r.bind($scope)
            $httpBackend.flush()
            expect($scope.step.state_strings).toEqual(["mystate_strings"])

        it 'should query default scope_key to route key', ->
            $httpBackend.expectGET('api/v2/builds/1/steps/2').respond({steps:[{res: "SUCCESS"}]})
            buildbotService.one("builds", 1).one("steps", 2).bind($scope)
            $httpBackend.flush()
            expect($scope.step.res).toBe("SUCCESS")

        it 'should update the $scope when event received', ->
            $httpBackend.expectGET('api/v2/builds/1/steps/2')
            .respond({steps:[{res: "PENDING", otherfield: "FOO"}]})
            r = buildbotService.one("builds", 1).one("steps", 2)
            r.bind $scope,
                ismutable: -> true
            $httpBackend.flush()
            expect($scope.step.res).toBe("PENDING")
            mqService.broadcast("builds/1/steps/2/update", {"res": "SUCCESS"})
            $rootScope.$digest()
            expect($scope.step.res).toBe("SUCCESS")
            # should not override other fields
            expect($scope.step.otherfield).toBe("FOO")

        it 'should update the $scope when event received for collections', ->
            $httpBackend.expectGET('api/v2/builds/1/steps')
            .respond({steps:[{stepid:1,res: "PENDING", otherfield: "FOO"}]})
            r = buildbotService.one("builds", 1).all("steps")
            childs = []
            r.bind $scope,
                ismutable: -> true
                onchild: (c) -> childs.push(c)
            $httpBackend.flush()
            expect($scope.steps.length).toBe(1)
            mqService.broadcast("builds/1/steps/3/new", {stepid:3, "res": "SUCCESS"})
            $rootScope.$digest()
            expect($scope.steps.length).toBe(2)
            expect(childs.length).toBe(2)
            for c in childs
                # make sure the objects sent to onchild are restangular objects
                expect(c.all).toBeDefined()
                expect(c.one).toBeDefined()
            expect($scope.steps[1].res).toBe("SUCCESS")

        it 'should update the $scope when event received for collections with same id', ->
            $httpBackend.expectGET('api/v2/builds/1/steps')
            .respond({steps:[{stepid:1, res: "PENDING", otherfield: "FOO"}]})
            r = buildbotService.one("builds", 1).all("steps")
            r.bind($scope)
            $httpBackend.flush()
            expect($scope.steps.length).toBe(1)
            mqService.broadcast("builds/1/steps/3/new", {stepid:3, "res": "SUCCESS"})
            mqService.broadcast("builds/1/steps/1/update", {stepid:1, res: "SUCCESS"})
            $rootScope.$digest()
            expect($scope.steps.length).toBe(2)
            expect($scope.steps[0].res).toBe("SUCCESS")
            expect($scope.steps[1].res).toBe("SUCCESS")

        it 'has a onchild api which should be usable for restangular api', ->
            $httpBackend.expectGET('api/v2/builds')
            .respond({builds:[{buildid:1,res: "PENDING", otherfield: "FOO"}]})
            $httpBackend.expectDataGET('builds/1/steps')
            r = buildbotService.all("builds")
            r.bind $scope,
                ismutable: -> true
                onchild: (build) ->
                    build.all("steps").bind $scope,
                        dest: build

            $httpBackend.flush()
            $httpBackend.expectDataGET('builds/3/steps')
            mqService.broadcast("builds/3/new", {buildid:3, "res": "SUCCESS"})
            $httpBackend.flush()
            expect($scope.builds[0].steps).toBeDefined()
            expect($scope.builds[1].steps).toBeDefined()

        it 'has a bindHierarchy helper to bind a hierarchy', ->
            $httpBackend.expectDataGET('builds/1')
            $httpBackend.expectDataGET('builds/1/steps/2')
            p = buildbotService.bindHierarchy($scope, {build: 1, step: 2}, ["builds", "steps"])
            res = null
            p.then (r) -> res = r
            $httpBackend.flush()
            # following triggers a $q callback resolving
            $rootScope.$digest()
            expect($scope.build).toBeDefined()
            expect($scope.step).toBeDefined()
            expect([$scope.build, $scope.step]).toEqual(res)

        it 'should return the same object for several subsequent
                calls to all(), one() and some()', ->
            r = buildbotService.all("build")
            r2 = buildbotService.all("build")
            expect(r).toBe(r2)
            r = buildbotService.one("build",1)
            r2 = buildbotService.one("build",1)
            r3 = buildbotService.one("build",2)
            expect(r).toBe(r2)
            expect(r).not.toBe(r3)
            r = buildbotService.one("builder",1).all("build")
            r2 = buildbotService.one("builder",1).all("build")
            expect(r).toBe(r2)
            r = buildbotService.one("builder",1).one("build",1)
            r2 = buildbotService.one("builder",1).one("build",1)
            expect(r).toBe(r2)
            r = buildbotService.one("builder",1).some("build", {limit:20})
            r2 = buildbotService.one("builder",1).some("build", {limit:20})
            expect(r).toBe(r2)

        it 'should use one request for one endpoint, take advantage of
                events to maintain synchronisation', ->
            $httpBackend.expectDataGET('builds')
            r = buildbotService.all("builds")
            builds1 = []
            r2 = buildbotService.all("builds")
            $scope2 = $rootScope.$new()
            builds2 = []
            r.bind $scope,
                onchild: (build) ->
                    builds1.push(build)
            r2.bind $scope2,
                onchild: (build) ->
                    builds2.push(build)
            $httpBackend.flush()
            $rootScope.$digest()
            mqService.broadcast("builds/3/new", {buildid:3, "res": "SUCCESS"})
            mqService.broadcast("builds/4/new", {buildid:4, "res": "SUCCESS"})
            mqService.broadcast("builds/5/new", {buildid:5, "res": "SUCCESS"})
            $rootScope.$digest()
            # ensure we reuse the same data between the two scopes
            expect($scope.builds).toBe($scope2.builds)

            # ensure the onchild callbacks were called the same
            expect(builds1).not.toBe(builds2)
            expect(builds1[0]).toBe(builds2[0])
            expect(builds1).toEqual(builds2)

            # destroy one scope
            $scope.$destroy()
            $timeout.flush()
            mqService.broadcast("builds/6/new", {buildid:6, "res": "SUCCESS"})
            $rootScope.$digest()
            expect(builds1.length + 1).toEqual(builds2.length)

            # destroy other scope, this should unregister after timeout
            $scope2.$destroy()
            $timeout.flush()
            expect ->
                mqService.broadcast("builds/7/new", {buildid:7, "res": "SUCCESS"})
            .toThrow()

        it 'should reload the data in case of loss of synchronisation', ->
            $httpBackend.expectDataGET 'builds',
                nItems:1
            r = buildbotService.all("builds")
            r.bind($scope)
            $httpBackend.flush()
            $rootScope.$digest()
            mqService.broadcast("builds/3/new", {buildid:3, "res": "SUCCESS"})
            $rootScope.$digest()
            expect($scope.builds.length).toBe(2)
            $httpBackend.expectDataGET 'builds',
                nItems:2
            $rootScope.$broadcast("lost-sync")
            $httpBackend.flush()
            $rootScope.$digest()
            expect($scope.builds.length).toBe(2)
            mqService.broadcast("builds/4/new", {buildid:4, "res": "SUCCESS"})
            $rootScope.$digest()
            expect($scope.builds.length).toBe(3)
