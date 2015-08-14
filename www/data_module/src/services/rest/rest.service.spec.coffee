describe 'Rest service', ->
    beforeEach module 'bbData'
    beforeEach ->
        module ($provide) ->
            $provide.constant('API', '/api/')

    restService = $httpBackend = undefined
    injected = ($injector) ->
        restService = $injector.get('restService')
        $httpBackend = $injector.get('$httpBackend')

    beforeEach(inject(injected))

    afterEach ->
        $httpBackend.verifyNoOutstandingExpectation()
        $httpBackend.verifyNoOutstandingRequest()

    it 'should be defined', ->
        expect(restService).toBeDefined()

    it 'should make an ajax GET call to /api/endpoint', ->
        response = {a: 'A'}
        $httpBackend.whenGET('/api/endpoint').respond(response)

        gotResponse = null
        restService.get('endpoint').then (r) -> gotResponse = r
        expect(gotResponse).toBeNull()

        $httpBackend.flush()
        expect(gotResponse).toEqual(response)

    it 'should make an ajax GET call to /api/endpoint with parameters', ->
        params = {key: 'value'}
        $httpBackend.whenGET('/api/endpoint?key=value').respond(200)

        restService.get('endpoint', params)
        $httpBackend.flush()

    it 'should reject the promise on error', ->
        error = 'Internal server error'
        $httpBackend.expectGET('/api/endpoint').respond(500, error)

        gotResponse = null
        restService.get('endpoint').then (response) ->
            gotResponse = response
        , (reason) ->
            gotResponse = reason

        $httpBackend.flush()
        expect(gotResponse).toBe(error)

    it 'should make an ajax POST call to /api/endpoint', ->
        response = {}
        data = {b: 'B'}
        $httpBackend.expectPOST('/api/endpoint', data).respond(response)

        gotResponse = null
        restService.post('endpoint', data).then (r) -> gotResponse = r

        $httpBackend.flush()
        expect(gotResponse).toEqual(response)

    it 'should reject the promise when the response is not valid JSON', ->
        response = 'aaa'

        data = {b: 'B'}
        $httpBackend.expectPOST('/api/endpoint', data).respond(response)

        gotResponse = null
        restService.post('endpoint', data).then (response) ->
            gotResponse = response
        , (reason) ->
            gotResponse = reason

        $httpBackend.flush()
        expect(gotResponse).not.toBeNull()
        expect(gotResponse).not.toEqual(response)
