class State extends Config
    constructor: ($stateProvider) ->
        $stateProvider.state "builder.forcebuilder",
            url: "/force/:scheduler",
            ### @ngInject ###
            onEnter: ($stateParams, $state, $modal) ->
                modal = {}
                modal.modal = $modal.open
                    templateUrl: "views/forcedialog.html"
                    controller: 'forceDialogController'
                    resolve:
                        builderid: -> $stateParams.builder
                        schedulerid: -> $stateParams.scheduler
                        modal: -> modal

                # We exit the state if the dialog is closed or dismissed
                goBuild = (result) ->
                    [ buildsetid, brids ] = result
                    buildernames = _.keys(brids)
                    if buildernames.length == 1
                        $state.go "buildrequest",
                            buildrequest: brids[buildernames[0]]
                            redirect_to_build: true
                goUp = (result) ->
                    $state.go "^",

                modal.modal.result.then(goBuild, goUp)
