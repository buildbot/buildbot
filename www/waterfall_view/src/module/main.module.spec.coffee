beforeEach ->
    module 'waterfall_view'

describe 'Waterfall view controller', ->
    $rootScope = $state = elem = w = $document = $window = config = null

    injected = ($injector) ->
        $rootScope = $injector.get('$rootScope')
        scope = $rootScope.$new()
        $compile = $injector.get('$compile')
        $controller = $injector.get('$controller')
        $state = $injector.get('$state')
        $document = $injector.get('$document')
        $window = $injector.get('$window')
        config = $injector.get('config')
        elem = angular.element('<div></div>')
        $document.find('body').append(elem)
        elem.append($compile('<ui-view></ui-view>')(scope))

        $state.transitionTo('waterfall')
        $rootScope.$digest()
        w = $document.find('.waterfall').scope().w

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
        expect(elem.find('.builder').length).toBeGreaterThan(1)
        expect(elem.find('.build').length).toBeGreaterThan(1)

    it 'should trigger mouse events on builds', ->
        

    it 'should rerender the waterfall on resize', ->
        spyOn(w, 'render')
        expect(w.render).not.toHaveBeenCalled()
        angular.element($window).triggerHandler('resize')
        expect(w.render).toHaveBeenCalled()
