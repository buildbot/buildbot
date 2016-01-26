beforeEach module 'app'

describe 'overview', ->

    $rootScope = $compile = $httpBackend = API = null

    injected = ($injector) ->
        $injector.get('$window').ReconnectingWebSocket = WebSocket
        $compile = $injector.get('$compile')
        $rootScope = $injector.get('$rootScope')
        $httpBackend = $injector.get('$httpBackend')
        $q = $injector.get('$q')
        dataService = $injector.get('dataService')
        decorateHttpBackend($httpBackend)

    beforeEach inject(injected)

    it 'should display tiles normally', ->
        $httpBackend.expectDataGET('masters')
        $httpBackend.expectDataGET('workers')
        $httpBackend.expectDataGET('builders')
        $httpBackend.expectDataGET('schedulers')
        elem = $compile('<overview></overview>')($rootScope)
        $httpBackend.flush()

        mastertile = elem.children().eq(0)
        count = mastertile.children().eq(1).text().trim()
        expect(count).toBe('1')
        extra = mastertile.children().eq(2).text().trim()
        expect(extra).toBe('0 active.')

        workertile = elem.children().eq(1)
        count = workertile.children().eq(1).text().trim()
        expect(count).toBe('1')
        extra = workertile.children().eq(2).text().trim()
        expect(extra).toBe('1 connection.')

        builderstile = elem.children().eq(2)
        count = builderstile.children().eq(1).text().trim()
        expect(count).toBe('1')

        schedulerstile = elem.children().eq(3)
        count = schedulerstile.children().eq(1).text().trim()
        expect(count).toBe('1')
