if window.__karma__?
    beforeEach module 'app'

    describe 'buildbot service', ->
        buildbotService = mqService = $scope = $httpBackend = $rootScope = null

        injected = ($injector) ->
            $httpBackend = $injector.get('$httpBackend')
            decorateHttpBackend($httpBackend)
            $rootScope = $injector.get('$rootScope')
            $scope = $rootScope.$new()
            mqService = $injector.get('mqService')
            # stub out the actual backend of mqservice
            spyOn(mqService,"setBaseUrl").andReturn(null)
            spyOn(mqService,"startConsuming").andReturn(null)
            spyOn(mqService,"stopConsuming").andReturn(null)
            buildbotService = $injector.get('buildbotService')

        beforeEach(inject(injected))

        it 'should query for changes at /changes and receive an empty array', ->
            $httpBackend.expectDataGET 'change',
                nItems:1
            buildbotService.all("change").bind($scope)
            $httpBackend.flush()
            expect($scope.changes.length).toBe(1)
        it 'should query for build/1/step/2 and receive a SUCCESS result', ->
            $httpBackend.expectDataGET 'build/1/step/2',
                override: (res) ->
                    res.steps[0].res = "SUCCESS"
            r = buildbotService.one("build", 1).one("step", 2)
            r.bind $scope,
                dest_key: "step_scope"
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

        it 'should update the $scope when event received', ->
            $httpBackend.expectGET('api/v2/build/1/step/2')
            .respond({steps:[{res: "PENDING", otherfield: "FOO"}]})
            r = buildbotService.one("build", 1).one("step", 2)
            r.bind $scope,
                ismutable: -> true
            $httpBackend.flush()
            expect($scope.step.res).toBe("PENDING")
            mqService.broadcast("build/1/step/2/update", {"res": "SUCCESS"})
            expect($scope.step.res).toBe("SUCCESS")
            # should not override other fields
            expect($scope.step.otherfield).toBe("FOO")

        it 'should update the $scope when event received for collections', ->
            $httpBackend.expectGET('api/v2/build/1/step')
            .respond({steps:[{stepid:1,res: "PENDING", otherfield: "FOO"}]})
            r = buildbotService.one("build", 1).all("step")
            childs = []
            r.bind $scope,
                ismutable: -> true
                onchild: (c) -> childs.push(c)
            $httpBackend.flush()
            expect($scope.steps.length).toBe(1)
            mqService.broadcast("build/1/step/3/new", {stepid:3, "res": "SUCCESS"})
            expect($scope.steps.length).toBe(2)
            expect(childs.length).toBe(2)
            for c in childs
                # make sure the objects sent to onchild are restangular objects
                expect(c.all).toBeDefined()
                expect(c.one).toBeDefined()
            expect($scope.steps[1].res).toBe("SUCCESS")

        it 'should update the $scope when event received for collections with same id', ->
            $httpBackend.expectGET('api/v2/build/1/step')
            .respond({steps:[{stepid:1, res: "PENDING", otherfield: "FOO"}]})
            r = buildbotService.one("build", 1).all("step")
            r.bind($scope)
            $httpBackend.flush()
            expect($scope.steps.length).toBe(1)
            mqService.broadcast("build/1/step/3/new", {stepid:3, "res": "SUCCESS"})
            mqService.broadcast("build/1/step/1/update", {stepid:1, res: "SUCCESS"})
            expect($scope.steps.length).toBe(2)
            expect($scope.steps[0].res).toBe("SUCCESS")
            expect($scope.steps[1].res).toBe("SUCCESS")

        it 'has a onchild api which should be usable for restangular api', ->
            $httpBackend.expectGET('api/v2/build')
            .respond({builds:[{buildid:1,res: "PENDING", otherfield: "FOO"}]})
            $httpBackend.expectDataGET('build/1/step')
            r = buildbotService.all("build")
            r.bind $scope,
                ismutable: -> true
                onchild: (step) ->
                    step.all("step").bind $scope,
                        dest: step

            $httpBackend.flush()
            $httpBackend.expectDataGET('build/3/step')
            mqService.broadcast("build/3/new", {buildid:3, "res": "SUCCESS"})
            $httpBackend.flush()
            expect($scope.builds[0].steps).toBeDefined()
            expect($scope.builds[1].steps).toBeDefined()

        it 'has a bindHierarchy helper to bind a hierarchy', ->
            $httpBackend.expectDataGET('build/1')
            $httpBackend.expectDataGET('build/1/step/2')
            p = buildbotService.bindHierarchy($scope, {build: 1, step: 2}, ["build", "step"])
            res = null
            p.then (r) -> res = r
            $httpBackend.flush()
            # following triggers a $q callback resolving
            $rootScope.$digest()
            expect($scope.build).toBeDefined()
            expect($scope.step).toBeDefined()
            expect([$scope.build, $scope.step]).toEqual(res)
