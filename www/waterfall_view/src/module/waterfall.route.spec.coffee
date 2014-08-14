beforeEach ->
    # Mock modalService
    module ($provide) ->
        $provide.service '$modal', ->
        $provide.service '$modalInstance', ->
        null

    module 'waterfall_view'

describe 'Waterfall view', ->
    $state = null

    injected = ($injector) ->
        $state = $injector.get('$state')

    beforeEach(inject(injected))

    it 'should register a new state with the correct configuration', ->
        name = 'waterfall'
        state = $state.get().pop()
        data = state.data
        expect(state.name).toBe(name)
        expect(state.controller).toBe("#{name}Controller")
        expect(state.controllerAs).toBe('w')
        expect(state.templateUrl).toBe("waterfall_view/views/#{name}.html")
        expect(state.url).toBe("/#{name}")