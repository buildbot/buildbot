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

    describe 'socketPathRE(arg)', ->

        it 'should return the WebSocket subscribe path of the parameter path', ->
            result = dataUtilsService.socketPathRE('asd/1/*')
            expect(result.test("asd/1/new")).toBeTruthy()

            result = dataUtilsService.socketPathRE('asd/1/bnm/*/*').source
            expect(result).toBe('^asd\\/1\\/bnm\\/[^\\/]+\\/[^\\/]+$')

            result = dataUtilsService.socketPathRE('asd/1/*').source
            expect(result).toBe('^asd\\/1\\/[^\\/]+$')


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

    describe 'parse(object)', ->

        it 'should parse fields from JSON', ->
            test =
                a: 1
                b: 'asd3'
                c: angular.toJson(['a', 1, 2])
                d: angular.toJson({asd: [], bsd: {}})

            copy = angular.copy(test)
            copy.c = angular.toJson(copy.c)
            copy.d = angular.toJson(copy.d)

            parsed = dataUtilsService.parse(test)

            expect(parsed).toEqual(test)

    describe 'numberOrString(string)', ->

        it 'should convert a string to a number if possible', ->
            result = dataUtilsService.numberOrString('12')
            expect(result).toBe(12)

        it 'should return the string if it is not a number', ->
            result = dataUtilsService.numberOrString('w3as')
            expect(result).toBe('w3as')

    describe 'emailInString(string)', ->

        it 'should return an email from a string', ->
            email = dataUtilsService.emailInString('foo <bar@foo.com>')
            expect(email).toBe('bar@foo.com')
            email = dataUtilsService.emailInString('bar@foo.com')
            expect(email).toBe('bar@foo.com')
