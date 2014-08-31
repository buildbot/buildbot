beforeEach ->
    module 'waterfall_view'
    # Mock modalService
    module ($provide) ->
        $provide.service '$modal', -> open: ->
        null

describe 'Waterfall view controller', ->
    $rootScope = $state = elem = w = $document = $window = $modal = config = $timeout = null

    injected = ($injector) ->
        $rootScope = $injector.get('$rootScope')
        scope = $rootScope.$new()
        $compile = $injector.get('$compile')
        $controller = $injector.get('$controller')
        $state = $injector.get('$state')
        $document = $injector.get('$document')
        $window = $injector.get('$window')
        $modal = $injector.get('$modal')
        $timeout = $injector.get('$timeout')
        config = $injector.get('config')
        elem = angular.element('<div></div>')
        elem.append($compile('<ui-view></ui-view>')(scope))
        $document.find('body').append(elem)

        $state.transitionTo('waterfall')
        $rootScope.$digest()
        scope = $document.find('.waterfall').scope()
        w = $document.find('.waterfall').controller()
        spyOn(w, 'mouseOver').and.callThrough()
        spyOn(w, 'mouseOut').and.callThrough()
        spyOn(w, 'mouseMove').and.callThrough()
        spyOn(w, 'click').and.callThrough()
        spyOn(w, 'loadMore').and.callThrough()
        # We don't want the setHeight to call loadMore
        spyOn(w, 'setHeight').and.callFake ->
        # Data is loaded
        $timeout.flush()

    beforeEach(inject(injected))

    # make sure we remove the element from the dom
    afterEach ->
        expect($document.find("svg").length).toEqual(2)
        elem.remove()
        expect($document.find('svg').length).toEqual(0)

    it 'should be defined', ->
        expect(w).toBeDefined()

    it 'should bind the builds and builders to scope', ->
        limit = config.plugins.waterfall_view.limit
        expect(w.builds).toBeDefined()
        expect(w.builds.length).toBe(limit)
        expect(w.builders).toBeDefined()
        expect(w.builders.length).not.toBe(0)

    it 'should create svg elements', ->
        expect(elem.find('svg').length).toBeGreaterThan(1)
        expect(elem.find('g').length).toBeGreaterThan(1)

    it 'should trigger mouse events on builds', ->
        e = d3.select('.build')
        n = e.node()
        # Test click event
        spyOn($modal, 'open')
        expect($modal.open).not.toHaveBeenCalled()
        n.__onclick()
        expect($modal.open).toHaveBeenCalled()
        # Test mouseover
        expect(w.mouseOver).not.toHaveBeenCalled()
        expect(e.select('.svg-tooltip').empty()).toBe(true)
        n.__onmouseover({})
        expect(w.mouseOver).toHaveBeenCalled()
        expect(e.select('.svg-tooltip').empty()).toBe(false)
        # Test mousemove
        expect(w.mouseMove).not.toHaveBeenCalled()
        n.__onmousemove({})
        expect(w.mouseMove).toHaveBeenCalled()
        # Test mouseout
        expect(w.mouseOut).not.toHaveBeenCalled()
        expect(e.select('.svg-tooltip').empty()).toBe(false)
        n.__onmouseout({})
        expect(w.mouseOut).toHaveBeenCalled()
        expect(e.select('.svg-tooltip').empty()).toBe(true)

    it 'should rerender the waterfall on resize', ->
        spyOn(w, 'render').and.callThrough()
        expect(w.render).not.toHaveBeenCalled()
        angular.element($window).triggerHandler('resize')
        expect(w.render).toHaveBeenCalled()

    it 'should rerender the waterfall on data change', ->
        spyOn(w, 'render').and.callThrough()
        expect(w.render).not.toHaveBeenCalled()
        w.loadMore()
        $timeout.flush()
        expect(w.render).toHaveBeenCalled()

    it 'should lazy load data on scroll', ->
        spyOn(w, 'getHeight').and.returnValue(900)
        e = d3.select('.inner-content')
        n = e.node()
        expect(w.loadMore).not.toHaveBeenCalled()
        angular.element(n).triggerHandler('scroll')
        expect(w.loadMore).toHaveBeenCalled()

    it 'should have string representations of result codes', ->
        testBuild =
            complete: false
            started_at: 0
        expect(w.getResultClassFromThing(testBuild)).toBe('pending')
        testBuild.complete = true
        expect(w.getResultClassFromThing(testBuild)).toBe('unknown')
        results =
            0: 'success'
            1: 'warnings'
            2: 'failure'
            3: 'skipped'
            4: 'exception'
            5: 'cancelled'
        for i in [0..5]
            testBuild.results = i
            expect(w.getResultClassFromThing(testBuild)).toBe(results[i])
