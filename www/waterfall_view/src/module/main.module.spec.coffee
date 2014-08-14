beforeEach ->
    module 'waterfall_view'

describe 'Waterfall view controller', ->
    createController = scope = $rootScope = $state = elem = $document = null

    injected = ($injector) ->
        $rootScope = $injector.get('$rootScope')
        scope = $rootScope.$new()
        $compile = $injector.get('$compile')
        $controller = $injector.get('$controller')
        $state = $injector.get('$state')
        $document = $injector.get('$document')
        elem = angular.element('<div></div>')
        $document.find("body").append(elem)
        elem.append($compile('<ui-view></ui-view>')(scope))


    beforeEach(inject(injected))

    # make sure we remove the element from the dom
    afterEach ->
        elem.remove()
        expect($document.find("svg").length).toEqual(0)

    it 'should be defined', ->
        $state.transitionTo('waterfall')
        $rootScope.$digest()
        # make sure the whole stuff created lots of graphics data
        expect(elem.find("svg").length).toBeGreaterThan(1)
        expect(elem.find("g").length).toBeGreaterThan(10)
