const pug = require('pug');
const path = require('path')
var loaderUtils = require("loader-utils");

/* ultra simple loader that only support our simple usecase 
  pug-loader is much more complicated, but do support lot of features, 
  including require inside template, which we don't really need.
*/

module.exports = function() {
  var fn = this.resourcePath;
  var code = pug.compileFile(fn);
  content = code();
	var libraryName = loaderUtils.getOptions(this).libraryName;

  // compute template name (legacy scheme)
  tpl_name = path.parse(fn).name.replace(/.tpl$/,'') + ".html";
  if (libraryName != "buildbot-www") {
    tpl_name = libraryName + "/" + tpl_name;
  }
  // search for custom_templates (we use T as a short name to avoid consume to much bytes)
  content = `module.exports = window.T['${tpl_name}'] || ${JSON.stringify(content)};`;
  return content;
}