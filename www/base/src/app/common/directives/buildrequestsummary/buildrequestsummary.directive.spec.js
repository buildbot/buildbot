/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
beforeEach(angular.mock.module('app'));

describe('buildrequest summary controller', function() {
    let $q, $rootScope, $timeout, createController;
    let $scope = ($rootScope = ($q = ($timeout = null)));
    let goneto = (createController = null);
    let dataService = null;
    // override "$state"
    beforeEach(angular.mock.module(function($provide) {
        $provide.value("$state",
                        {go(...args) { return goneto = args; }});
    })
    );

    const injected = function($injector) {
        $rootScope = $injector.get('$rootScope');
        $scope = $rootScope.$new();
        $scope.buildrequestid = 1;
        $timeout = $injector.get('$timeout');
        const $controller = $injector.get('$controller');
        $q = $injector.get('$q');
        dataService = $injector.get('dataService');
        // stub out the actual backend of mqservice
        createController = () =>
            $controller('_buildrequestsummaryController',
                {$scope})
        ;
    };
    beforeEach(inject(injected));

    it('should get the buildrequest', function() {
        const buildrequests = [{buildrequestid: 1, builderid: 2, buildsetid: 3}];
        dataService.expect('builders', buildrequests);
        dataService.expect('buildrequests/1', buildrequests);
        dataService.expect('buildsets/3', buildrequests);
        expect(dataService.get).not.toHaveBeenCalled();
        const controller = createController();
        $timeout.flush();
        dataService.verifyNoOutstandingExpectation();
        expect($scope.buildrequest.buildrequestid).toBe(1);
    });

    it('should query for builds again if first query returns 0', function() {
        const buildrequests = [{buildrequestid: 1, builderid: 2, buildsetid: 3}];
        dataService.expect('builders', buildrequests);
        dataService.expect('buildrequests/1', buildrequests);
        dataService.expect('buildsets/3', buildrequests);
        let builds = [];

        const controller = createController();
        $timeout.flush();
        dataService.verifyNoOutstandingExpectation();

        dataService.expect('builds', {buildrequestid: 1}, builds);

        $scope.$apply(() => $scope.buildrequest.claimed = true);
        $timeout.flush();

        dataService.verifyNoOutstandingExpectation();
        expect($scope.builds.length).toBe(builds.length);

        builds = [{buildid: 1, buildrequestid: 1}, {buildid: 2, buildrequestid: 1}];
        $scope.builds.from(builds);

        $timeout.flush();
        dataService.verifyNoOutstandingExpectation();
        expect($scope.builds.length).toBe(builds.length);
    });
});
