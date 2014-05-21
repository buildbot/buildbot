### ###############################################################################################
#
#   Compresses images
#
### ###############################################################################################
module.exports =

    compress:
        options:
            optimizationLevel: 7
        files: [
            src: '<%= files.images %>'
            dest: '<%= dir.temp %>/img'
            expand: true
            flatten: true
        ]