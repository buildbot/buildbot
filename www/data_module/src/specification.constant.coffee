# Class specification contains the fields and paths for every root
# TODO use by indexedDBService (dbstores, processUrl)
#      generate classes
# n: number
# i: identifier
class Specification extends Constant
    constructor: -> return {
        FIELDTYPES:
            IDENTIFIER: 'i'
            NUMBER: 'n'

        builds:
            id: 'buildid'
            fields: [
                'buildid'
                'builderid'
                'buildrequestid'
                'buildslaveid'
                'complete'
                'complete_at'
                'masterid'
                'number'
                'results'
                'started_at'
                'state_string'
            ]
            root: true
            paths: [
                'changes'
                'properties'
                'steps'
                'steps/i:name'
                'steps/i:name/logs'
                'steps/i:name/logs/i:slug'
                'steps/i:name/logs/i:slug/contents'
                'steps/i:name/logs/i:slug/raw'
                'steps/n:number'
                'steps/n:number/logs'
                'steps/n:number/logs/i:slug'
                'steps/n:number/logs/i:slug/contents'
                'steps/n:number/logs/i:slug/raw'
            ]
            static:
                complete: true
        builders:
            id: 'builderid'
            identifier: 'name'
            fields: [
                'builderid'
                'description'
                'name'
                'tags'
            ]
            root: true
            paths: [
                'forceschedulers'
                'buildrequests'
                'masters'
                'masters/n:masterid'
                'buildslaves'
                'buildslaves/i:name'
                'buildslaves/n:buildslaveid'
                'builds'
                'builds/n:number'
                'builds/n:number/steps'
                'builds/n:number/steps/i:name'
                'builds/n:number/steps/i:name/logs'
                'builds/n:number/steps/i:name/logs/i:slug'
                'builds/n:number/steps/i:name/logs/i:slug/contents'
                'builds/n:number/steps/i:name/logs/i:slug/raw'
                'builds/n:number/steps/n:number'
                'builds/n:number/steps/n:number/logs'
                'builds/n:number/steps/n:number/logs/i:slug'
                'builds/n:number/steps/n:number/logs/i:slug/contents'
                'builds/n:number/steps/n:number/logs/i:slug/raw'
            ]
            static: true
        buildrequests:
            id: 'buildrequestid'
            fields: [
                'buildrequestid'
                'builderid'
                'buildsetid'
                'claimed'
                'claimed_at'
                'claimed_by_masterid'
                'complete'
                'complete_at'
                'priority'
                'results'
                'submitted_at'
                'waited_for'
            ]
            root: true
            paths: [
                'builds'
            ]
            static:
                complete: true
        buildsets:
            id: 'bsid'
            fields: [
                'bsid'
                'complete'
                'complete_at'
                'external_idstring'
                'parent_buildid'
                'parent_relationship'
                'reason'
                'results'
                'sourcestamps'
                'submitted_at'
            ]
            root: true
            paths: [
                'properties'
            ]
            static:
                complete: true
        buildslaves:
            id: 'buildslaveid'
            fields: [
                'buildslaveid'
                'configured_on'
                'connected_to'
                'name'
                'slaveinfo'
            ]
            root: true
            paths: []
            static: true
        changes:
            id: 'changeid'
            fields: [
                'changeid'
                'author'
                'branch'
                'category'
                'codebase'
                'comments'
                'files'
                'parent_changeids'
                'project'
                'properties'
                'repository'
                'revision'
                'revlink'
                'sourcestamp'
                'when_timestamp'
            ]
            root: true
            paths: []
            static: true
        changesources:
            id: 'changesourceid'
            fields: [
                'changesourceid'
                'master'
                'name'
            ]
            root: true
            paths: []
            static: true
        forceschedulers:
            id: 'name'
            fields: [
                'name'
                'all_fields'
                'builder_names'
                'label'
            ]
            root: true
            paths: []
            static: true
        masters:
            id: 'masterid'
            fields: [
                'masterid'
                'active'
                'last_active'
                'name'
            ]
            root: true
            paths: [
                'builders'
                'builders/n:builderid'
                'builders/n:builderid/buildslaves'
                'builders/n:builderid/buildslaves/n:buildslaveid'
                'builders/n:builderid/buildslaves/i:name'
                'buildslaves'
                'buildslaves/i:name'
                'buildslaves/n:buildslaveid'
                'changesources'
                'changesources/n:changesourceid'
                'schedulers'
                'schedulers/n:schedulerid'
            ]
            static: true
        schedulers:
            id: 'schedulerid'
            fields: [
                'schedulerid'
                'master'
                'name'
            ]
            root: true
            paths: []
            static: true
        sourcestamps:
            id: 'ssid'
            fields: [
                'ssid'
                'branch'
                'codebase'
                'created_at'
                'patch'
                'project'
                'repository'
                'revision'
            ]
            root: true
            paths: [
                'changes'
            ]
            static: true

        steps:
            id: 'stepid'
            identifier: 'name'
            fields: [
                'stepid'
                'buildid'
                'complete'
                'complete_at'
                'hidden'
                'name'
                'number'
                'results'
                'started_at'
                'state_string'
                'urls'
            ]
            root: false
            paths: [
                'logs'
                'logs/i:slug'
                'logs/i:slug/contents'
                'logs/i:slug/raw'
            ]
            static:
                complete: true
        logs:
            id: 'logid'
            identifier: 'slug'
            fields: [
                'logid'
                'complete'
                'name'
                'num_lines'
                'slug'
                'stepid'
                'type'
            ]
            root: false
            paths: []
            static:
                complete: true
        properties:
            id: null
            fields: [] # TODO add buildid, buildsetid (to be able to join later)
            root: false
    }
