/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS205: Consider reworking code to avoid use of IIFEs
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class DataProcessor {
    constructor() {
        ({});
    }
    // Returns groups and adds builds to builders
    getGroups(builders, builds, threshold) {
        // Sort builds by buildid
        let builder;
        builds.sort((a, b) => a.buildid - b.buildid);
        // Create groups: ignore periods when builders are idle
        const groups = [];

        let groupid = -1;
        const last = {groupid: 0, time: 0};
        // Create empty builds array for all the builders
        for (builder of Array.from(builders)) {
            builder.builds = [];
        }
        for (let build of Array.from(builds)) {
            builder = builders.get(build.builderid);
            if ((builder == null) || !builder.builds) {
                // builder is filtered, so we don't take its build in account
                continue;
            }
            // Group number starts from 0, for the first time the condition is always true
            if ((build.started_at - last.time) > threshold) { ++groupid; }

            // Create new object for a group with the minimum time
            if (groups[groupid] == null) { groups[groupid] = {min: build.started_at}; }
            // Add maximum time to the group object when the groupid is increased
            if (last.groupid !== groupid) {
                groups[last.groupid].max = last.time;
            }

            if (!build.complete) { build.complete_at = Math.round(new Date() / 1000); }
            build.groupid = (last.groupid = groupid);
            builder = builders.get(build.builderid);
            builder.builds.push(build);

            if (build.complete_at > last.time) { last.time = build.complete_at; }
        }
        // The last group maximum time
        if (groups[last.groupid]) {
            groups[last.groupid].max = last.time;
        }
        return groups;
    }

    // Add the most recent build result to the builder
    addStatus(builders) {
        for (let builder of Array.from(builders)) {
            let latest = null;
            for (let build of Array.from(builder.builds)) {
                latest = build;
                if (build.number > latest.number) { latest = build; }
            }
            builder.started_at = latest != null ? latest.started_at : undefined;
            builder.complete = (latest != null ? latest.complete : undefined) || false;
            builder.results = latest != null ? latest.results : undefined;
        }
    }

    filterBuilders(builders) {
        const ret = [];
        for (let builder of Array.from(builders)) {
            if (builder.builds != null ? builder.builds.length : undefined) {
                ret.push(builder);
            }
        }
        return ret;
    }
}


angular.module('waterfall_view')
.service('dataProcessorService', [DataProcessor]);
