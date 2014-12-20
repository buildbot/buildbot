'use strict';

var gulp = require('gulp'),
coffee = require('gulp-coffee'),
browserify = require('gulp-browserify'),
rename = require('gulp-rename'),
gutil = require('gulp-util'),
uglify = require('gulp-uglify'),
replace = require('gulp-replace');

gulp.task('scripts', function(){
	return gulp.src('main.coffee')
	.pipe(coffee()).on('error', gutil.log)
	.pipe(gulp.dest('.'));
});

gulp.task('vendors', function(){
	return gulp.src('vendors.coffee',  { read: false })
    .pipe(browserify({
      transform: ['coffeeify'],
      extensions: ['.coffee'],
	  builtins: false,
	  commondir: false,
	  detectGlobals: false,
	  insertGlobals : false,
          // those packages need to access files from the package
	  exclude: ['readline', 'karma', 'mime', 'body-parser', 'consolidate'],
      ignore: ['./lib-cov/connect'],
	}))
	.on('error', gutil.log)
	.pipe(replace(/var pkg = require\(path/, 'var pkg = {version:"1"}; //'))
    .pipe(rename('vendors.js'))
//    .pipe(uglify())
	.pipe(gulp.dest('.'));
});

gulp.task('watch', function()
{
	return gulp.watch('main.coffee', ['scripts']);
});
gulp.task('watch2', function()
{
	return gulp.watch('vendors.coffee', ['vendors']);
});
gulp.task('default', ['scripts', 'vendors', 'watch', 'watch2']);
