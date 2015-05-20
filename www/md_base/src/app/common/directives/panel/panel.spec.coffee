beforeEach module 'app'

describe 'panel', ->

    $rootScope = $compile = $httpBackend = null

    injected = ($injector) ->
        $compile = $injector.get('$compile')
        $rootScope = $injector.get('$rootScope')
        $httpBackend = $injector.get('$httpBackend')
        decorateHttpBackend($httpBackend)

    beforeEach inject injected

    it 'should display title normally', ->
        $httpBackend.expectGETSVGIcons()
        $rootScope.title = "test_title_string"
        panel = $compile('<panel title="title">')($rootScope)
        $httpBackend.flush()

        title = panel.children().eq(0).children().eq(0)
        expect(title.text()).toBe("test_title_string")

    it 'should collapse normally', ->
        $httpBackend.expectGETSVGIcons()
        panel = $compile('<panel is-collapsed="collapsed">')($rootScope)
        $httpBackend.flush()

        expect(panel.hasClass('collapsed')).toBe(false)

        $rootScope.collapsed = true
        $rootScope.$digest()

        expect(panel.hasClass('collapsed')).toBe(true)

        $rootScope.collapsed = false
        $rootScope.$digest()

        expect(panel.hasClass('collapsed')).toBe(false)

        titlebar = panel.children().eq(0).children().eq(0)
        expandButton = titlebar.children().eq(1).children().eq(0)

        expandButton.triggerHandler('click')
        expect($rootScope.collapsed).toBe(true)
        expect(panel.hasClass('collapsed')).toBe(true)

        expandButton.triggerHandler('click')
        expect($rootScope.collapsed).toBe(false)
        expect(panel.hasClass('collapsed')).toBe(false)


    it 'should lock normally', ->
        $httpBackend.expectGETSVGIcons()
        panel = $compile('<panel locked="locked">')($rootScope)
        $httpBackend.flush()

        titlebar = panel.children().eq(0).children().eq(0)
        title = titlebar.children().eq(0)
        expect(title.hasClass('locked')).toBe(false)
        expect(titlebar.children().length).toBe(2)

        $rootScope.locked = true
        $rootScope.$digest()

        expect(title.hasClass('locked')).toBe(true)
        expect(titlebar.children().length).toBe(1)
