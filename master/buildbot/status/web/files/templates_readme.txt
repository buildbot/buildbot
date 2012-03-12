This is the directory to place customized templates for webstatus.

You can find the sources for the templates used in:
buildbot/status/web/templates

You can copy any of those files to this directory, make changes, and buildbot will automatically
use your modified templates.

Also of note is that you will not need to restart/reconfig buildbot master to have these changes take effect.

The syntax of the templates is Jinja2:
http://jinja.pocoo.org/