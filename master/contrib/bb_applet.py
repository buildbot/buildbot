#! /usr/bin/python

# This is a Gnome-2 panel applet that uses the
# buildbot.status.client.PBListener interface to display a terse summary of
# the buildmaster. It displays one column per builder, with a box on top for
# the status of the most recent build (red, green, or orange), and a somewhat
# smaller box on the bottom for the current state of the builder (white for
# idle, yellow for building, red for offline). There are tooltips available
# to tell you which box is which.

# Edit the line at the beginning of the MyApplet class to fill in the host
# and portnumber of your buildmaster's PBListener status port. Eventually
# this will move into a preferences dialog, but first we must create a
# preferences dialog.

# See the notes at the end for installation hints and support files (you
# cannot simply run this script from the shell). You must create a bonobo
# .server file that points to this script, and put the .server file somewhere
# that bonobo will look for it. Only then will this applet appear in the
# panel's "Add Applet" menu.

# Note: These applets are run in an environment that throws away stdout and
# stderr. Any logging must be done with syslog or explicitly to a file.
# Exceptions are particularly annoying in such an environment.

#   -Brian Warner, warner@lothar.com

if 0:
    import sys
    dpipe = open("/tmp/applet.log", "a", 1)
    sys.stdout = dpipe
    sys.stderr = dpipe
    print "starting"

from twisted.internet import gtk2reactor
gtk2reactor.install() #@UndefinedVariable

import gtk #@UnresolvedImport
import gnomeapplet #@UnresolvedImport

# preferences are not yet implemented
MENU = """
<popup name="button3">
 <menuitem name="Connect" verb="Connect" label="Connect"
           pixtype="stock" pixname="gtk-refresh"/>
 <menuitem name="Disconnect" verb="Disconnect" label="Disconnect"
           pixtype="stock" pixname="gtk-stop"/>
 <menuitem name="Prefs" verb="Props" label="_Preferences..."
           pixtype="stock" pixname="gtk-properties"/>
</popup>
"""

from twisted.spread import pb
from twisted.cred import credentials

# sigh, these constants should cross the wire as strings, not integers
SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION = range(5)
Results = ["success", "warnings", "failure", "skipped", "exception"]


class Box:

    def __init__(self, buildername, hbox, tips, size, hslice):
        self.buildername = buildername
        self.hbox = hbox
        self.tips = tips
        self.state = "idle"
        self.eta = None
        self.last_results = None
        self.last_text = None
        self.size = size
        self.hslice = hslice

    def create(self):
        self.vbox = gtk.VBox(False)
        l = gtk.Label(".")
        self.current_box = box = gtk.EventBox()
        # these size requests are somewhat non-deterministic. I think it
        # depends upon how large label is, or how much space was already
        # consumed when the box is added.
        self.current_box.set_size_request(self.hslice, self.size * 0.75)
        box.add(l)
        self.vbox.pack_end(box)
        self.current_box.modify_bg(gtk.STATE_NORMAL,
                                   gtk.gdk.color_parse("gray50"))

        l2 = gtk.Label(".")
        self.last_box = gtk.EventBox()
        self.current_box.set_size_request(self.hslice, self.size * 0.25)
        self.last_box.add(l2)
        self.vbox.pack_end(self.last_box, True, True)
        self.vbox.show_all()
        self.hbox.pack_start(self.vbox, True, True)

    def remove(self):
        self.hbox.remove(self.box)

    def set_state(self, state):
        self.state = state
        self.update()

    def set_eta(self, eta):
        self.eta = eta
        self.update()

    def set_last_build_results(self, results):
        self.last_results = results
        self.update()

    def set_last_build_text(self, text):
        self.last_text = text
        self.update()

    def update(self):
        currentmap = {"offline": "red",
                      "idle": "white",
                      "waiting": "yellow",
                      "interlocked": "yellow",
                      "building": "yellow",
        }
        color = currentmap[self.state]
        self.current_box.modify_bg(gtk.STATE_NORMAL,
                                   gtk.gdk.color_parse(color))
        lastmap = {None: "gray50",
                   SUCCESS: "green",
                   WARNINGS: "orange",
                   FAILURE: "red",
                   EXCEPTION: "purple",
                   }
        last_color = lastmap[self.last_results]
        self.last_box.modify_bg(gtk.STATE_NORMAL,
                                gtk.gdk.color_parse(last_color))
        current_tip = "%s:\n%s" % (self.buildername, self.state)
        if self.eta is not None:
            current_tip += " (ETA=%ds)" % self.eta
        self.tips.set_tip(self.current_box, current_tip)
        last_tip = "%s:\n" % self.buildername
        if self.last_text:
            last_tip += "\n".join(self.last_text)
        else:
            last_tip += "no builds"
        self.tips.set_tip(self.last_box, last_tip)


