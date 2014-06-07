### ###############################################################################################
#
#   Compile LESS files to CSS
#
### ###############################################################################################
module.exports =

    # Compile with source map
    dev:
        options:
            sourceMap: true
        files: [
            src: '<%= files.less %>'
            dest: '.temp/styles/main.css'
        ]

    # Compress output using clean-css
    prod:
        options:
            cleancss: true
        files: [
            src: '<%= files.less %>'
            dest: '.temp/styles/main.css'
        ]