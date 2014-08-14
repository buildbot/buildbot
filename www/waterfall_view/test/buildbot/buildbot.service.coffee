###
   # Test data
   ###
builders = [
    builderid: 1
,
    builderid: 2
,
    builderid: 3
,
    builderid: 4
]

builds = [
    buildid: 1
    builderid: 1
    started_at: 1403059709
    complete_at: 1403059772
    complete: true
,
    buildid: 2
    builderid: 2
    buildrequestid: 1
    started_at: 1403059711
    complete_at: 1403060287
    complete: true
,
    buildid: 3
    builderid: 4
    buildrequestid: 2
    started_at: 1403059710
    complete_at: 1403060278
    complete: true
,
    buildid: 4
    builderid: 3
    buildrequestid: 2
    started_at: 1403059710
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
    constructor: ($q) ->
        @some = (string, options) ->
            deferred = $q.defer()
            switch string
                when 'builds' then deferred.resolve builds[0..options.limit]
                when 'builders' then deferred.resolve builders[0..options.limit]
                when 'buildrequests' then deferred.resolve buildrequests[0..options.limit]
                else
                    deferred.resolve []
            bind: ->
                deferred.promise
        @all = (string) =>
            deferred = $q.defer()
            switch string
                when 'builds' then deferred.resolve builds
                when 'builders' then deferred.resolve builders
                when 'buildrequests' then deferred.resolve buildrequests
                else
                    deferred.resolve []
            bind: ->
                deferred.promise
            getList: ->
                deferred.promise
