angular.module('app').directive 'forcedialogbutton', ["buildbotService", "$modal", (buildbotService, $modal) ->
  restrict: 'E'
  scope: ->
  link : (scope, elem, attrs) ->

    buildbotService.all('forceschedulers').getList().then (schedulers) ->
      scheduler = null
      for scheduler in schedulers
        if scheduler.name == attrs.scheduler
          break

      elem.on 'click', () ->
        modal = {}
        modal.modal = $modal.open
          templateUrl: "views/forcedialog.html"
          controller: [ "$scope",
            ($scope) ->
              angular.extend $scope,
                sch: scheduler
                ok: ->
                  modal.modal.close()
                cancel: ->
                  modal.modal.close()
          ]
]

