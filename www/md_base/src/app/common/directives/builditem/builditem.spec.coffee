beforeEach module 'app'

describe 'builditem', ->

    $rootScope = $compile = $httpBackend = buildbotService = null

    injected = ($injector) ->
        $compile = $injector.get('$compile')
        $rootScope = $injector.get('$rootScope')
        $httpBackend = $injector.get('$httpBackend')
        decorateHttpBackend($httpBackend)
        mqService = $injector.get('mqService')
        $q = $injector.get('$q')
        spyOn(mqService,"setBaseUrl").and.returnValue(null)
        spyOn(mqService,"startConsuming").and.returnValue($q.when( -> ))
        spyOn(mqService,"stopConsuming").and.returnValue(null)
        buildbotService = $injector.get('buildbotService')

    beforeEach inject injected

    it 'should display a build correctly', ->
        $rootScope.showBuilder = true

        $httpBackend.expectDataGET('builds/1')
        buildbotService.one('builds', 1).bind($rootScope)
        $httpBackend.flush()
        
        build = $rootScope.build
        build.started_at = (new Date()).getTime() / 1000 - 3600

        $httpBackend.expectDataGET('builders/1')
        $httpBackend.expectGETSVGIcons()
        elem = $compile('<build-item build="build" show-builder="showBuilder">')($rootScope)
        $rootScope.$digest()
        $httpBackend.flush()

        innerRow = elem.children().eq(0)
        expect(innerRow.children().length).toBe(4)

        builderName = innerRow.children().eq(1).text().trim()
        buildNumber = innerRow.children().eq(2).text().trim()
        date = innerRow.children().eq(3).text().trim()

        expect(builderName).toBe('11')
        expect(buildNumber).toBe('#' + $rootScope.build.number)
        expect(date).toBe('an hour ago')

    it 'should able to hide builder name', ->
        $rootScope.showBuilder = false

        $httpBackend.expectDataGET('builds/1')
        buildbotService.one('builds', 1).bind($rootScope)
        $httpBackend.flush()

        $httpBackend.expectGETSVGIcons()
        elem = $compile('<build-item build="build" show-builder="showBuilder">')($rootScope)
        $rootScope.$digest()

        innerRow = elem.children().eq(0)
        expect(innerRow.children().length).toBe(3)
        expect(innerRow.children()[0].tagName.toLowerCase()).toBe('build-status')
        expect(innerRow.children().eq(1).hasClass('number')).toBe(true)
        expect(innerRow.children().eq(2).hasClass('time')).toBe(true)
