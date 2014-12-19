class Settings extends Controller
    constructor: ($scope, config, fieldsService) ->
        # All settings definition
        # 
        
        $scope.settings = 
            settings1: fieldsService.checkbox("Settings 1")
            settings2: fieldsService.checkbox("Settings 2")
            settings3: fieldsService.radio("Settings 3")
