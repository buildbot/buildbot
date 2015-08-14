describe 'Data utils service', ->
    beforeEach module 'bbData'

    dataUtilsService = undefined
    injected = ($injector) ->
        dataUtilsService = $injector.get('dataUtilsService')

    beforeEach(inject(injected))

    it 'should be defined', ->
        expect(dataUtilsService).toBeDefined()

    describe 'capitalize(string)', ->

        it 'should capitalize the parameter string', ->
            result = dataUtilsService.capitalize('test')
            expect(result).toBe('Test')

            result = dataUtilsService.capitalize('t')
            expect(result).toBe('T')

    describe 'type(arg)', ->

        it 'should return the type of the parameter endpoint', ->
            result = dataUtilsService.type('asd/1')
            expect(result).toBe('asd')

            result = dataUtilsService.type('asd/1/bnm')
            expect(result).toBe('bnm')

    describe 'singularType(arg)', ->

        it 'should return the singular the type name of the parameter endpoint', ->
            result = dataUtilsService.singularType('tests/1')
            expect(result).toBe('test')

            result = dataUtilsService.singularType('tests')
            expect(result).toBe('test')

    describe 'socketPath(arg)', ->

        it 'should return the WebSocket subscribe path of the parameter path', ->
            result = dataUtilsService.socketPath('asd/1/bnm')
            expect(result).toBe('asd/1/bnm/*/*')

            result = dataUtilsService.socketPath('asd/1')
            expect(result).toBe('asd/1/*')

    describe 'restPath(arg)', ->

        it 'should return the rest path of the parameter WebSocket subscribe path', ->
            result = dataUtilsService.restPath('asd/1/bnm/*/*')
            expect(result).toBe('asd/1/bnm')

            result = dataUtilsService.restPath('asd/1/*')
            expect(result).toBe('asd/1')

    describe 'endpointPath(arg)', ->

        it 'should return the endpoint path of the parameter rest or WebSocket path', ->
            result = dataUtilsService.endpointPath('asd/1/bnm/*/*')
            expect(result).toBe('asd/1/bnm')

            result = dataUtilsService.endpointPath('asd/1/*')
            expect(result).toBe('asd')

    describe 'copyOrSplit(arrayOrString)', ->

        it 'should copy an array', ->
            array = [1, 2, 3]
            result = dataUtilsService.copyOrSplit(array)
            expect(result).not.toBe(array)
            expect(result).toEqual(array)

        it 'should split a string', ->
            string = 'asd/123/bnm'
            result = dataUtilsService.copyOrSplit(string)
            expect(result).toEqual(['asd', '123', 'bnm'])

    describe 'unWrap(data, path)', ->

        it 'should return the array of the type based on the path', ->
            data =
                asd: [{'data'}]
                meta: {}
            result = dataUtilsService.unWrap(data, 'bnm/1/asd')
            expect(result).toBe(data.asd)

            result = dataUtilsService.unWrap(data, 'bnm/1/asd/2')
            expect(result).toBe(data.asd)
