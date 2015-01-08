class Settings extends Controller
    constructor: ($scope, config, fieldsService) ->
        # All settings definition
        # 
        
        $scope.settings1 = true
        $scope.settings5 = "Here is a test"
        $scope.val = "First choice"
        $scope.settings = 
            settings1: fieldsService.checkbox("Settings 1", $scope.settings1)
            settings2: fieldsService.checkbox("Settings 2")
            settings3: fieldsService.radio("Settings 3", $scope.val, "First choice", "Second choice", "Third choice")
            settings4: fieldsService.radio("Settings 4", true, "First choice", "Second choice")
            settings5: fieldsService.input("Settings 5", $scope.settings5)

