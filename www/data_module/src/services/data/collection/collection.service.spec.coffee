describe 'Collection', ->
    beforeEach module 'bbData'

    Collection = $q = $rootScope = tabexService = indexedDBService = c = undefined
    injected = ($injector) ->
        $q = $injector.get('$q')
        $rootScope = $injector.get('$rootScope')
        Collection = $injector.get('Collection')

        c = new Collection('builds')

    beforeEach(inject(injected))

    it 'should be defined', ->
        expect(Collection).toBeDefined()
        expect(c).toBeDefined()

    it 'should have a put function, which does not add twice for the same id', ->
        c.put(buildid: 1)
        expect(c.length).toEqual(1)
        c.put(buildid: 1)
        expect(c.length).toEqual(1)
        c.put(buildid: 2)
        expect(c.length).toEqual(2)

    it 'should have a from function, which iteratively inserts data', ->
        c.from [
            buildid: 1
        ,
            buildid: 2
        ,
            buildid: 2
        ]
        expect(c.length).toEqual(2)
