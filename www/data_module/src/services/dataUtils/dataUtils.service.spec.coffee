describe 'Helper service', ->
    beforeEach module 'bbData'

    dataUtilsService = null

    injected = ($injector) ->
        dataUtilsService = $injector.get('dataUtilsService')

    beforeEach(inject(injected))

    it 'should be defined', ->
        expect(dataUtilsService).toBeDefined()

    it 'should capitalize the first word', ->
        expect(dataUtilsService.capitalize('abc')).toBe('Abc')
        expect(dataUtilsService.capitalize('abc cba')).toBe('Abc cba')

    it 'should return the endpoint name for rest endpoints', ->
        tests =
            'builders/100/forceschedulers': 'forcescheduler'
            'builders/1/builds': 'build'
            'builders/2/builds/1': 'build'
        for k, v of tests
            expect(dataUtilsService.singularType(k)).toBe(v)

    it 'should return the class name for rest endpoints', ->
        tests =
            'builders/100/forceschedulers': 'Forcescheduler'
            'builders/1/builds': 'Build'
            'builders/2/builds/1': 'Build'
        for k, v of tests
            expect(dataUtilsService.className(k)).toBe(v)

    it 'should return the WebSocket path for an endpoint', ->
        tests =
            'builders/100/forceschedulers/*/*': ['builders', 100, 'forceschedulers']
            'builders/1/builds/*/*': ['builders', 1, 'builds']
            'builders/2/builds/1/*': ['builders', 2, 'builds', 1]
        for k, v of tests
            expect(dataUtilsService.socketPath(v)).toBe(k)

    it 'should return the path for an endpoint', ->
        tests =
            'builders/100/forceschedulers': ['builders', 100, 'forceschedulers']
            'builders/1/builds': ['builders', 1, 'builds']
            # removes the identifier
            'builders/2/builds': ['builders', 2, 'builds', 1]
        for k, v of tests
            expect(dataUtilsService.endpointPath(v)).toBe(k)
