### ###############################################################################################
#
#   Clean files and folders
#   Before generating files, remove any previously-created files
#
### ###############################################################################################
module.exports =

    options:
        force: true
    scripts: [
        '<%= dir.temp %>/scripts/libs/**'
        '<%= dir.temp %>/scripts/*.js'
        '<%= dir.temp %>/scripts/*.js.map'
    ]