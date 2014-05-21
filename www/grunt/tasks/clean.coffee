### ###############################################################################################
#
#   Clean files and folders
#   Before generating files, remove any previously-created files
#
### ###############################################################################################
module.exports =

    options:
        force: true
    main: [
        '<%= dir.temp %>'
        '<%= dir.build %>'
    ]