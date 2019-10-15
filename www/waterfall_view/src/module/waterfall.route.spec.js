describe('Waterfall view', function() {
    let $state = null;

    const injected = $injector => $state = $injector.get('$state');

    beforeEach(inject(injected));

    it('should register a new state with the correct configuration', function() {
        const name = 'waterfall';
        const states = $state.get().map(state => state.name);
        expect(states).toContain(name);
    });
});
