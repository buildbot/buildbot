class DataProcessor extends Service
    constructor: ->
        {}
    # Returns groups and adds builds to builders
    getGroups: (builders, builds, threshold) ->
        # Sort builds by buildid
        builds.sort (a, b) -> a.buildid - b.buildid
        # Create groups: ignore periods when builders are idle
        groups = []

        groupid = -1
        last = groupid: 0, time: 0
        # Create empty builds array for all the builders
        for builder in builders
            builder.builds = []
        for build in builds
            builder = builders.get(build.builderid)
            if not builder? or not builder.builds
                # builder is filtered, so we don't take its build in account
                continue
            # Group number starts from 0, for the first time the condition is always true
            ++groupid if build.started_at - last.time > threshold

            # Create new object for a group with the minimum time
            groups[groupid] ?= min: build.started_at
            # Add maximum time to the group object when the groupid is increased
            if last.groupid isnt groupid
                groups[last.groupid].max = last.time

            if not build.complete then build.complete_at = Math.round(new Date() / 1000)
            build.groupid = last.groupid = groupid
            builder = builders.get(build.builderid)
            builder.builds.push(build)

            if build.complete_at > last.time then last.time = build.complete_at
        # The last group maximum time
        if groups[last.groupid]
            groups[last.groupid].max = last.time
        return groups

    # Add the most recent build result to the builder
    addStatus: (builders) ->
        for builder in builders
            latest = null
            for build in builder.builds
                latest = build
                if build.number > latest.number then latest = build
            builder.started_at = latest?.started_at
            builder.complete = latest?.complete or false
            builder.results = latest?.results

    filterBuilders: (builders) ->
        ret = []
        for builder in builders
            if builder.builds?.length
                ret.push(builder)
        return ret
