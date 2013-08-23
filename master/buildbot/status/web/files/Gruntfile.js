module.exports = function(grunt) {

  // Configuration goes here
  grunt.initConfig({
    
    // Metadata.
    meta: {
        basePath: '/',
        srcPath: 'sass',
        deployPath: 'css'
    },
    // compass
    compass: {                  // Task
      dev: {                    // Another target
        options: {
          sassDir: '<%= meta.srcPath %>',
          cssDir: '<%= meta.deployPath %>',
          debugInfo: true,
          environment: "development"
        }
      },
      prod: {                    // Another target
        options: {
          sassDir: '<%= meta.srcPath %>',
          cssDir: 'prod/<%= meta.deployPath %>',
          environment: "production"
        }
      }
    },
    // javascript compression
    uglify: {
      my_target: {
        files: {
          'prod/script/output.min.js': ['script/jQuery.2.0.3.js','script/jquery.dataTables.js','script/select2.js','script/default.js']
        }
      }
    },
    // watch
    watch: {
      css: {
          files: [
              '<%= meta.srcPath %>/**/*.scss'
          ],
          tasks: ['compass']
      }
    }
  });

  // Load plugins here
  grunt.loadNpmTasks('grunt-contrib-compass');
  grunt.loadNpmTasks('grunt-contrib-watch');
  grunt.loadNpmTasks('grunt-contrib-uglify');

  // Define your tasks here
  grunt.registerTask('default', ['compass']);
  grunt.registerTask('default', ['uglify']);

};