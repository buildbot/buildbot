angular.module('buildbot.builders').config [ "$stateProvider", ($stateProvider) ->
    $stateProvider.state "builder.forcebuilder",
        url: "/force/:scheduler",
        onEnter: ["$stateParams", "$state", "$modal", "buildbotService"
            ($stateParams, $state, $modal, buildbotService) ->
                scheduler = buildbotService.one('forceschedulers', $stateParams.scheduler)
                scheduler.get().then (scheduler_data) ->
                    modal = {}
                    modal.modal = $modal.open
                        templateUrl: "views/forcedialog.html"
                        controller: 'forceDialogController'
                        resolve:
                            builderid: -> $stateParams.builder
                            scheduler: -> scheduler
                            scheduler_data: -> scheduler_data
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
            ]
]
