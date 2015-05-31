beforeEach module 'app'

describe 'buildstatus', ->

    $rootScope = $compile = $httpBackend = null

    injected = ($injector) ->
        $compile = $injector.get('$compile')
        $rootScope = $injector.get('$rootScope')
        $httpBackend = $injector.get('$httpBackend')
        decorateHttpBackend($httpBackend)

    beforeEach inject injected

    it 'should show build status correctly', ->
        $httpBackend.expectGETSVGIcons()
        $rootScope.build =
            complete: false
            started_at: 0
            results: -1
        elem = $compile('<build-status build="build">')($rootScope)
        $httpBackend.flush()
        icon = elem.children().eq(0)

        # unknown status
        expect(icon.attr('md-svg-icon')).toBe('build-pending')
        expect(icon.hasClass('unknown')).toBe(true)
        expect(icon.hasClass('pending')).toBe(false)
        expect(icon.hasClass('success')).toBe(false)
        expect(icon.hasClass('fail')).toBe(false)

        # pending status
        $rootScope.build.started_at = (new Date()).valueOf()
        $rootScope.$digest()
        expect(icon.attr('md-svg-icon')).toBe('build-pending')
        expect(icon.hasClass('unknown')).toBe(false)
        expect(icon.hasClass('pending')).toBe(true)
        expect(icon.hasClass('success')).toBe(false)
        expect(icon.hasClass('fail')).toBe(false)
        
        # success status
        $rootScope.build.complete = true
        $rootScope.build.results = 0
        $rootScope.$digest()
        expect(icon.attr('md-svg-icon')).toBe('build-success')
        expect(icon.hasClass('unknown')).toBe(false)
        expect(icon.hasClass('pending')).toBe(false)
        expect(icon.hasClass('success')).toBe(true)
        expect(icon.hasClass('fail')).toBe(false)

        # fail status
        $rootScope.build.results = 2
        $rootScope.$digest()
        expect(icon.attr('md-svg-icon')).toBe('build-fail')
        expect(icon.hasClass('unknown')).toBe(false)
        expect(icon.hasClass('pending')).toBe(false)
        expect(icon.hasClass('success')).toBe(false)
        expect(icon.hasClass('fail')).toBe(true)
