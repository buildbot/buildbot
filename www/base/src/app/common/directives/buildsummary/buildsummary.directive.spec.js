beforeEach(angular.mock.module('app'));

describe('buildsummary controller', function() {
    let $compile, $rootScope, $stateParams, baseurl, createController, results, $scope;
    let dataService = ($scope = ($rootScope = ($compile = null)));
    let $timeout = (createController = ($stateParams = (results = (baseurl = null))));

    const injected = function($injector) {
        results = $injector.get('RESULTS');
        $rootScope = $injector.get('$rootScope');
        $scope = $rootScope.$new();
        $scope.buildid = 1;
        $scope.condensed = 0;

        $timeout = $injector.get('$timeout');
        $stateParams = $injector.get('$stateParams');
        const $q = $injector.get('$q');
        $compile = $injector.get('$compile');
        baseurl = $injector.get('config')['buildbotURL'];

        dataService = $injector.get('dataService');
        dataService.when('builds/1', [{buildid: 1, builderid: 1}]);
        dataService.when('builders', [{builderid: 1}]);
        dataService.when('builders/1', [{builderid: 1}]);
        dataService.when('builds/1/steps', [{builderid: 1, stepid: 1, number: 1}]);
        dataService.when('steps/1/logs', [{stepid: 1, logid: 1}, {stepid: 1, logid: 2}]);
    };

    beforeEach(inject(injected));

    it('should provide correct isStepDisplayed when condensed', function() {
        $scope.condensed = true;
        const element = $compile("<buildsummary buildid='buildid' condensed='condensed'></buildsummary>")($scope);
        $scope.$apply();
        const { buildsummary } = element.isolateScope();
        expect(buildsummary.isStepDisplayed({results:results.SUCCESS})).toBe(false);
        expect(buildsummary.isStepDisplayed({results:results.WARNING})).toBe(false);
        expect(buildsummary.isStepDisplayed({results:results.FAILURE})).toBe(false);
        buildsummary.toggleDetails();
        expect(buildsummary.isStepDisplayed({results:results.SUCCESS})).toBe(false);
        expect(buildsummary.isStepDisplayed({results:results.WARNING})).toBe(true);
        expect(buildsummary.isStepDisplayed({results:results.FAILURE})).toBe(true);
        buildsummary.toggleDetails();
        expect(buildsummary.isStepDisplayed({results:results.SUCCESS})).toBe(true);
        expect(buildsummary.isStepDisplayed({results:results.WARNING})).toBe(true);
        expect(buildsummary.isStepDisplayed({results:results.FAILURE})).toBe(true);
        buildsummary.toggleDetails();
        expect(buildsummary.isStepDisplayed({results:results.SUCCESS})).toBe(false);
        expect(buildsummary.isStepDisplayed({results:results.WARNING})).toBe(false);
        expect(buildsummary.isStepDisplayed({results:results.FAILURE})).toBe(false);
    });

    it('should provide correct isStepDisplayed when not condensed', function() {
        $scope.condensed = 0;
        const element = $compile("<buildsummary buildid='buildid' condensed='condensed'></buildsummary>")($scope);
        $scope.$apply();
        const { buildsummary } = element.isolateScope();
        expect(buildsummary.isStepDisplayed({results:results.SUCCESS})).toBe(true);
        expect(buildsummary.isStepDisplayed({results:results.WARNING})).toBe(true);
        expect(buildsummary.isStepDisplayed({results:results.FAILURE})).toBe(true);
        buildsummary.toggleDetails();
        expect(buildsummary.isStepDisplayed({results:results.SUCCESS})).toBe(false);
        expect(buildsummary.isStepDisplayed({results:results.WARNING})).toBe(false);
        expect(buildsummary.isStepDisplayed({results:results.FAILURE})).toBe(false);
        buildsummary.toggleDetails();
        expect(buildsummary.isStepDisplayed({results:results.SUCCESS})).toBe(false);
        expect(buildsummary.isStepDisplayed({results:results.WARNING})).toBe(true);
        expect(buildsummary.isStepDisplayed({results:results.FAILURE})).toBe(true);
        buildsummary.toggleDetails();
    });

    it('should provide correct isStepDisplayed when details = EVERYTHING and when details = NONE', function() {
        const element = $compile("<buildsummary buildid='buildid'></buildsummary>")($scope);
        $scope.$apply();
        const { buildsummary } = element.isolateScope();
        // details = EVERYTHING
        expect(buildsummary.isStepDisplayed({hidden: true})).toBe(false);
        expect(buildsummary.isStepDisplayed({hidden: false})).toBe(true);
        buildsummary.toggleDetails(); // set details = NONE
        expect(buildsummary.isStepDisplayed({hidden: false, results:results.FAILURE})).toBe(false);
    });

    it('should provide correct getDisplayedStepCount', function() {
        const element = $compile("<buildsummary buildid='buildid'></buildsummary>")($scope);
        $scope.$apply();
        const { buildsummary } = element.isolateScope();
        buildsummary.steps = [{hidden: false}, {hidden: false}];
        expect(buildsummary.getDisplayedStepCount()).toEqual(2);

        buildsummary.steps = [{hidden: true}, {hidden: true}];
        expect(buildsummary.getDisplayedStepCount()).toEqual(0);

        buildsummary.steps = [{hidden: true}, {hidden: false}];
        expect(buildsummary.getDisplayedStepCount()).toEqual(1);
    });

    it('assignDisplayedStepNumber should assign correct step display number', function() {
        const element = $compile("<buildsummary buildid='buildid'></buildsummary>")($scope);
        $scope.$apply();
        const { buildsummary } = element.isolateScope();
        var step;
        step = {number: 0, hidden: true, display_num: null};
        expect(buildsummary.assignDisplayedStepNumber(step)).toBe(true);
        expect(step.display_num).toEqual(null);

        step = {number: 1, hidden: false, display_num: null};
        expect(buildsummary.assignDisplayedStepNumber(step)).toBe(true);
        expect(step.display_num).toEqual(0);

        step = {number: 2, hidden: false, display_num: null};
        expect(buildsummary.assignDisplayedStepNumber(step)).toBe(true);
        expect(step.display_num).toEqual(1);

        step = {number: 3, hidden: false, display_num: null};
        expect(buildsummary.assignDisplayedStepNumber(step)).toBe(true);
        expect(step.display_num).toEqual(2);

        // reset display_num to zero whenever step.number = 0
        step = {number: 0, hidden: false, display_num: null};
        expect(buildsummary.assignDisplayedStepNumber(step)).toBe(true);
        expect(step.display_num).toEqual(0);

        step = {number: 1, hidden: false, display_num: null};
        expect(buildsummary.assignDisplayedStepNumber(step)).toBe(true);
        expect(step.display_num).toEqual(1);
    });
});
