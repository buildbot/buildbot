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
        '.temp/scripts/libs/**'
        '.temp/scripts/*.js'
        '.temp/scripts/*.js.map'
    ]