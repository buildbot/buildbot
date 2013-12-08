angular.module('app').directive 'forcedialogbutton', ["buildbotService", "$modal", (buildbotService, $modal) ->
    restrict: 'E'
    link : (scope, elem, attrs) ->
        #TODO: add service method that allows for fetching a single scheduler by name
        #buildbotService.all('forceschedulers').getList().then (schedulers) ->
        scheduler = buildbotService.one('forceschedulers', attrs.scheduler)
        scheduler.get().then (schedulers) ->
#            scheduler = null
#            for scheduler in schedulers
#                if scheduler.name == attrs.scheduler
#                    break
            elem.on 'click', () ->
                prepareFields = (fields) ->
                    for field in fields
                        if field.type == "nested"
                            prepareFields(field.fields)
                        else
                            field.value = field.default
                prepareFields(schedulers[0].all_fields)
                modal = {}
                modal.modal = $modal.open({
                    templateUrl: "views/directives/forcedialog.html"
                    #TODO: consider not declaring this inline, but rather by name (string), for unit testing..
                    controller: [ "$scope", "$rootScope"
                        ($scope, $rootScope) ->
                            angular.extend $scope,
                                rootfield:
                                    type: "nested"
                                    layout: "simple"
                                    fields: schedulers[0].all_fields
                                    columns: 1
                                sch: schedulers[0]
                                ok: ->
                                    params =
                                        builderid: attrs.builder
                                    fields_ref = {}
                                    gatherFields = (fields) ->
                                        for field in fields
                                            field.errors = ""
                                            if field.type == "nested"
                                                gatherFields(field.fields)
                                            else
                                                params[field.fullName] = field.value
                                                fields_ref[field.fullName] = field

                                    gatherFields(schedulers[0].all_fields)
                                    scheduler.control("force", params)
                                    .then (res) ->
                                            modal.modal.close(res)
                                        ,   (err) ->
                                            if err.data.error.code == -32602
                                                for k, v of err.data.error.message
                                                    fields_ref[k].errors = v
                                            $rootScope.$apply()
                                cancel: ->
                                    modal.modal.dismiss()
                    ]
                })
]

