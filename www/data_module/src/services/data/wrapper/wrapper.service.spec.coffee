describe 'Wrapper', ->
    beforeEach module 'bbData'
    beforeEach module ($provide) ->
        $provide.constant 'SPECIFICATION',
            a:
                id: 'aid'
                identifier: 'aidentifier'
                paths: [
                    'b'
                    'b/n:bid'
                ]

    Wrapper = $q = $rootScope = tabexService = indexedDBService = dataService = data = i = undefined
    injected = ($injector) ->
        $q = $injector.get('$q')
        $rootScope = $injector.get('$rootScope')
        Wrapper = $injector.get('Wrapper')
        tabexService = $injector.get('tabexService')
        indexedDBService = $injector.get('indexedDBService')
        dataService = $injector.get('dataService')

        data =
            aid: 12
            aidentifier: 'n12'
        i = new Wrapper(data, 'a')

    beforeEach(inject(injected))

    it 'should be defined', ->
        expect(Wrapper).toBeDefined()
        expect(i).toBeDefined()

    it 'should add the data to the object passed in to the constructor', ->
        for k, v in data
            expect(i[k]).toEqual(v)

    it 'should generate functions for every type in the specification', ->
        expect(i.loadA).toBeDefined()
        expect(angular.isFunction(i.loadA)).toBeTruthy()

    describe 'get(args)', ->

        it 'should call dataService.get', ->
            spyOn(dataService, 'get')
            expect(dataService.get).not.toHaveBeenCalled()
            i.get('b')
            expect(dataService.get).toHaveBeenCalledWith('a', 12, 'b')

            i.get('b', {param: 1})
            expect(dataService.get).toHaveBeenCalledWith('a', 12, 'b', {param: 1})

            i.get('b', 11)
            expect(dataService.get).toHaveBeenCalledWith('a', 12, 'b', 11)

    describe 'getId()', ->

        it 'should return the id value', ->
            expect(i.getId()).toEqual(data.aid)

    describe 'getIdentifier()', ->

        it 'should return the identifier value', ->
            expect(i.getIdentifier()).toEqual(data.aidentifier)

    describe 'classId()', ->

        it 'should return the id name', ->
            expect(i.classId()).toEqual('aid')

    describe 'classIdentifier()', ->

        it 'should return the identifier name', ->
            expect(i.classIdentifier()).toEqual('aidentifier')

    describe 'unsubscribe()', ->

        it 'call unsubscribe on each object', ->
            i.obj = unsubscribe: jasmine.createSpy('unsubscribe')
            expect(i.obj.unsubscribe).not.toHaveBeenCalled()
            i.unsubscribe()
            expect(i.obj.unsubscribe).toHaveBeenCalled()
