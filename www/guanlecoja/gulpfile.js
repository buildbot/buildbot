gulp = require("gulp")
coffee = require("gulp-coffee")
gutil = require("gulp-util")
gulp.task("scripts", function(){
	gulp.src("main.coffee")
	.pipe(coffee()).on('error', gutil.log)
	.pipe(gulp.dest("."))
})
gulp.task("watch", function()
{
	return gulp.watch("main.coffee", ["scripts"])
});
gulp.task("default", ["scripts", "watch"])