beforeEach ->
    module 'waterfall_view'

describe 'Waterfall view controller', ->
    $rootScope = $state = elem = w = $document = null

    injected = ($injector) ->
        $rootScope = $injector.get('$rootScope')
        scope = $rootScope.$new()
        $compile = $injector.get('$compile')
        $controller = $injector.get('$controller')
        $state = $injector.get('$state')
        $document = $injector.get('$document')
        elem = angular.element('<div></div>')
        $document.find('body').append(elem)
        elem.append($compile('<ui-view></ui-view>')(scope))

        $state.transitionTo('waterfall')
        $rootScope.$digest()
        w = $document.find('.waterfall').scope().w

    beforeEach(inject(injected))

    # make sure we remove the element from the dom
    afterEach ->
        elem.remove()
        expect($document.find('svg').length).toEqual(0)

    it 'should be defined', ->
        expect(w).toBeDefined()

    it 'should bind the builds and builders to scope', ->
        expect(w.builds).toBeDefined()
        expect(w.builds.length).not.toBe(0)
        expect(w.builders).toBeDefined()
        expect(w.builders.length).not.toBe(0)

    it 'should create 2 svg elements and a lot of svg groups', ->
        expect(elem.find('svg').length).toBeGreaterThan(1)
        expect(elem.find('g').length).toBeGreaterThan(10)
