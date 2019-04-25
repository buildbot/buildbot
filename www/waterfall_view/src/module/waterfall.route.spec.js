/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('Waterfall view', function() {
    let $state = null;

    const injected = $injector => $state = $injector.get('$state');

    beforeEach(inject(injected));

    return it('should register a new state with the correct configuration', function() {
        const name = 'waterfall';
        const states = $state.get().map(state => state.name);
        return expect(states).toContain(name);
    });
});
