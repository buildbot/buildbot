beforeEach module 'app'

describe 'MD: Sidebar directive', ->
    $rootScope = $compile = $httpBackend = _menuServiceProvider = null

    injected = ($injector) ->
        $compile = $injector.get('$compile')
        $rootScope = $injector.get('$rootScope')
        $httpBackend = $injector.get('$httpBackend')
        decorateHttpBackend($httpBackend)

    beforeEach module (menuServiceProvider) ->
        _menuServiceProvider = menuServiceProvider
        return null
    beforeEach inject injected

    afterEach ->
        $httpBackend.verifyNoOutstandingExpectation()
        $httpBackend.verifyNoOutstandingRequest()

    it 'should displays nav items', ->
        _menuServiceProvider.items = []
        $httpBackend.expectGETSVGIcons()
        element = $compile('<div><sidenav items="items" current="current"></sidenav></div>')($rootScope)
        $rootScope.$digest()
        $httpBackend.flush()

        sidenavEle = element.children().eq(0)

        # sidenav contains a md-toolbar and a md-content
        expect(sidenavEle.children().length).toBe(2)

        # sidenav items is empty when not items specified
        content = sidenavEle.children().eq(1)
        expect(content.children().length).toBe(0)

        # adding items
        for n in [1..3]
            _menuServiceProvider.addItem
                name: 'testitem' + n
                caption: 'test item ' + n
                icon: 'test-icon-' + n
                order: n

        $rootScope.$digest()

        # there should be 3 nav items
        expect(content.children().length).toBe(3)

        for n in [1..3]
            navitem = content.children().eq(n-1)
            title = navitem.children().eq(1).text()
            expect(title).toBe('test item ' + n)

        # testing highlight
        for i in [i..3]
            _menuServiceProvider.current = 'testitem' + i
            $rootScope.$digest()

            for n in [1..3]
                navitem = content.children().eq(n-1)
                expect(navitem.hasClass('highlighted')).toBe(i == n)
