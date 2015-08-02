beforeEach module 'app'

describe 'buildinfo', ->

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

    it 'should display build changes correctly', ->
        $httpBackend.expectDataGET('builds/1')
        dataService.getBuilds(1).then (data) ->
            $rootScope.build = data[0]
        $httpBackend.flush()

        # Expect get requests, please do not change the order of exprect statements
        $httpBackend.expectDataGET('builds/1/changes')
        $httpBackend.expectGETSVGIcons()
        $httpBackend.expectDataGET('builds/1/properties')
        elem = $compile('<build-info build="build"></build-info>')($rootScope)
        $rootScope.$digest()
        $httpBackend.flush()

        changes = elem.children().eq(0).children().eq(0)
        expect(changes.children().length).toBe(1)


    it 'should display properties correctly', ->
        $httpBackend.expectDataGET('builds/1')
        dataService.getBuilds(1).then (data) ->
            $rootScope.build = data[0]
        $httpBackend.flush()

        # Expect get requests, please do not change the order of exprect statements
        $httpBackend.expectDataGET('builds/1/changes')
        $httpBackend.expectGETSVGIcons()
        $httpBackend.expectDataGET('builds/1/properties')
        elem = $compile('<build-info build="build"></build-info>')($rootScope)
        $rootScope.$digest()
        $httpBackend.flush()

        properties = elem.children().eq(0).children().eq(1)

        buttons = properties.children().eq(0).children()
        summarybtn = buttons.eq(0)
        rawbtn = buttons.eq(1)

        # Testing tab switch of properties
        expect(summarybtn.hasClass('selected')).toBe(true)
        expect(rawbtn.hasClass('selected')).toBe(false)
        expect(properties.children().eq(1).hasClass('summary')).toBe(true)
        expect(properties.children().eq(1).hasClass('raw')).toBe(false)

        rawbtn.triggerHandler('click')

        expect(summarybtn.hasClass('selected')).toBe(false)
        expect(rawbtn.hasClass('selected')).toBe(true)
        expect(properties.children().eq(1).hasClass('summary')).toBe(false)
        expect(properties.children().eq(1).hasClass('raw')).toBe(true)
        
        summarybtn.triggerHandler('click')
        expect(summarybtn.hasClass('selected')).toBe(true)
        expect(rawbtn.hasClass('selected')).toBe(false)
        expect(properties.children().eq(1).hasClass('summary')).toBe(true)
        expect(properties.children().eq(1).hasClass('raw')).toBe(false)

        # Testing summary content
        # 0. Get controller
        controller = elem.controller('buildInfo')

        # 1. Test owners
        mockproperties =
            owners: [
                name: 'user1'
                email: 'email@test.local'
            ,
                name: 'user1'
                email: 'email@test.local'
            ,
                name: 'user1'
                email: 'email@test.local'
            ]

        controller.properties = mockproperties
        controller.build = {}
        $rootScope.$digest()

        content = properties.children().eq(1).children()
        expect(content.length).toBe(3)
        for i in [0..2]
            owner = content.eq(i)
            origin = mockproperties.owners[i]
            avatar = owner.children().eq(0)
            link = owner.children().eq(1)
            expect(avatar.attr('src')).toBe('avatar?email=' + origin.email)
            expect(link.attr('href')).toBe('mailto:' + origin.email)
            expect(link.text()).toBe(origin.name)

        # 2. Test property summary
        mockproperties =
            revision: 'abcdefasfasdfasdffwjpeofiasdpvio'
            slave: 'slavetest'
            scheduler: 'testscheduler'
            dir: '/test/work/dir'

        controller.properties = mockproperties
        controller.build = {}

        $rootScope.$digest()
        content = properties.children().eq(1).children()
        
        expect(content.length).toBe(4)
        expect(content.eq(0).text()).toBe(mockproperties.revision)
        expect(content.eq(1).text()).toBe(mockproperties.slave)
        expect(content.eq(2).text()).toBe(mockproperties.scheduler)
        expect(content.eq(3).text()).toBe(mockproperties.dir)
        expect(content.eq(3).children().eq(1).attr('title')).toBe(mockproperties.dir)

        # 3. Test build summary
        mockbuild =
            complete: false
            started_at: (new Date()).valueOf() / 1000 - 4

        controller.properties = {}
        controller.build = mockbuild

        $rootScope.$digest()
        content = properties.children().eq(1).children()

        expect(content.length).toBe(1)
        expect(content.eq(0).text()).toBe('started a few seconds ago')

        mockbuild.complete = true
        mockbuild.complete_at = mockbuild.started_at + 4

        $rootScope.$digest()
        content = properties.children().eq(1).children()

        expect(content.length).toBe(2)
        expect(content.eq(0).text()).toBe('ran for 4 seconds')
        expect(content.eq(1).text()).toBe('started a few seconds ago')
