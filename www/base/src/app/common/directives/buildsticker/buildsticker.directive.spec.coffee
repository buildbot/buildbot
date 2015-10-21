beforeEach module 'app'

describe 'buildsticker controller', ->
    buildbotService = mqService = $httpBackend = $rootScope = $compile = results = null

    injected = ($injector) ->
        $compile = $injector.get('$compile')
        $httpBackend = $injector.get('$httpBackend')
        $location = $injector.get('$location')
        decorateHttpBackend($httpBackend)
        $rootScope = $injector.get('$rootScope')
        mqService = $injector.get('mqService')
        $controller = $injector.get('$controller')
        $q = $injector.get('$q')
        results = $injector.get('RESULTS')

        # stub out the actual backend of mqservice
        spyOn(mqService,"setBaseUrl").and.returnValue(null)
        spyOn(mqService,"startConsuming").and.returnValue($q.when( -> ))
        spyOn(mqService,"stopConsuming").and.returnValue(null)
        buildbotService = $injector.get('buildbotService')

    beforeEach(inject(injected))

    afterEach ->
        $httpBackend.verifyNoOutstandingExpectation()
        $httpBackend.verifyNoOutstandingRequest()

    it 'directive should generate correct html', ->
        $httpBackend.expectDataGET('builds/1')
        buildbotService.one('builds', 1).bind($rootScope)
        $httpBackend.flush()
        $httpBackend.expectDataGET('builders/1')
        element = $compile("<buildsticker build='build'></buildsticker>")($rootScope)
        $httpBackend.flush()
        $rootScope.$digest()

        build = $rootScope.build

        sticker = element.children().eq(0)

        row0 = sticker.children().eq(0)
        row1 = sticker.children().eq(1)

        resultSpan = row0.children().eq(0)
        buildLink = row0.children().eq(1)
        durationSpan = row1.children().eq(0)
        startedSpan = row1.children().eq(1)
        stateSpan = row1.children().eq(2)

        # the link of build should be correct
        expect(buildLink.attr('href')).toBe('#/builders/2/builds/1')

        # pending state
        build.complete = false
        build.results = -1
        build.state_string = 'pending'
        $rootScope.$digest()
        expect(resultSpan.hasClass('results_PENDING')).toBe(true)
        expect(resultSpan.text()).toBe('...')
        expect(durationSpan.hasClass('ng-hide')).toBe(true)
        expect(startedSpan.hasClass('ng-hide')).toBe(false)
        expect(stateSpan.text()).toBe('pending')

        # success state
        build.complete = true
        build.complete_at = 2
        build.results = results.SUCCESS
        build.state_string = 'finished'
        $rootScope.$digest()
        expect(resultSpan.hasClass('results_SUCCESS')).toBe(true)
        expect(resultSpan.text()).toBe('SUCCESS')
        expect(durationSpan.hasClass('ng-hide')).toBe(false)
        expect(startedSpan.hasClass('ng-hide')).toBe(true)
        expect(durationSpan.text()).toBe('1 s')
        expect(stateSpan.text()).toBe('finished')
        
        # failed state
        build.complete = true
        build.complete_at = 2
        build.results = results.FAILURE
        build.state_string = 'failed'
        $rootScope.$digest()
        expect(resultSpan.hasClass('results_FAILURE')).toBe(true)
        expect(resultSpan.text()).toBe('FAILURE')
        expect(durationSpan.hasClass('ng-hide')).toBe(false)
        expect(startedSpan.hasClass('ng-hide')).toBe(true)
        expect(durationSpan.text()).toBe('1 s')
        expect(stateSpan.text()).toBe('failed')
