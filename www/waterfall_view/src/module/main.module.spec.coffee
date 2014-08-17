beforeEach ->
    module 'waterfall_view'
    # Mock modalService
    module ($provide) ->
        $provide.service '$modal', -> open: ->
        null

describe 'Waterfall view controller', ->
    $rootScope = $state = elem = w = $document = $window = $modal = config = null

    injected = ($injector) ->
        $rootScope = $injector.get('$rootScope')
        scope = $rootScope.$new()
        $compile = $injector.get('$compile')
        $controller = $injector.get('$controller')
        $state = $injector.get('$state')
        $document = $injector.get('$document')
        $window = $injector.get('$window')
        $modal = $injector.get('$modal')
        config = $injector.get('config')
        elem = angular.element('<div></div>')
        elem.append($compile('<ui-view></ui-view>')(scope))
        $document.find('body').append(elem)

        $state.transitionTo('waterfall')
        $rootScope.$digest()
        w = $document.find('.waterfall').scope().w

        spyOn(w, 'setHeight').and.callFake ->

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
        expect(e.select('.svg-tooltip').empty()).toBe(true)
        n.__onmouseover({})
        expect(e.select('.svg-tooltip').empty()).toBe(false)
        # Test mousemove
        event = document.createEvent('MouseEvents')
        event.initMouseEvent('mousemove', true, true, window,
            0, 0, 0, 100, 850, false, false, false, false, 0, null)
        expect(e.select('.svg-tooltip').attr('transform')).toContain('NaN')
        n.__onmousemove(event)
        expect(e.select('.svg-tooltip').attr('transform')).not.toContain('NaN')
        # Test mouseout
        expect(e.select('.svg-tooltip').empty()).toBe(false)
        n.__onmouseout({})
        expect(e.select('.svg-tooltip').empty()).toBe(true)

    it 'should rerender the waterfall on resize', ->
        spyOn(w, 'render')
        expect(w.render).not.toHaveBeenCalled()
        angular.element($window).triggerHandler('resize')
        expect(w.render).toHaveBeenCalled()

    it 'should rerender the waterfall on data change', ->
        spyOn(w, 'render')
        expect(w.render).not.toHaveBeenCalled()
        #w.loadMore()
        $rootScope.$digest()
        expect(w.render).toHaveBeenCalled()
