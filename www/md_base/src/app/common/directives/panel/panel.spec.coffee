beforeEach module 'app'

describe 'panel', ->

    $rootScope = $compile = $httpBackend = null

    injected = ($injector) ->
        $compile = $injector.get('$compile')
        $rootScope = $injector.get('$rootScope')
        $httpBackend = $injector.get('$httpBackend')
        decorateHttpBackend($httpBackend)

    beforeEach inject injected

    panelbind =
        name: 'underline_should_be_replaced'
        title: "test_title_string"
        collapsed: false

    it 'should display title normally', ->
        $httpBackend.expectGETSVGIcons()
        $rootScope.data = panelbind
        panel = $compile('<panel bind="data">')($rootScope)
        $httpBackend.flush()

        title = panel.children().eq(0).children().eq(0)
        expect(title.text()).toBe("test_title_string")

    it 'should collapse normally', ->
        $httpBackend.expectGETSVGIcons()
        $rootScope.data = panelbind
        panel = $compile('<panel bind="data">')($rootScope)
        $httpBackend.flush()

        expect(panel.hasClass('collapsed')).toBe(false)

        panelbind.collapsed = true
        $rootScope.$digest()

        expect(panel.hasClass('collapsed')).toBe(true)

        panelbind.collapsed = false
        $rootScope.$digest()

        expect(panel.hasClass('collapsed')).toBe(false)

        titlebar = panel.children().eq(0).children().eq(0)
        expandButton = titlebar.children().eq(1).children().eq(0)

        expandButton.triggerHandler('click')
        expect(panelbind.collapsed).toBe(true)
        expect(panel.hasClass('collapsed')).toBe(true)

        expandButton.triggerHandler('click')
        expect(panelbind.collapsed).toBe(false)
        expect(panel.hasClass('collapsed')).toBe(false)


    it 'should lock normally', ->
        $httpBackend.expectGETSVGIcons()
        $rootScope.data = panelbind
        panel = $compile('<panel bind="data" locked="locked">')($rootScope)
        $httpBackend.flush()

        titlebar = panel.children().eq(0).children().eq(0)
        title = titlebar.children().eq(0)
        expect(title.hasClass('locked')).toBe(false)
        expect(titlebar.children().length).toBe(2)

        $rootScope.locked = true
        $rootScope.$digest()

        expect(title.hasClass('locked')).toBe(true)
        expect(titlebar.children().length).toBe(1)


    it 'should compile content directive correctly', ->
        $httpBackend.expectGETSVGIcons()
        $rootScope.data = panelbind
        panel = $compile('<panel bind="data">')($rootScope)
        $httpBackend.flush()

        content = panel.children().eq(0).children().eq(1)
        subdirective = content.children()[0]
        expect(subdirective.tagName.toLowerCase()).toBe('underline-should-be-replaced')
