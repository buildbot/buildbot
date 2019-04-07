/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
beforeEach(() =>
    // Mock modalService
    module(function($provide) {
        $provide.service('$uibModalInstance', () => ({close() {}}));
        return null;
    })
);

describe('Waterfall modal controller', function() {
    let $rootScope, $uibModalInstance, scope;
    let createController = ($rootScope = ($uibModalInstance = (scope = null)));

    const injected = function($injector) {
        const $controller = $injector.get('$controller');
        $rootScope = $injector.get('$rootScope');
        $uibModalInstance = $injector.get('$uibModalInstance');
        scope = $rootScope.$new();

        return createController = () =>
            $controller('waterfallModalController as m', {
                $scope: scope,
                selectedBuild: {}
            })
        ;
    };

    beforeEach(inject(injected));

    it('should be defined', function() {
        createController();
        const { m } = scope;
        expect(m).toBeDefined();
        // close function should be to defined
        expect(m.close).toBeDefined();
        return expect(typeof m.close).toBe('function');
    });

    it('should call close() on stateChangeStart event', function() {
        createController();
        const { m } = scope;
        spyOn(m, 'close');
        $rootScope.$broadcast('$stateChangeStart');
        return expect(m.close).toHaveBeenCalled();
    });

    return it('should call $uibModalInstance.close on close()', function() {
        createController();
        const { m } = scope;
        spyOn($uibModalInstance, 'close');
        expect($uibModalInstance.close).not.toHaveBeenCalled();
        m.close();
        return expect($uibModalInstance.close).toHaveBeenCalled();
    });
});
