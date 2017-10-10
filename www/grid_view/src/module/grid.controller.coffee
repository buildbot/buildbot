# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

class Grid extends Controller
    constructor: (@$scope, @$stateParams, @$state, resultsService, dataService, bbSettingsService) ->
        _.mixin(@$scope, resultsService)
        @data = dataService.open().closeOnDestroy(@$scope)

        @branch = @$stateParams.branch
        @tags = @$stateParams.tag ? []
        if not angular.isArray(@tags)
            @tags = [@tags]
        @result = @$stateParams.result
        # XXX: Angular ngOptions tag only works with string values. Force
        # convert the result code to string.
        @results = ({code: c + '', text: t} for c, t of resultsService.resultsTexts)

        settings = bbSettingsService.getSettingsGroup('Grid')
        @revisionLimit = settings.revisionLimit.value
        @changeFetchLimit = settings.changeFetchLimit.value
        @buildFetchLimit = settings.buildFetchLimit.value
        @fullChanges = settings.fullChanges.value
        @leftToRight = settings.leftToRight.value

        @buildsets = @data.getBuildsets(
            limit: @buildFetchLimit
            order: '-bsid'
        )
        @changes = @data.getChanges(
            limit: @changeFetchLimit
            order: '-changeid'
        )
        @builders = @data.getBuilders()
        @buildrequests = @data.getBuildrequests(
            limit: @buildFetchLimit
            order: '-buildrequestid'
        )
        @builds = @data.getBuilds(
            limit: @buildFetchLimit
            order: '-buildrequestid'
        )

        @buildsets.onChange = @changes.onChange = @builders.onChange = \
            @buildrequests.change = @builds.onChange = @onChange

    dataReady: ->
        for collection in [@buildsets, @changes, @builders, @buildrequests, @builds]
            if not (collection.$resolved and collection.length > 0)
                return false
        return true

    dataFetched: ->
        for collection in [@buildsets, @changes, @builders, @buildrequests, @builds]
            if not collection.$resolved
                return false
        return true

    onChange: =>
        if not @dataReady()
            return

        changes = {}
        branches = {}

        # map changes by source stamp id
        changesBySSID = {}
        for c in @changes
            changesBySSID[c.sourcestamp.ssid] = c
            c.buildsets = {}  # there can be multiple buildsets by change

        # associate buildsets to each change and remember existing branches
        for bset in @buildsets
            change = changesBySSID[_.last(bset.sourcestamps).ssid]
            unless change?
                continue

            change.buildsets[bset.bsid] = bset
            change.branch ?= 'master'
            branches[change.branch] = true

            if @branch and change.branch != @branch
                continue

            changes[change.changeid] = change

        # only keep the @revisionLimit most recent changes for display
        changes = (change for own cid, change of changes)
        if @leftToRight
            changes.sort((a, b) -> a.changeid - b.changeid)
            if changes.length > @revisionLimit
                changes = changes.slice(changes.length - @revisionLimit)
        else
            changes.sort((a, b) -> b.changeid - a.changeid)
            if changes.length > @revisionLimit
                changes = changes.slice(0, @revisionLimit)
        @$scope.changes = changes

        @$scope.branches = (br for br of branches)

        requestsByBSID = {}
        for req in @buildrequests
            (requestsByBSID[req.buildsetid] ?= []).push(req)
        buildsByReqID = {}
        for build in @builds
            # There may be multiple builds for a given request
            # (for example when a worker connection is lost).
            (buildsByReqID[build.buildrequestid] ?= []).push(build)

        for builder in @builders
            builder.builds = {}

        buildersById = {}
        # find builds for the selected changes and associate them to builders
        for c in @$scope.changes
            for own bsid, bset of c.buildsets
                requests = requestsByBSID[bsid]
                unless requests?
                    continue
                for req in requests
                    builds = buildsByReqID[req.buildrequestid] ? []
                    if @result? and @result != '' and !isNaN(@result)
                        i = 0
                        while i < builds.length
                            if parseInt(builds[i].results) != parseInt(@result)
                                builds.splice(i, 1)
                            else
                                i += 1
                    unless builds.length > 0
                        continue
                    builder = @builders.get(builds[0].builderid)
                    unless @isBuilderDisplayed(builder)
                        continue
                    buildersById[builder.builderid] = builder
                    builder.builds[c.changeid] = builds

        @$scope.builders = (builder for own i, builder of buildersById)

    changeBranch: (branch) =>
        @branch = branch
        @refresh()

    changeResult: (result) =>
        @result = result
        @refresh()

    toggleTag: (tag) =>
        i = @tags.indexOf(tag)
        if i < 0
            @tags.push(tag)
        else
            @tags.splice(i, 1)
        @refresh()

    resetTags: =>
        @tags = []
        @refresh()

    refresh: =>
        @$stateParams.branch = @branch
        if @tags.length == 0
            @$stateParams.tag = undefined
        else
            @$stateParams.tag = @tags
        @$stateParams.result = @result

        params =
            branch: @$stateParams.branch
            tag: @$stateParams.tag
            result: @$stateParams.result

        # change URL without reloading page
        @$state.transitionTo(@$state.current, params, {notify: false})
        @onChange()

    isBuilderDisplayed: (builder) =>
        for tag in @tags
            if builder.tags.indexOf(tag) < 0
                return false
        return true

    isTagToggled: (tag) =>
        return @tags.indexOf(tag) >= 0
