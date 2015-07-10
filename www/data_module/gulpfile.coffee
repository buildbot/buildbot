################################################################################
#   Gulp
################################################################################

gulp = require('gulp')
# gulp plugins & dependencies
p = require('gulp-load-plugins')()
del = require('del')
# scoped release tasks for gulp
require('gulp-release-tasks')(gulp)

################################################################################
#   Arguments
################################################################################

# --watch
WATCH = p.util.env.watch?

################################################################################
#   Configuration
################################################################################

c =
    fileName: 'buildbot-data'
    karma:
        action: if WATCH then 'watch' else 'run'
        configFile: 'karma.conf.coffee'
    classify:
        appName: 'bbData'
        provider:
          suffix: 'Service'

paths =
    src: 'src'
    build: 'dist'

files =
    coffee: [
        "#{paths.src}/**/*.module.coffee"
        "#{paths.src}/**/!(*.spec).coffee"
    ]

################################################################################
#   Tasks
################################################################################

gulp.task 'clean', (cb) ->
    del paths.build, cb

gulp.task 'build', ['clean'], ->
    gulp.src files.coffee
    .pipe p.ngClassify(c.classify)
    .pipe p.coffee()
    .pipe p.ngAnnotate()
    .pipe p.concat("#{c.fileName}.js")
    .pipe gulp.dest(paths.build)
    .pipe p.uglify()
    .pipe p.rename("#{c.fileName}.min.js")
    .pipe gulp.dest(paths.build)

gulp.task 'test', ['bower'], ->
    # pass in a directory that doesn't exist
    # karma will use the files specified in the configuration
    gulp.src('test')
    .pipe p.karma(c.karma)

gulp.task 'watch', ->
    if WATCH
        gulp.watch files.coffee, ['build']

gulp.task 'bower', -> return p.bower()

gulp.task 'default', ['clean', 'test', 'build', 'watch']
