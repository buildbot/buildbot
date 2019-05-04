/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
beforeEach(() =>
    // Mock modalService
    angular.mock.module(function($provide) {
        $provide.service('$uibModalInstance', function() { return {close() {}}; });
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

        createController = () =>
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
        expect(typeof m.close).toBe('function');
    });

    it('should call close() on stateChangeStart event', function() {
        createController();
        const { m } = scope;
        spyOn(m, 'close');
        $rootScope.$broadcast('$stateChangeStart');
        expect(m.close).toHaveBeenCalled();
    });

    it('should call $uibModalInstance.close on close()', function() {
        createController();
        const { m } = scope;
        spyOn($uibModalInstance, 'close');
        expect($uibModalInstance.close).not.toHaveBeenCalled();
        m.close();
        expect($uibModalInstance.close).toHaveBeenCalled();
    });
});
