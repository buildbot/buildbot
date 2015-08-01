class BuildInfo extends Directive

    constructor: ->
        return {
            restrict: 'E'
            templateUrl: 'views/buildinfo.html'
            controller: '_BuildInfoController'
            controllerAs: 'buildinfo'
            bindToController: true
            scope:
                build: '='
        }

class _BuildInfo extends Controller
    showRaw: false
    changesLimit: 5

    changes: []
    change_owners: []
    properties: {}
    raw_properties: {}

    constructor: ->
        @build.loadChanges().then (changes) =>
            @changes = changes
            @change_owners = @processOwners(_.uniq(change.author for change in changes))

            @build.loadProperties().then (data) =>
                @processProperties(data[0])

    processOwners: (owners = []) ->
        emailRegex = /[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*/
        return _.map owners, (owner) ->
            email = emailRegex.exec(owner) || ['']
            return {
                name: owner
                email: email[0]
            }

    processProperties: (data = {}) ->
        raw = {}
        for k, v of data
            raw[k] = {value: v[0], source: v[1]} if v and v.length == 2

        @raw_properties = raw

        display = {}
        display.owners = @change_owners || @processOwners(raw.owners?.value || [])
        display.revision = (raw.got_revision?.value || raw.revision?.value || '')[0..20]
        display.slave = raw.slavename?.value
        display.scheduler = raw.scheduler?.value
        display.dir = raw.builddir?.value || raw.worddir?.value

        @properties = display


