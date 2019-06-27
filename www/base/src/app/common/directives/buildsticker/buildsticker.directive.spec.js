beforeEach(angular.mock.module('app'));

describe('buildsticker controller', function() {
    let $compile, $rootScope, $timeout, results, scope;
    let dataService = (scope = ($compile = (results = ($timeout = ($rootScope = null)))));

    const injected = function($injector) {
        $compile = $injector.get('$compile');
        $rootScope = $injector.get('$rootScope');
        scope = $rootScope.$new();
        const $controller = $injector.get('$controller');
        const $q = $injector.get('$q');
        $timeout = $injector.get('$timeout');
        results = $injector.get('RESULTS');
        dataService = $injector.get('dataService');
    };

    beforeEach(inject(injected));

    it('directive should generate correct html', function() {
        const build = {buildid: 3, builderid: 2, number: 1};
        dataService.when('builds', [build]);
        dataService.when('builds/3', [build]);
        dataService.when('builders', [{builderid: 2}]);
        dataService.when('builders/2', [{builderid: 2}]);
        const data = dataService.open();
        data.getBuilds(build.buildid).onNew = build => scope.build = build;
        const element = $compile("<buildsticker build='build'></buildsticker>")(scope);
        $timeout.flush();
        $rootScope.$digest();

        const sticker = element.children().eq(0);

        const row0 = sticker.children().eq(0);
        const row1 = sticker.children().eq(1);

        const resultSpan = row0.children().eq(0);
        const buildLink = row0.children().eq(1);
        const durationSpan = row1.children().eq(0);
        const startedSpan = row1.children().eq(1);
        const stateSpan = row1.children().eq(2);

        // the link of build should be correct
        expect(buildLink.attr('href')).toBe('#/builders/2/builds/1');

        // pending state
        scope.build.complete = false;
        scope.build.started_at = Date.now();
        scope.build.results = -1;
        scope.build.state_string = 'pending';
        scope.$apply();
        expect(resultSpan.hasClass('results_PENDING')).toBe(true);
        expect(resultSpan.text()).toBe('...');
        expect(durationSpan.hasClass('ng-hide')).toBe(true);
        expect(startedSpan.hasClass('ng-hide')).toBe(false);
        expect(stateSpan.text()).toBe('pending');

        // success state
        scope.build.complete = true;
        scope.build.complete_at = scope.build.started_at + 1;
        scope.build.results = results.SUCCESS;
        scope.build.state_string = 'finished';
        scope.$apply();
        expect(resultSpan.hasClass('results_SUCCESS')).toBe(true);
        expect(resultSpan.text()).toBe('SUCCESS');
        expect(durationSpan.hasClass('ng-hide')).toBe(false);
        expect(startedSpan.hasClass('ng-hide')).toBe(true);
        expect(durationSpan.text()).toBe('1 s');
        expect(stateSpan.text()).toBe('finished');

        // failed state
        scope.build.complete = true;
        scope.build.complete_at = scope.build.started_at + 1;
        scope.build.results = results.FAILURE;
        scope.build.state_string = 'failed';
        scope.$apply();
        expect(resultSpan.hasClass('results_FAILURE')).toBe(true);
        expect(resultSpan.text()).toBe('FAILURE');
        expect(durationSpan.hasClass('ng-hide')).toBe(false);
        expect(startedSpan.hasClass('ng-hide')).toBe(true);
        expect(durationSpan.text()).toBe('1 s');
        expect(stateSpan.text()).toBe('failed');
    });
});
