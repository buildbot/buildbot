/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS206: Consider reworking classes to avoid initClass
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
beforeEach(function() {
    angular.mock.module(function($provide) {
        $provide.service('resultsService', function() { return {results2class() {}}; });
    });

    // Mock bbSettingsProvider
    angular.mock.module(function($provide) {
        $provide.provider('bbSettingsService', (function() {
            let group = undefined;
            const Cls = class {
                static initClass() {
                    group = {};
                }
                addSettingsGroup(g) { return g.items.map(function(i) {
                    if (i.name === 'lazy_limit_waterfall') {
                        i.default_value = 2;
                    }
                    return group[i.name] = {value: i.default_value};
                }); }
                $get() {
                    return {
                        getSettingsGroup() {
                            return group;
                        },
                        save() {}
                    };
                }
            };
            Cls.initClass();
            return Cls;
        })()
        );
    });
    angular.mock.module('grid_view');
});

describe('Grid view controller', function() {
    // Test data
    let $rootScope, dataService, scope;
    const builders = [{
        builderid: 1,
        tags: []
    }
    , {
        builderid: 2,
        tags: ['a']
    }
    , {
        builderid: 3,
        tags: ['a', 'b']
    }
    , {
        builderid: 4,
        tags: ['b']
    }
    ];

    const builds = [{
        buildid: 1,
        buildrequestid: 1,
        builderid: 1
    }
    , {
        buildid: 2,
        buildrequestid: 2,
        builderid: 2
    }
    , {
        buildid: 3,
        buildrequestid: 3,
        builderid: 4
    }
    , {
        buildid: 4,
        buildrequestid: 4,
        builderid: 3
    }
    , {
        buildid: 5,
        buildrequestid: 5,
        builderid: 1
    }
    , {
        buildid: 6,
        buildrequestid: 6,
        builderid: 4
    }
    , {
        buildid: 7,
        buildrequestid: 7,
        builderid: 3
    }
    , {
        buildid: 8,
        buildrequestid: 8,
        builderid: 2
    }
    ];

    const buildrequests = [{
        buildrequestid: 1,
        builderid: 1,
        buildsetid: 1
    }
    , {
        buildrequestid: 2,
        builderid: 2,
        buildsetid: 1
    }
    , {
        buildrequestid: 3,
        builderid: 1,
        buildsetid: 2
    }
    , {
        buildrequestid: 4,
        builderid: 3,
        buildsetid: 2
    }
    , {
        buildrequestid: 5,
        builderid: 4,
        buildsetid: 2
    }
    , {
        buildrequestid: 6,
        builderid: 4,
        buildsetid: 3
    }
    , {
        buildrequestid: 7,
        builderid: 3,
        buildsetid: 3
    }
    , {
        buildrequestid: 8,
        builderid: 2,
        buildsetid: 3
    }
    ];

    const buildsets = [{
        bsid: 1,
        sourcestamps: [
            {ssid: 1}
        ]
    }
    , {
        bsid: 2,
        sourcestamps: [
            {ssid: 2}
        ]
    }
    , {
        bsid: 3,
        sourcestamps: [
            {ssid: 3}
        ]
    }
    ];

    const changes = [{
        changeid: 3,
        branch: 'refs/pull/3333/merge',
        sourcestamp: {
            ssid: 3
        }
    }
    , {
        changeid: 1,
        branch: 'master',
        sourcestamp: {
            ssid: 1
        }
    }
    , {
        changeid: 2,
        branch: null,
        sourcestamp: {
            ssid: 2
        }
    }
    ];

    let createController = (scope = ($rootScope = (dataService = null)));

    const injected = function($injector) {
        $rootScope = $injector.get('$rootScope');
        dataService = $injector.get('dataService');
        scope = $rootScope.$new();
        dataService.when('builds', builds);
        dataService.when('builders', builders);
        dataService.when('changes', changes);
        dataService.when('buildrequests', buildrequests);
        dataService.when('buildsets', buildsets);

        // Create new controller using controller as syntax
        const $controller = $injector.get('$controller');
        createController = () =>
            $controller('gridController as C',
                // Inject controller dependencies
                {$scope: scope})
        ;
    };

    beforeEach(inject(injected));

    it('should be defined', function() {
        createController();
        expect(scope.C).toBeDefined();
    });

    it('should bind the builds, builders, changes, buildrequests and buildsets to scope', function() {
        createController();
        $rootScope.$digest();
        expect(scope.C.builds).toBeDefined();
        expect(scope.C.builds.length).toBe(builds.length);
        expect(scope.C.builders).toBeDefined();
        expect(scope.C.builders.length).toBe(builders.length);
        expect(scope.C.changes).toBeDefined();
        expect(scope.C.changes.length).toBe(changes.length);
        expect(scope.C.buildrequests).toBeDefined();
        expect(scope.C.buildrequests.length).toBe(buildrequests.length);
        expect(scope.C.buildsets).toBeDefined();
        expect(scope.C.buildsets.length).toBe(buildsets.length);
    });

    it('should list branches', function() {
        createController();
        $rootScope.$digest();
        scope.C.onChange();
        expect(scope.branches).toBeDefined();
        expect(scope.branches).toEqual(['refs/pull/3333/merge', 'master']);
    });

    it('should only list changes of the selected branch', function() {
        createController();
        $rootScope.$digest();
        scope.C.branch = 'master';
        scope.C.onChange();
        expect(scope.changes).toBeDefined();
        expect(scope.changes.length).toBe(2);
    });

    it('should only list builders with builds of the selected branch', function() {
        createController();
        $rootScope.$digest();
        scope.C.branch = 'refs/pull/3333/merge';
        scope.C.onChange();
        expect(scope.builders).toBeDefined();
        expect(scope.builders.length).toBe(3);
    });

    it('should only list builders with the selected tags', function() {
        createController();
        $rootScope.$digest();
        scope.C.tags = ['b'];
        scope.C.onChange();
        expect(scope.builders).toBeDefined();
        expect(scope.builders.length).toBe(2);
    });
});
