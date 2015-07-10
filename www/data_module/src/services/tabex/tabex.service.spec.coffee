describe 'Tabex service', ->
    beforeEach module 'bbData'

    class ClientMock
        channels: {}
        CHANNELS =
            MASTER: '!sys.master'
            REFRESH: '!sys.channels.refresh'

        callMasterHandler: (isMaster) ->
            data = master_id: 1, node_id: if isMaster then 1 else 2
            @emit CHANNELS.MASTER, data, true

        on: (c, l) ->
            @channels[c] ?= []
            @channels[c].push(l)
            @emit CHANNELS.REFRESH, {channels: Object.keys(@channels)}, true

        off: (c, l) ->
            if angular.isArray(@channels[c])
                idx = @channels[c].indexOf(l)
                if idx > -1 then @channels[c].split(idx, 1)

        emit: (c, m, self = false) ->
            if angular.isArray(@channels[c]) and self
                for l in @channels[c]
                    if angular.isFunction(l) then l(m)

    tabexService = socketService = indexedDBService = restService = undefined
    $window = $q = $rootScope = $timeout = undefined
    clientMock = new ClientMock()
    injected = ($injector) ->
        $window = $injector.get('$window')
        $q = $injector.get('$q')
        $rootScope = $injector.get('$rootScope')
        $timeout = $injector.get('$timeout')

        spyOn($window.tabex, 'client').and.returnValue(clientMock)

        tabexService = $injector.get('tabexService')
        socketService = $injector.get('socketService')
        indexedDBService = $injector.get('indexedDBService')
        restService = $injector.get('restService')

    beforeEach(inject(injected))

    afterEach -> clientMock.channels = {}

    it 'should be defined', ->
        expect(tabexService).toBeDefined()

    it 'should have event constants', ->
        expect(tabexService.EVENTS).toBeDefined()
        expect(tabexService.EVENTS.READY).toBeDefined()
        expect(tabexService.EVENTS.UPDATE).toBeDefined()
        expect(tabexService.EVENTS.NEW).toBeDefined()

    it 'should handle the socketService.onMessage event', ->
        expect(angular.isFunction(socketService.onMessage)).toBeTruthy()
        expect(socketService.onMessage).toBe(tabexService.messageHandler)

    it 'should handle the socketService.onClose event', ->
        expect(angular.isFunction(socketService.onClose)).toBeTruthy()
        expect(socketService.onClose).toBe(tabexService.closeHandler)

    it 'should call the activatePaths function before unload', ->
        spyOn(tabexService, 'activatePaths')
        expect(tabexService.activatePaths).not.toHaveBeenCalled()
        $window.onbeforeunload()
        expect(tabexService.activatePaths).toHaveBeenCalled()

    describe 'masterHandler(data)', ->

        it 'should handle the tabex master event', ->
            # TODO the original function is registered, not the spied one
            spyOn(tabexService, 'masterHandler')
            expect(tabexService.masterHandler).not.toHaveBeenCalled()

            clientMock.callMasterHandler()
            # expect(tabexService.masterHandler).toHaveBeenCalled()

        it 'should resolve the initialRoleDeferred', ->
            roleIsResolved = jasmine.createSpy('roleIsResolved')
            tabexService.initialRole.then -> roleIsResolved()

            expect(roleIsResolved).not.toHaveBeenCalled()
            $rootScope.$apply -> clientMock.callMasterHandler()
            expect(roleIsResolved).toHaveBeenCalled()

        it 'should assign the role on master event (slave)', ->
            expect(tabexService.role).toBeUndefined()
            clientMock.callMasterHandler()
            expect(tabexService.role).toBeDefined()
            expect(tabexService.role).toBe(tabexService._ROLES.SLAVE)

        it 'should assign the role on master event (slave)', ->
            expect(tabexService.role).toBeUndefined()
            clientMock.callMasterHandler(true)
            expect(tabexService.role).toBeDefined()
            expect(tabexService.role).toBe(tabexService._ROLES.MASTER)

    describe 'refreshHandler(data)', ->

        it 'should handle the tabex refresh event', ->
            # TODO the original function is registered, not the spied one
            spyOn(tabexService, 'refreshHandler')
            expect(tabexService.refreshHandler).not.toHaveBeenCalled()

            tabexService.client.on 'channel1', ->
            # expect(tabexService.refreshHandler).toHaveBeenCalled()

        it 'should call the master refresh handler if the role is master', ->
            spyOn(tabexService, 'masterRefreshHandler')
            expect(tabexService.masterRefreshHandler).not.toHaveBeenCalled()
            tabexService.client.on 'channel1', ->
            expect(tabexService.masterRefreshHandler).not.toHaveBeenCalled()
            $rootScope.$apply -> clientMock.callMasterHandler(true)
            expect(tabexService.masterRefreshHandler).toHaveBeenCalled()

        it 'should only call the master refresh handler once (debounce)', ->
            spyOn(tabexService, 'masterRefreshHandler')
            $rootScope.$apply -> clientMock.callMasterHandler(true)
            tabexService.client.on 'channel1', ->
            tabexService.client.on 'channel2', ->
            tabexService.client.on 'channel3', ->
            expect(tabexService.masterRefreshHandler.calls.count()).toBe(1)

        it 'should send startConsuming messages', ->
            spyOn(socketService, 'send')
            spyOn(tabexService, 'activatePaths').and.returnValue($q.resolve())
            tabexService.debounceTimeout = 0
            expect(socketService.send).not.toHaveBeenCalled()
            $rootScope.$apply -> clientMock.callMasterHandler(true)
            tabexService.on 'path1/*/*', {subscribe: true}, ->
            tabexService.on 'path1/1/*', {subscribe: true}, ->
            tabexService.on 'path2/*/*', {subscribe: true}, ->
            $timeout.flush()
            expect(socketService.send).toHaveBeenCalledWith(cmd: 'startConsuming', path: 'path1/*/*')
            expect(socketService.send).toHaveBeenCalledWith(cmd: 'startConsuming', path: 'path2/*/*')
            expect(socketService.send).not.toHaveBeenCalledWith(cmd: 'startConsuming', path: 'path1/1/*')

        # TODO
        it 'should add the path to trackedPath', ->

        it 'should call the loadAll function', ->
            spyOn(tabexService, 'loadAll')
            spyOn(tabexService, 'activatePaths').and.returnValue($q.resolve())
            spyOn(tabexService, 'startConsumingAll').and.returnValue($q.resolve())
            tabexService.debounceTimeout = 0
            expect(tabexService.loadAll).not.toHaveBeenCalled()
            $rootScope.$apply -> clientMock.callMasterHandler(true)
            $timeout.flush()
            expect(tabexService.loadAll).toHaveBeenCalled()

        it 'should add queries to the trackedPath', ->


    # TODO ->
    describe 'messageHandler(key, message)', ->

        it 'should update the object in the indexedDB', ->
            indexedDBService.db = 'bsd': put: ->
            spyOn(indexedDBService.db['bsd'], 'put').and.returnValue($q.resolve())
            expect(indexedDBService.db['bsd'].put).not.toHaveBeenCalled()
            message = bsd: 1
            socketService.onMessage('asd/1/bsd/2/new', message)
            expect(indexedDBService.db['bsd'].put).toHaveBeenCalledWith(message)

        it 'should emit update events for matching paths', ->
            indexedDBService.db =
                asd: put: -> $q.resolve()
                bsd: put: -> $q.resolve()

            spyOn(tabexService, 'activatePaths').and.returnValue($q.resolve())
            spyOn(tabexService, 'startConsumingAll').and.returnValue($q.resolve())
            spyOn(tabexService, 'loadAll').and.callFake ->
            tabexService.debounceTimeout = 0
            $rootScope.$apply -> clientMock.callMasterHandler(true)

            tabexService.on 'asd/*/*', {subscribe: true}, ->
            tabexService.on 'asd/1/*', {subscribe: true}, ->
            tabexService.on 'bsd/*/*', {subscribe: true}, ->

            $timeout.flush()

            spyOn(tabexService, 'emit')
            expect(tabexService.emit).not.toHaveBeenCalled()
            $rootScope.$apply -> tabexService.messageHandler('asd/1/completed', {})
            expect(tabexService.emit).toHaveBeenCalledWith('asd/*/*', {}, tabexService.EVENTS.UPDATE)
            expect(tabexService.emit).toHaveBeenCalledWith('asd/1/*', {}, tabexService.EVENTS.UPDATE)

            expect(tabexService.emit).not.toHaveBeenCalledWith('bsd/*/*', {}, tabexService.EVENTS.UPDATE)
            $rootScope.$apply -> tabexService.messageHandler('bsd/2/new', {})
            expect(tabexService.emit).toHaveBeenCalledWith('bsd/*/*', {}, tabexService.EVENTS.NEW)

    describe 'closeHandler()', ->

        it 'should send the startConsuming messages', ->
            spyOn(tabexService, 'startConsuming')
            clientMock.callMasterHandler(true)
            tabexService.trackedPaths = {'path/*/*': [{}]}

            expect(tabexService.startConsuming).not.toHaveBeenCalled()
            socketService.socket.onclose()
            expect(tabexService.startConsuming).toHaveBeenCalledWith('path/*/*')

    describe 'loadAll()', ->

        it 'should load all untracked paths', ->
            spyOn(indexedDBService.db.paths, 'toArray').and.returnValue($q.resolve([]))
            spyOn(tabexService, 'load')

            paths =
                'asd/*/*': [{bsd: 1}, {}]
            tabexService.loadAll(paths)

            $rootScope.$apply()
            for p, qs of paths
                for q in qs
                    expect(tabexService.load).toHaveBeenCalledWith(p, q, [])

    describe 'load(path, query, dbPaths)', ->

        it 'should load not cached data', ->
            spyOn(tabexService, 'emit')
            spyOn(restService, 'get').and.returnValue($q.resolve(asd: {}))
            spyOn(tabexService, 'getSpecification').and.returnValue(static: false)
            spyOn(indexedDBService.db, 'transaction').and.returnValue($q.resolve())

            path = 'asd/*/*'
            query = {}
            tabexService.load(path, query)
            expect(tabexService.emit).not.toHaveBeenCalled()
            $rootScope.$apply()
            expect(tabexService.emit).toHaveBeenCalledWith(path, query, tabexService.EVENTS.READY)

        it 'should not load cached data', ->
            spyOn(tabexService, 'emit')
            expect(tabexService.emit).not.toHaveBeenCalled()
            spyOn(tabexService, 'getSpecification').and.returnValue(static: false)

            path = ''
            query = {}
            now = new Date()
            tabexService.load path, query, [
                path: path
                query: angular.toJson(query)
                lastActive: now
            ]
            $rootScope.$apply()
            expect(tabexService.emit).toHaveBeenCalledWith(path, query, tabexService.EVENTS.READY)

        it 'should not load cached data', ->
            spyOn(tabexService, 'emit')
            expect(tabexService.emit).not.toHaveBeenCalled()
            spyOn(tabexService, 'getSpecification').and.returnValue(static: true)

            path = ''
            query = {}
            now = new Date()
            tabexService.load path, query, [
                path: path
                query: angular.toJson(query)
                lastActive: new Date(0)
            ]
            $rootScope.$apply()
            expect(tabexService.emit).toHaveBeenCalledWith(path, query, tabexService.EVENTS.READY)

    describe 'startConsumingAll(paths)', ->

        it 'should call startConsuming for all not tracked paths', ->
            spyOn(tabexService, 'startConsuming').and.returnValue($q.resolve())
            tabexService.trackedPaths =
                'asd': [{}]

            ready = jasmine.createSpy('ready')
            expect(tabexService.startConsuming).not.toHaveBeenCalled()
            tabexService.startConsumingAll(['bsd', 'asd']).then(ready)
            tabexService.startConsumingAll({csd: [{}]})
            expect(tabexService.startConsuming).toHaveBeenCalledWith('bsd')
            expect(tabexService.startConsuming).toHaveBeenCalledWith('csd')
            expect(tabexService.startConsuming).not.toHaveBeenCalledWith('asd')
            expect(ready).not.toHaveBeenCalled()
            $rootScope.$apply()
            expect(ready).toHaveBeenCalled()
