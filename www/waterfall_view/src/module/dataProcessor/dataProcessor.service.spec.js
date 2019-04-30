/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS205: Consider reworking code to avoid use of IIFEs
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('Data Processor service', function() {

    let builders, builds;
    let dataProcessorService = (builds = (builders = null));

    const injected = function($injector) {
        const $rootScope = $injector.get('$rootScope');
        dataProcessorService = $injector.get('dataProcessorService');
        const Collection = $injector.get('Collection');

        const _builders = [{
            builderid: 1,
            name: 'builder1',
            masterids: [1]
        }
        , {
            builderid: 2,
            name: 'builder2',
            masterids: [1]
        }
        , {
            builderid: 3,
            name: 'builder3',
            masterids: [1]
        }
        , {
            builderid: 4,
            name: 'builder4',
            masterids: [1]
        }
        ];
        builders = new Collection("builders", {});
        builders.from(_builders);
        const _builds = [{
            buildid: 1,
            builderid: 1,
            started_at: 1403059709,
            complete_at: 1403059772,
            complete: true,
            results: 'success'
        }
        , {
            buildid: 2,
            builderid: 2,
            buildrequestid: 1,
            started_at: 1403059802,
            complete_at: 1403060287,
            complete: true,
            results: 'success'
        }
        , {
            buildid: 3,
            builderid: 2,
            buildrequestid: 2,
            started_at: 1403059710,
            complete_at: 1403060278,
            complete: true,
            results: 'failure'
        }
        , {
            buildid: 4,
            builderid: 3,
            buildrequestid: 2,
            started_at: 1403060250,
            complete_at: 0,
            complete: false
        }
        ];
        builds = new Collection("builds", {});
        builds.from(_builds);
    };

    beforeEach(inject(injected));

    it('should be defined', function() {
        expect(dataProcessorService).toBeDefined();
        // getGroups is a function
        expect(dataProcessorService.getGroups).toBeDefined();
        expect(typeof dataProcessorService.getGroups).toBe('function');
        // addStatus is a function
        expect(dataProcessorService.addStatus).toBeDefined();
        expect(typeof dataProcessorService.addStatus).toBe('function');
    });

    it('should add builds to builders', function() {
        // Add builds to builders
        dataProcessorService.getGroups(builders, builds, 0);
        for (let build of Array.from(builds)) {
            // A builder should contain its build
            expect(builders[build.builderid - 1].builds).toContain(build);
        }
        // Builders builds length should be equal to all builds length
        let buildsInBuilders = 0;
        for (let builder of Array.from(builders)) {
            buildsInBuilders += builder.builds.length;
        }
        expect(buildsInBuilders).toEqual(builds.length);
    });

    it('should create groups', function() {
        // Create groups with a bigger threshold
        let threshold = builds[1].started_at - builds[0].complete_at;
        let groups = dataProcessorService.getGroups(builders, builds, threshold);
        expect(groups.length).toBe(1);

        // Create groups with a smaller threshold
        threshold = builds[1].started_at - builds[0].complete_at;
        groups = dataProcessorService.getGroups(builders, builds, threshold - 1);
        expect(groups.length).toBe(2);

        // Add builds to groups, all build have to be in one group
        let buildsInGroups = 0;
        for (let build of Array.from(builds)) {
            for (let group of Array.from(groups)) {
                if (group.builds == null) { group.builds = []; }
                if ((build.started_at <= group.min) && (build.complete_at <= group.max)) {
                    group.builds.push(build);
                    buildsInGroups++;
                }
            }
        }
        expect(buildsInGroups).toEqual(builds.length);

        // If the time between two builds is less than the threshold, they should be in different groups
        Array.from(builds).map((build1, i) => {
            for (let build2 of Array.from(builds.slice(i + 1))) {
            // If build2 starts earlier than build1, swap them
                if (build2.buildid < build1.buildid) {
                    [build1, build2] = Array.from([build2, build1]);
                }
                if ((build2.started_at - build1.complete_at) > threshold) {
                    expect(build1.groupid).not.toBe(build2.groupid);
                }
            }
        });
    });

    it('should add complete_at to unfinished builds', function() {
        const unfinishedBuilds = builds.filter(build => !build.complete);
        dataProcessorService.getGroups(builders, unfinishedBuilds, 0);

        for (let build of Array.from(unfinishedBuilds)) {
            expect(build.complete_at).toBeDefined();
            // It should be a correct timestamp
            expect(build.complete_at.toString().length).toBe(10);
        }
    });

    it('should add status to builders', function() {
        // Add builds to builders first
        dataProcessorService.getGroups(builders, builds, 0);
        dataProcessorService.addStatus(builders);
        Array.from(builders).map((builder) =>
            builder.complete ? expect(builder.results).toBeDefined()
            : expect(builder.results).not.toBeDefined());
    });
});
