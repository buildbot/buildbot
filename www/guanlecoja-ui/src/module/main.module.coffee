# first thing, we install underscore.string inside lodash
_.mixin(_.str.exports())

angular.module("guanlecoja.ui", ["ui.bootstrap", "ui.router"])
