describe 'Data service', ->
    _dataServiceProvider = null
    beforeEach module 'bbData', (dataServiceProvider, $provide) ->
        _dataServiceProvider = dataServiceProvider
        $provide.constant 'SPECIFICATION',
            asd: root: true
            bsd: root: false

        $provide.constant '$state', new class State
            reload: jasmine.createSpy('reload')

    dataService = $q = $rootScope = $state = restService = indexedDBService = Collection = undefined
    injected = ($injector) ->
        $q = $injector.get('$q')
        $rootScope = $injector.get('$rootScope')
        $state = $injector.get('$state')
        indexedDBService = $injector.get('indexedDBService')
        restService = $injector.get('restService')
        dataService = $injector.invoke(_dataServiceProvider.$get)

    beforeEach(inject(injected))

    it 'should be defined', ->
        expect(dataService).toBeDefined()

    it '`s cache should be true', ->
        expect(dataService.cache).toBeTruthy()

    it 'should generate functions for every root in the specification', ->
        expect(dataService.getAsd).toBeDefined()
        expect(angular.isFunction(dataService.getAsd)).toBeTruthy()

        expect(dataService.getBsd).not.toBeDefined()
        expect(angular.isFunction(dataService.getBsd)).toBeFalsy()

        spyOn(dataService, 'get')
        dataService.getAsd(1)
        expect(dataService.get).toHaveBeenCalledWith('asd', 1)

    describe 'clearCache()', ->

        it 'should clear the database, then reload the page', ->
            spyOn(indexedDBService, 'clear').and.returnValue($q.resolve())
            expect(indexedDBService.clear).not.toHaveBeenCalled()
            dataService.clearCache()
            expect(indexedDBService.clear).toHaveBeenCalled()

            expect($state.reload).not.toHaveBeenCalled()
            $rootScope.$apply()
            expect($state.reload).toHaveBeenCalled()

    describe 'get(args)', ->

        it 'should create a new Collection and return a promise', ->
            original = dataService.createCollection
            c = null
            spyOn(dataService, 'createCollection').and.callFake (args...) ->
                c = original(args...)
                spyOn(c, 'subscribe').and.returnValue($q.resolve(c))
                return c
            cb = jasmine.createSpy('callback')
            expect(dataService.createCollection).not.toHaveBeenCalled()
            dataService.get('asd').then(cb)
            expect(dataService.createCollection).toHaveBeenCalledWith('asd', subscribe: false)

            expect(cb).not.toHaveBeenCalled()
            $rootScope.$apply()
            expect(cb).toHaveBeenCalledWith(c)

    describe 'processArguments(args)', ->

        it 'should return the restPath and the query (empty query)', ->
            [restPath, query] = dataService.processArguments(['asd', '1'])
            expect(restPath).toBe('asd/1')
            expect(query).toEqual({})

        it 'should return the restPath and the query (not empty query)', ->
            [restPath, query] = dataService.processArguments(['asd', '1', parameter: 1])
            expect(restPath).toBe('asd/1')
            expect(query).toEqual(parameter: 1)

    describe 'control(url, method, params)', ->

        it 'should make a POST call', ->
            spyOn(restService, 'post').and.returnValue($q.resolve())
            cb = jasmine.createSpy('cb')
            expect(restService.post).not.toHaveBeenCalled()

            url = 'forceschedulers/force'
            method = 'force'
            params = parameter: 1

            dataService.control(url, method, params).then(cb)

            expect(restService.post).toHaveBeenCalledWith url,
                id: jasmine.any(Number)
                jsonrpc: '2.0'
                method: method
                params: params

            expect(cb).not.toHaveBeenCalled()
            $rootScope.$apply()
            expect(cb).toHaveBeenCalled()

        it 'should change the id on each call', ->
            spyOn(restService, 'post')

            url = 'forceschedulers/force'
            method = 'force'

            dataService.control(url, method)
            dataService.control(url, method)

            id1 = restService.post.calls.argsFor(0)[1].id
            id2 = restService.post.calls.argsFor(1)[1].id

            expect(id1).not.toEqual(id2)

        describe 'open(scope)', ->

            it 'should return a class with close, closeOnDestroy and getXXX functions', ->
                scope = $rootScope.$new()
                dataAccessor = dataService.open(scope)
                expect(angular.isFunction(dataAccessor.close)).toBeTruthy()
                expect(angular.isFunction(dataAccessor.closeOnDestroy)).toBeTruthy()

            it 'should generate functions for every root in the specification', ->
                dataAccessor = dataService.open()
                expect(dataAccessor.getAsd).toBeDefined()
                expect(angular.isFunction(dataAccessor.getAsd)).toBeTruthy()

                expect(dataAccessor.getBsd).not.toBeDefined()
                expect(angular.isFunction(dataAccessor.getBsd)).toBeFalsy()

                spyOn(dataService, 'get').and.callThrough()
                dataAccessor.getAsd(1)
                dataAccessor.getAsd(2, param: 3)
                dataAccessor.getAsd(4, subscribe: false)
                expect(dataService.get).toHaveBeenCalledWith('asd', 1, subscribe: true)
                expect(dataService.get).toHaveBeenCalledWith('asd', 2, param: 3, subscribe: true)
                expect(dataService.get).toHaveBeenCalledWith('asd', 4, subscribe: false)

            it 'should unsubscribe on destroy event', ->
                scope = $rootScope.$new()
                spyOn(scope, '$on').and.callThrough()

                dataAccessor = dataService.open(scope)
                expect(scope.$on).toHaveBeenCalledWith('$destroy', jasmine.any(Function))

                spyOn(dataAccessor, 'close').and.callThrough()
                expect(dataAccessor.close).not.toHaveBeenCalled()
                scope.$destroy()
                expect(dataAccessor.close).toHaveBeenCalled()

            it 'should call unsubscribe on each element', ->
                dataAccessor = dataService.open()
                el1 = unsubscribe: jasmine.createSpy('unsubscribe1')
                el2 = unsubscribe: jasmine.createSpy('unsubscribe2')
                el3 = {}

                dataAccessor.collections.push(el1)
                dataAccessor.collections.push(el2)
                dataAccessor.collections.push(el3)

                expect(el1.unsubscribe).not.toHaveBeenCalled()
                expect(el2.unsubscribe).not.toHaveBeenCalled()
                dataAccessor.close()
                expect(el1.unsubscribe).toHaveBeenCalled()
                expect(el2.unsubscribe).toHaveBeenCalled()
