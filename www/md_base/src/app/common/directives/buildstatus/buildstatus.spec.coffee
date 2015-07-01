beforeEach module 'app'

describe 'buildstatus', ->

    $rootScope = $compile = $httpBackend = RESULTS_TEXT = null

    injected = ($injector) ->
        $compile = $injector.get('$compile')
        $rootScope = $injector.get('$rootScope')
        $httpBackend = $injector.get('$httpBackend')
        RESULTS_TEXT = $injector.get('RESULTS_TEXT')
        decorateHttpBackend($httpBackend)

    beforeEach inject injected

    it 'should show status correctly', ->
        $httpBackend.expectGETSVGIcons()
        $rootScope.build =
            complete: false
            started_at: 0
            results: -1
        elem = $compile('<build-status build="build">')($rootScope)
        $httpBackend.flush()
        icon = elem.children().eq(0)

        # unknown status
        expect(icon.attr('md-svg-icon')).toBe('pending')
        expect(icon.hasClass('unknown')).toBe(true)
        expect(icon.hasClass('pending')).toBe(false)
        for _, text of RESULTS_TEXT
            expect(icon.hasClass(text.toLowerCase())).toBe(false)

        # pending status
        $rootScope.build.started_at = (new Date()).valueOf()
        $rootScope.$digest()
        expect(icon.attr('md-svg-icon')).toBe('pending')
        expect(icon.hasClass('unknown')).toBe(false)
        expect(icon.hasClass('pending')).toBe(true)
        for _, text of RESULTS_TEXT
            expect(icon.hasClass(text.toLowerCase())).toBe(false)
        
        # success status
        $rootScope.build.complete = true
        $rootScope.build.results = 0
        $rootScope.$digest()
        expect(icon.attr('md-svg-icon')).toBe('checkmark')
        expect(icon.hasClass('unknown')).toBe(false)
        expect(icon.hasClass('pending')).toBe(false)
        for code, text of RESULTS_TEXT
            expect(icon.hasClass(text.toLowerCase())).toBe(code == '0')

        # fail status
        for i in [1..6]
            $rootScope.build.results = i
            $rootScope.$digest()
            expect(icon.attr('md-svg-icon')).toBe('crossmark')
            expect(icon.hasClass('unknown')).toBe(false)
            expect(icon.hasClass('pending')).toBe(false)
            for code, text of RESULTS_TEXT
                expect(icon.hasClass(text.toLowerCase())).toBe(parseInt(code) == i)
