describe 'Waterfall view', ->
    $state = null

    injected = ($injector) ->
        $state = $injector.get('$state')

    beforeEach(inject(injected))

    it 'should register a new state with the correct configuration', ->
        name = 'waterfall'
        states = $state.get().map (state) -> return state.name
        expect(states).toContain(name)
