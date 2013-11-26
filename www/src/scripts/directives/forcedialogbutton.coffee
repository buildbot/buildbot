angular.module('app').directive 'forcedialogbutton', ["buildbotService", "$modal", (buildbotService, $modal) ->
    restrict: 'E'
    link : (scope, elem, attrs) ->

        #TODO: add service method that allows for fetching a single scheduler by name
        buildbotService.all('forceschedulers').getList().then (schedulers) ->

            scheduler = null
            for scheduler in schedulers
                if scheduler.name == attrs.scheduler
                    break

            elem.on 'click', () ->
                modal = {}
                modal.modal = $modal.open({
                    templateUrl: "views/directives/forcedialog.html"
                    #TODO: consider not declaring this inline, but rather by name (string), for unit testing..
                    controller: [ "$scope",
                        ($scope) ->
                            angular.extend $scope,
                                sch: scheduler
                                ok: ->
                                    modal.modal.close()
                                cancel: ->
                                    modal.modal.close()
                    ]
                })
]

