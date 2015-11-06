describe 'Data service', ->
    beforeEach module 'bbData'

    dataService = restService = socketService = ENDPOINTS = $rootScope = $q = $httpBackend = null
    injected = ($injector) ->
        dataService = $injector.get('dataService')
        restService = $injector.get('restService')
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
        it 'should return a promise', ->
            p = dataService.getBuilds()
            expect(angular.isFunction(p.then)).toBeTruthy()
            expect(angular.isFunction(p.getArray)).toBeTruthy()

        it 'should call get for the rest api endpoint', ->
            d = $q.defer()
            spyOn(restService, 'get').and.returnValue(d.promise)
            expect(restService.get).not.toHaveBeenCalled()
            $rootScope.$apply ->
                dataService.get('asd', subscribe: false)
            # the query should not contain the subscribe field
            expect(restService.get).toHaveBeenCalledWith('asd', {})

        it 'should send startConsuming with the socket path', ->
            d = $q.defer()
            spyOn(socketService, 'send').and.returnValue(d.promise)
            expect(socketService.send).not.toHaveBeenCalled()
            $rootScope.$apply ->
                dataService.get('asd')
            expect(socketService.send).toHaveBeenCalledWith
                cmd: 'startConsuming'
                path: 'asd/*/*'
            $rootScope.$apply ->
                dataService.get('asd', 1)
            expect(socketService.send).toHaveBeenCalledWith
                cmd: 'startConsuming'
                path: 'asd/1/*'

        it 'should not call startConsuming when {subscribe: false} is passed in', ->
            d = $q.defer()
            spyOn(restService, 'get').and.returnValue(d.promise)
            spyOn(dataService, 'startConsuming')
            expect(dataService.startConsuming).not.toHaveBeenCalled()
            $rootScope.$apply ->
                dataService.getBuilds(subscribe: false)
            expect(dataService.startConsuming).not.toHaveBeenCalled()

        it 'should add the new instance on /new WebSocket message', ->
            spyOn(restService, 'get').and.returnValue($q.resolve(builds: []))
            builds = null
            $rootScope.$apply ->
                builds = dataService.getBuilds(subscribe: false).getArray()
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
            dataService.control(method, params)
            expect(restService.post).toHaveBeenCalledWith
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

        it 'should call unsubscribe on each root class on close', ->
            p = $q.resolve(builds: [{}, {}, {}])
            spyOn(restService, 'get').and.returnValue(p)
            builds = null
            $rootScope.$apply ->
                builds = opened.getBuilds(subscribe: false).getArray()
            expect(builds.length).toBe(3)
            spyOn(b, 'unsubscribe') for b in builds
            expect(b.unsubscribe).not.toHaveBeenCalled() for b in builds
            opened.close()
            expect(b.unsubscribe).toHaveBeenCalled() for b in builds

        it 'should call close when the $scope is destroyed', ->
            spyOn(opened, 'close')
            scope = $rootScope.$new()
            opened.closeOnDestroy(scope)
            expect(opened.close).not.toHaveBeenCalled()
            scope.$destroy()
            expect(opened.close).toHaveBeenCalled()

        # TODO ...
