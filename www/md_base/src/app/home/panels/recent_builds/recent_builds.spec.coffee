beforeEach module 'app'

describe 'recent builds', ->

    $rootScope = $compile = $httpBackend = null

    injected = ($injector) ->
        $compile = $injector.get('$compile')
        $rootScope = $injector.get('$rootScope')
        $httpBackend = $injector.get('$httpBackend')
        $q = $injector.get('$q')
        mqService = $injector.get('mqService')
        spyOn(mqService,"setBaseUrl").and.returnValue(null)
        spyOn(mqService,"startConsuming").and.returnValue($q.when( -> ))
        spyOn(mqService,"stopConsuming").and.returnValue(null)
        decorateHttpBackend($httpBackend)

    beforeEach inject injected

    it 'should display tiles normally', ->
        $httpBackend.expectDataGET('masters')
        $httpBackend.expectDataGET('buildslaves')
        $httpBackend.expectDataGET('builders')
        $httpBackend.expectDataGET('schedulers')
        elem = $compile('<overview></overview>')($rootScope)
        $httpBackend.flush()

        mastertile = elem.children().eq(0)
        count = mastertile.children().eq(1).text().trim()
        expect(count).toBe('1')
        extra = mastertile.children().eq(2).text().trim()
        expect(extra).toBe('0 active.')

        slavetile = elem.children().eq(1)
        count = slavetile.children().eq(1).text().trim()
        expect(count).toBe('1')
        extra = slavetile.children().eq(2).text().trim()
        expect(extra).toBe('1 connection.')

        builderstile = elem.children().eq(2)
        count = builderstile.children().eq(1).text().trim()
        expect(count).toBe('1')

        schedulerstile = elem.children().eq(3)
        count = schedulerstile.children().eq(1).text().trim()
        expect(count).toBe('1')
