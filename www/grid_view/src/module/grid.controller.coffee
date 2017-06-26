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

        settings = bbSettingsService.getSettingsGroup('Grid')
        @revisionLimit = settings.revisionLimit.value
        @changeFetchLimit = settings.changeFetchLimit.value
        @buildFetchLimit = settings.buildFetchLimit.value
        @compactChanges = settings.compactChanges.value

        @buildsets = @data.getBuildsets(
            limit: @changeFetchLimit
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

        changesByBSID = {}
        @$scope.changes = []
        branches = {}

        changesBySSID = {}
        for c in @changes
            changesBySSID[c.sourcestamp.ssid] = c

        for bset in @buildsets
            change = changesBySSID[_.last(bset.sourcestamps).ssid]
            unless change?
                continue
            change.bsid = bset.bsid
            change.branch ?= 'master'
            branches[change.branch] = true

            if @$scope.changes.length > @revisionLimit
                continue
            if @branch and change.branch != @branch
                continue

            @$scope.changes.push(change)
            changesByBSID[bset.bsid] = change

        @$scope.changes.sort((a, b) -> a.bsid - b.bsid)

        @$scope.branches = (br for br of branches)

        requestsByBSID = {}
        for req in @buildrequests
            (requestsByBSID[req.buildsetid] ?= []).push(req)
        buildByReqID = {}
        for build in @builds
            buildByReqID[build.buildrequestid] = build

        for builder in @builders
            builder.builds = {}

        buildersById = {}
        # find builds for the selected changes and associate them to builders
        for c in @$scope.changes
            requests = requestsByBSID[c.bsid]
            unless requests?
                continue
            for req in requests
                build = buildByReqID[req.buildrequestid]
                unless build?
                    continue
                builder = @builders.get(build.builderid)
                unless @isBuilderDisplayed(builder)
                    continue
                buildersById[builder.builderid] = builder
                builder.builds[c.bsid] = build

        @$scope.builders = (buildersById[i] for i of buildersById)

    changeBranch: (branch) =>
        @branch = branch
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

        params =
            branch: @$stateParams.branch
            tag: @$stateParams.tag

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
