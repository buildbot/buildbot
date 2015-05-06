invert_constant = (constant_name, inverted_constant_name) ->
    angular.module('common').service inverted_constant_name, [constant_name, (original) ->
        return _.invert(original)
    ]

class Baseurlapi extends Constant('common')
    constructor: ->
        return 'api/v2/'

class Baseurlws extends Constant('common')
    constructor: ->
        href = location.href.toString()
        if location.hash != ""
            href = href.replace(location.hash, "")
        if href[href.length - 1] != "/"
            href = href + "/"

        return href.replace(/^http/, "ws") + "ws"

class Plurals extends Constant('common')
    constructor: ->
        return {
            build: "builds"
            builder: "builders"
            buildset: "buildsets"
            buildrequest: "buildrequests"
            buildslave: "buildslaves"
            master: "masters"
            change: "changes"
            step: "steps"
            log: "logs"
            logchunk: "logchunks"
            forcescheduler: "forceschedulers"
            scheduler: "schedulers"
            spec: "specs"
            property: "properties"
        }
invert_constant('PLURALS', 'SINGULARS')

class Results extends Constant('common')
    constructor: ->
        return {
            SUCCESS: 0
            WARNINGS: 1
            FAILURE: 2
            SKIPPED: 3
            EXCEPTION: 4
            RETRY: 5
            CANCELLED: 6
        }
invert_constant('RESULTS', 'RESULTS_TEXT')
