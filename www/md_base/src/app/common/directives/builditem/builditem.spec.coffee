beforeEach module 'app'

describe 'builditem', ->

    $compile = $rootScope = $httpBackend = dataService = scope = null
    injected = ($injector) ->
        $compile = $injector.get('$compile')
        $rootScope = $injector.get('$rootScope')
        $httpBackend = $injector.get('$httpBackend')
        decorateHttpBackend($httpBackend)
        $q = $injector.get('$q')
        webSocketService = $injector.get('webSocketService')
        spyOn(webSocketService, 'getWebSocket').and.returnValue({})
        dataService = $injector.get('dataService')
        spyOn(dataService, 'startConsuming').and.returnValue($q.resolve())
        scope = $rootScope.$new()

    beforeEach inject injected

    it 'should display a build correctly', ->
        scope.showBuilder = true

        $httpBackend.expectDataGET('builds/1')
        dataService.getBuilds(1).then (builds) -> scope.build = builds[0]
        $httpBackend.flush()

        build = scope.build
        build.started_at = (new Date()).getTime() / 1000 - 3600

        $httpBackend.expectDataGET('builders/1')
        $httpBackend.expectGETSVGIcons()
        elem = $compile('<build-item build="build" show-builder="showBuilder">')(scope)
        $rootScope.$digest()
        $httpBackend.flush()

        innerRow = elem.children().eq(0)
        expect(innerRow.children().length).toBe(5)

        builderName = innerRow.children().eq(1).text().trim()
        buildNumber = innerRow.children().eq(2).text().trim()
        date = innerRow.children().eq(4).text().trim()

        expect(builderName).toBe('11')
        expect(buildNumber).toBe('#' + scope.build.number)
        expect(date).toBe('an hour ago')

    it 'should able to hide builder name', ->
        scope.showBuilder = false

        $httpBackend.expectDataGET('builds/1')
        dataService.getBuilds(1).then (builds) -> scope.build = builds[0]
        $httpBackend.flush()

        $httpBackend.expectGETSVGIcons()
        elem = $compile('<build-item build="build" show-builder="showBuilder">')(scope)
        $rootScope.$digest()

        innerRow = elem.children().eq(0)
        expect(innerRow.children().length).toBe(4)
        expect(innerRow.children()[0].tagName.toLowerCase()).toBe('build-status')
        expect(innerRow.children().eq(1).hasClass('number')).toBe(true)
        expect(innerRow.children().eq(3).hasClass('time')).toBe(true)
