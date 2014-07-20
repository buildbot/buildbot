module.exports = (grunt) ->

    ### ###########################################################################################
    #   Custom tasks
    ### ###########################################################################################

    grunt.registerTask 'dataspec', ->
        done = @async()
        grunt.util.spawn
            cmd: "buildbot"
            args: "dataspec -o .temp/scripts/test/dataspec.js -g dataspec".split(" ")
        , (error, result, code) ->
            grunt.log.write result.toString()
            done(!error)

    extra_code_for_tests_tasks: ['dataspec']
