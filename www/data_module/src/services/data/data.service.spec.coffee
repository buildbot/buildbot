describe 'Data service', ->
    beforeEach module 'bbData'

    dataService = restService = socketService = ENDPOINTS = $rootScope = $q = $httpBackend = $timeout = null
    injected = ($injector) ->
        dataService = $injector.get('dataService')
        restService = $injector.get('restService')
        $timeout = $injector.get('$timeout')
        socketService = $injector.get('socketService')
        ENDPOINTS = $injector.get('ENDPOINTS')
        $rootScope = $injector.get('$rootScope')
        $q = $injector.get('$q')
        $httpBackend = $injector.get('$httpBackend')

    beforeEach(inject(injected))

    it 'should be defined', ->
        expect(dataService).toBeDefined()

    it 'should have getXxx functions for endpoints', ->
        for e in ENDPOINTS
            E = e[0].toUpperCase() + e[1..-1].toLowerCase()
            expect(dataService["get#{E}"]).toBeDefined()
            expect(angular.isFunction(dataService["get#{E}"])).toBeTruthy()

    describe 'get()', ->
        it 'should return a collection', ->
            ret = dataService.getBuilds()
            expect(ret.length).toBeDefined()

        it 'should call get for the rest api endpoint', ->
            d = $q.defer()
            spyOn(restService, 'get').and.returnValue(d.promise)
            expect(restService.get).not.toHaveBeenCalled()
            $rootScope.$apply ->
                dataService.get('asd', subscribe: false)
            # the query should not contain the subscribe field
            expect(restService.get).toHaveBeenCalledWith('asd', {})

        it 'should send startConsuming with the socket path', ->
            data = dataService.open()
            p = $q.resolve([])
            spyOn(socketService, 'send').and.returnValue(p)
            spyOn(restService, 'get').and.returnValue(p)
            expect(socketService.send).not.toHaveBeenCalled()
            $rootScope.$apply ->
                data.getBuilds()
            expect(socketService.send).toHaveBeenCalledWith
                cmd: 'startConsuming'
                path: 'builds/*/*'
            socketService.send.calls.reset()

            $rootScope.$apply ->
                data.getBuilds(1)
            expect(socketService.send).toHaveBeenCalledWith
                cmd: 'startConsuming'
                path: 'builds/1/*'
            # get same build again, it should not register again
            socketService.send.calls.reset()
            $rootScope.$apply ->
                data.getBuilds(1)
            expect(socketService.send).not.toHaveBeenCalled()

            # now we close the accessor, and we should send stopConsuming
            $rootScope.$apply ->
                data.close()
            expect(socketService.send).toHaveBeenCalledWith
                cmd: 'stopConsuming'
                path: 'builds/*/*'
            expect(socketService.send).toHaveBeenCalledWith
                cmd: 'stopConsuming'
                path: 'builds/1/*'


        it 'should not call startConsuming when {subscribe: false} is passed in', ->
            d = $q.defer()
            spyOn(restService, 'get').and.returnValue(d.promise)
            spyOn(socketService, 'send').and.returnValue(d.promise)
            expect(socketService.send).not.toHaveBeenCalled()
            $rootScope.$apply ->
                dataService.getBuilds(subscribe: false)
            expect(socketService.send).not.toHaveBeenCalled()

        it 'should add the new instance on /new WebSocket message', ->
            spyOn(restService, 'get').and.returnValue($q.resolve(builds: []))
            builds = null
            $rootScope.$apply ->
                builds = dataService.getBuilds(subscribe: false)
            socketService.eventStream.push
                k: 'builds/111/new'
                m: asd: 111
            expect(builds.pop().asd).toBe(111)

    describe 'control(method, params)', ->

        it 'should send a jsonrpc message using POST', ->
            spyOn(restService, 'post')
            expect(restService.post).not.toHaveBeenCalled()
            method = 'force'
            params = a: 1
            dataService.control("a", 1, method, params)
            expect(restService.post).toHaveBeenCalledWith "a/1",
                id: 1
                jsonrpc: '2.0'
                method: method
                params: params

    describe 'open()', ->

        opened = null
        beforeEach ->
            opened = dataService.open()

        it 'should return a new accessor', ->
            expect(opened).toEqual(jasmine.any(Object))

        it 'should have getXxx functions for endpoints', ->
            for e in ENDPOINTS
                E = e[0].toUpperCase() + e[1..-1].toLowerCase()
                expect(opened["get#{E}"]).toBeDefined()
                expect(angular.isFunction(opened["get#{E}"])).toBeTruthy()

        it 'should call unsubscribe on each subscribed collection on close', ->
            p = $q.resolve(builds: [{buildid:1}, {buildid:2}, {buildid:3}])
            spyOn(restService, 'get').and.returnValue(p)
            builds = null
            $rootScope.$apply ->
                builds = opened.getBuilds(subscribe: false)
            expect(builds.length).toBe(3)
            spyOn(builds, 'close')
            opened.close()
            expect(builds.close).toHaveBeenCalled()

        it 'should call close when the $scope is destroyed', ->
            spyOn(opened, 'close')
            scope = $rootScope.$new()
            opened.closeOnDestroy(scope)
            expect(opened.close).not.toHaveBeenCalled()
            scope.$destroy()
            expect(opened.close).toHaveBeenCalled()

        it 'should work with mock calls as well', ->
            dataService.when('builds/1', [{buildid: 1, builderid: 1}])
            builds = opened.getBuilds(1, subscribe: false)

    describe 'when()', ->
        it 'should autopopulate ids', (done) ->
            dataService.when('builds', [{}, {}, {}])
            dataService.getBuilds().onChange = (builds) ->
                expect(builds.length).toBe(3)
                expect(builds[1].buildid).toBe(2)
                expect(builds[2].buildid).toBe(3)
                done()
            $timeout.flush()
