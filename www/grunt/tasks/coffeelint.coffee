### ###############################################################################################
#
#   CoffeeScript lint
#   Enforce basic coding style rules
#
### ###############################################################################################
module.exports =

    scripts:
        options:
            configFile: 'grunt/coffeelint.json'
            force: 'true'
        src: [
            '<%= files.coffee %>'
            '<%= files.coffee_unit %>'
        ]