class MyApplet(pb.Referenceable):
    # CHANGE THIS TO POINT TO YOUR BUILDMASTER
    buildmaster = "buildmaster.example.org", 12345
    filled = None

    def __init__(self, container):
        self.applet = container
        self.size = container.get_size()
        self.hslice = self.size / 4
        container.set_size_request(self.size, self.size)
        self.fill_nut()
        verbs = [("Props", self.menu_preferences),
                 ("Connect", self.menu_connect),
                 ("Disconnect", self.menu_disconnect),
        ]
        container.setup_menu(MENU, verbs)
        self.boxes = {}
        self.connect()

    def fill(self, what):
        if self.filled:
            self.applet.remove(self.filled)
            self.filled = None
        self.applet.add(what)
        self.filled = what
        self.applet.show_all()

    def fill_nut(self):
        i = gtk.Image()
        i.set_from_file("/tmp/nut32.png")
        self.fill(i)

    def fill_hbox(self):
        self.hbox = gtk.HBox(True)
        self.fill(self.hbox)

    def connect(self):
        host, port = self.buildmaster
        cf = pb.PBClientFactory()
        creds = credentials.UsernamePassword("statusClient", "clientpw")
        d = cf.login(creds)
        reactor.connectTCP(host, port, cf)
        d.addCallback(self.connected)
        return d

    def connected(self, ref):
        print "connected"
        ref.notifyOnDisconnect(self.disconnected)
        self.remote = ref
        self.remote.callRemote("subscribe", "steps", 5, self)
        self.fill_hbox()
        self.tips = gtk.Tooltips()
        self.tips.enable()

    def disconnect(self):
        self.remote.broker.transport.loseConnection()

    def disconnected(self, *args):
        print "disconnected"
        self.fill_nut()

    def remote_builderAdded(self, buildername, builder):
        print "builderAdded", buildername
        box = Box(buildername, self.hbox, self.tips, self.size, self.hslice)
        self.boxes[buildername] = box
        box.create()
        self.applet.set_size_request(self.hslice * len(self.boxes),
                                     self.size)
        d = builder.callRemote("getLastFinishedBuild")

        def _got(build):
            if build:
                d1 = build.callRemote("getResults")
                d1.addCallback(box.set_last_build_results)
                d2 = build.callRemote("getText")
                d2.addCallback(box.set_last_build_text)
        d.addCallback(_got)

    def remote_builderRemoved(self, buildername):
        self.boxes[buildername].remove()
        del self.boxes[buildername]
        self.applet.set_size_request(self.hslice * len(self.boxes),
                                     self.size)

    def remote_builderChangedState(self, buildername, state, eta):
        self.boxes[buildername].set_state(state)
        self.boxes[buildername].set_eta(eta)
        print "change", buildername, state, eta

    def remote_buildStarted(self, buildername, build):
        print "buildStarted", buildername

    def remote_buildFinished(self, buildername, build, results):
        print "buildFinished", results
        box = self.boxes[buildername]
        box.set_eta(None)
        d1 = build.callRemote("getResults")
        d1.addCallback(box.set_last_build_results)
        d2 = build.callRemote("getText")
        d2.addCallback(box.set_last_build_text)

    def remote_buildETAUpdate(self, buildername, build, eta):
        self.boxes[buildername].set_eta(eta)
        print "ETA", buildername, eta

    def remote_stepStarted(self, buildername, build, stepname, step):
        print "stepStarted", buildername, stepname

    def remote_stepFinished(self, buildername, build, stepname, step, results):
        pass

    def menu_preferences(self, event, data=None):
        print "prefs!"
        p = Prefs(self)
        p.create()

    def set_buildmaster(self, buildmaster):
        host, port = buildmaster.split(":")
        self.buildmaster = host, int(port)
        self.disconnect()
        reactor.callLater(0.5, self.connect)

    def menu_connect(self, event, data=None):
        self.connect()

    def menu_disconnect(self, event, data=None):
        self.disconnect()


class Prefs:

    def __init__(self, parent):
        self.parent = parent

    def create(self):
        self.w = w = gtk.Window()
        v = gtk.VBox()
        h = gtk.HBox()
        h.pack_start(gtk.Label("buildmaster (host:port) : "))
        self.buildmaster_entry = b = gtk.Entry()
        if self.parent.buildmaster:
            host, port = self.parent.buildmaster
            b.set_text("%s:%d" % (host, port))
        h.pack_start(b)
        v.add(h)

        b = gtk.Button("Ok")
        b.connect("clicked", self.done)
        v.add(b)

        w.add(v)
        w.show_all()

    def done(self, widget):
        buildmaster = self.buildmaster_entry.get_text()
        self.parent.set_buildmaster(buildmaster)
        self.w.unmap()


