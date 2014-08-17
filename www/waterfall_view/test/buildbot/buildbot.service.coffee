###
# Test data
###
builders = [
    builderid: 1
    name: 'builder1'
,
    builderid: 2
    name: 'builder2'
,
    builderid: 3
    name: 'builder3'
,
    builderid: 4
    name: 'builder4'
]

builds = [
    buildid: 1
    builderid: 1
    started_at: 1403059709
    complete_at: 1403059772
    complete: true
    results: 'success'
,
    buildid: 2
    builderid: 2
    buildrequestid: 1
    started_at: 1403059802
    complete_at: 1403060287
    complete: true
    results: 'success'
,
    buildid: 3
    builderid: 2
    buildrequestid: 2
    started_at: 1403059710
    complete_at: 1403060278
    complete: true
    results: 'failure'
,
    buildid: 4
    builderid: 3
    buildrequestid: 2
    started_at: 1403060250
    complete_at: 0
    complete: false
]

buildrequests = [
    builderid: 1
    buildrequestid: 1
    buildsetid: 1
,
    builderid: 1
    buildrequestid: 2
    buildsetid: 1
,
    builderid: 1
    buildrequestid: 3
    buildsetid: 2
]

# Mocked buildbot service
class Buildbot extends Service('common')
    constructor: ($q, $timeout) ->
        @some = (string, options) ->
            deferred = $q.defer()
            resolve = ->
                switch string
                    when 'builds' then deferred.resolve builds[0..options.limit-1]
                    when 'builders' then deferred.resolve builders[0..options.limit-1]
                    when 'buildrequests' then deferred.resolve buildrequests[0..options.limit-1]
                    else deferred.resolve []
            $timeout(resolve, 100)
            bind: (scope) ->
                deferred.promise.then (b) ->
                    scope[string] = b
                deferred.promise
            getSome: ->
                deferred.promise
        @all = (string) =>
            deferred = $q.defer()
            switch string
                when 'builds' then deferred.resolve builds
                when 'builders' then deferred.resolve builders
                when 'buildrequests' then deferred.resolve buildrequests
                else
                    deferred.resolve []
            bind: (scope) ->
                deferred.promise
            getList: ->
                deferred.promise

        for build in builds
            build.all = (string) ->
                deferred = $q.defer()
                # TODO sample data (eg. steps)
                deferred.resolve []
                bind: -> deferred.promise