def factory(applet, iid):
    MyApplet(applet)
    applet.show_all()
    return True


from twisted.internet import reactor

# instead of reactor.run(), we do the following:
reactor.startRunning()
reactor.simulate()
gnomeapplet.bonobo_factory("OAFIID:GNOME_Buildbot_Factory",
                           gnomeapplet.Applet.__gtype__,
                           "buildbot", "0", factory)

# code ends here: bonobo_factory runs gtk.mainloop() internally and
# doesn't return until the program ends

# SUPPORTING FILES:

# save the following as ~/lib/bonobo/servers/bb_applet.server, and update all
# the pathnames to match your system
bb_applet_server = """
<oaf_info>

<oaf_server iid="OAFIID:GNOME_Buildbot_Factory"
            type="exe"
            location="/home/warner/stuff/buildbot-trunk/contrib/bb_applet.py">

        <oaf_attribute name="repo_ids" type="stringv">
            <item value="IDL:Bonobo/GenericFactory:1.0"/>
            <item value="IDL:Bonobo/Unknown:1.0"/>
        </oaf_attribute>
        <oaf_attribute name="name" type="string" value="Buildbot Factory"/>
        <oaf_attribute name="description" type="string" value="Test"/>
</oaf_server>

<oaf_server iid="OAFIID:GNOME_Buildbot"
            type="factory"
            location="OAFIID:GNOME_Buildbot_Factory">

        <oaf_attribute name="repo_ids" type="stringv">
                <item value="IDL:GNOME/Vertigo/PanelAppletShell:1.0"/>
                <item value="IDL:Bonobo/Control:1.0"/>
                <item value="IDL:Bonobo/Unknown:1.0"/>
        </oaf_attribute>
        <oaf_attribute name="name" type="string" value="Buildbot"/>
        <oaf_attribute name="description" type="string"
          value="Watch Buildbot status"
        />
        <oaf_attribute name="panel:category" type="string" value="Utility"/>
        <oaf_attribute name="panel:icon" type="string"
 value="/home/warner/stuff/buildbot-trunk/doc/hexnut32.png"
 />

</oaf_server>

</oaf_info>
"""

# a quick rundown on the Gnome2 applet scheme (probably wrong: there are
# better docs out there that you should be following instead)
#  http://www.pycage.de/howto_bonobo.html describes a lot of
#   the base Bonobo stuff.
#  http://www.daa.com.au/pipermail/pygtk/2002-September/003393.html

# bb_applet.server must be in your $BONOBO_ACTIVATION_PATH . I use
# ~/lib/bonobo/servers . This environment variable is read by
# bonobo-activation-server, so it must be set before you start any Gnome
# stuff. I set it in ~/.bash_profile . You can also put it in
# /usr/lib/bonobo/servers/ , which is probably on the default
# $BONOBO_ACTIVATION_PATH, so you won't have to update anything.

# It is safest to put this in place before bonobo-activation-server is
# started, which may mean before any Gnome program is running. It may or may
# not detect bb_applet.server if it is installed afterwards.. there seem to
# be hooks, some of which involve FAM, but I never managed to make them work.
# The file must have a name that ends in .server or it will be ignored.

# The .server file registers two OAF ids and tells the activation-server how
# to create those objects. The first is the GNOME_Buildbot_Factory, and is
# created by running the bb_applet.py script. The second is the
# GNOME_Buildbot applet itself, and is created by asking the
# GNOME_Buildbot_Factory to make it.

# gnome-panel's "Add To Panel" menu will gather all the OAF ids that claim
# to implement the "IDL:GNOME/Vertigo/PanelAppletShell:1.0" in its
# "repo_ids" attribute. The sub-menu is determined by the "panel:category"
# attribute. The icon comes from "panel:icon", the text displayed in the
# menu comes from "name", the text in the tool-tip comes from "description".

# The factory() function is called when a new applet is created. It receives
# a container that should be populated with the actual applet contents (in
# this case a Button).

# If you're hacking on the code, just modify bb_applet.py and then kill -9
# the running applet: the panel will ask you if you'd like to re-load the
# applet, and when you say 'yes', bb_applet.py will be re-executed. Note that
# 'kill PID' won't work because the program is sitting in C code, and SIGINT
# isn't delivered until after it surfaces to python, which will be never.

# Running bb_applet.py by itself will result in a factory instance being
# created and then sitting around forever waiting for the activation-server
# to ask it to make an applet. This isn't very useful.

# The "location" filename in bb_applet.server must point to bb_applet.py, and
# bb_applet.py must be executable.

# Enjoy!
#  -Brian Warner
