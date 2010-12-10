# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

#! /usr/bin/python
from slides import Lecture, NumSlide, Slide, Bullet, SubBullet, PRE, URL

class Raw:
    def __init__(self, title, html):
        self.title = title
        self.html = html
    def toHTML(self):
        return self.html

class HTML(Raw):
    def __init__(self, html):
        self.html = html

lecture = Lecture(
    "BuildBot: Build/Test Automation",
    Slide("The BuildBot: Build/Test Automation",
          Bullet("Home page: ",
                 URL("http://buildbot.sourceforge.net/"),
                 ),
          Bullet("Brian Warner  < warner-buildbot @ lothar . com >"),
          ),

    # quick description of what it does
    # motivation: what is the problem it is trying to solve
    # architecture: master+slaves
    # design
    #  starting the build: changes, tree-stable timers
    #  doing the build: builders, processes
    #  describing the build: status
    #  status clients
    # configuration: examples of Step, setup script
    # demos: glib, show twisted status page
    # future directions
    # current status, availability, more info

    Slide("Overview",
          Bullet("What is the BuildBot?"),
          Bullet("Motivation: What problem is it trying to solve?"),
          Bullet("Architecture: What does it look like?"),
          Bullet("Design: How does it work?"),
          Bullet("Configuration: How do I make it do my bidding?"),
          Bullet("Demo: Show me the code!"),
          Bullet("Future Directons: What will it do in the future?"),
          Bullet("More Information: How do I find out more?"),
          ),

    # description
    Slide("Automating the Compile/Test cycle",
          Bullet("CVS commits trigger new builds"),
          Bullet("Builds run on multiple machines to cover various platforms and environments"),
          Bullet("Builds include running tests"),
          Bullet("Build status easy to retrieve, can be pushed to developers"),
          Bullet("inspired by Tinderbox"),
          ),

    # motivation
    Slide("Distributed cross-platform projects are tricky",
          Bullet("Distance means poor communication"),
          Bullet("Size leads to specialization: " + \
                 "Not everyone knows the whole tree"),
          Bullet("Multiple platforms: hard to do sufficient testing"),
          Bullet("Somebody has to keep it all working"),
          ),
    # personal experience as chief harassment officer
    
    Slide("Automating away the job of 'Build Sheriff'",
          Bullet("Give quick feedback about build problems"),
          Bullet("minimize inconvenience to other developers"),
          Bullet("provide (gentle) incentive to fix bugs"),
          Bullet("provide (less gentle) encouragement to fix bugs"),
          Bullet("provide (outright hostile) harassment to STOP BREAKING STUFF!"),
          Bullet("Help developers to Do The Right Thing"),
          ),

    Slide("Features",
          Bullet("Runs builds (and tests) when code is changed, report failures quickly"),
          Bullet("Performs tests on a variety of slave platforms"),
          Bullet("Handles arbitrary build processes: C, Python, Perl, etc"),
          Bullet("Status delivery through web page, email, other protocols"),
          Bullet("Track builds in progress, provide estimated completion time"),
          Bullet("Flexible configuration by subclassing generic build process classes"),
          Bullet("Minimal host requirements: Python and Twisted"),
          Bullet("Released under the GPL"),
          ),
                 
    # master and slaves
    # slaves can be behind a firewall if they can still do checkout
    Raw("Architecture",
        """<h2>Architecture</h2>
        <img src=\"../overview.png\" />
        """
        ),

    # design
    Slide("Starting the Build",
          Bullet("Changes come from the version control system",
                 SubBullet("CVSToys listener"),
                 SubBullet("Parse cvs-commit email"),
                 ),
          Bullet("Builders wait for tree to be stable"),
          Bullet("Builders can ignore some files which won't affect the build",
                 SubBullet("Documentation files"),
                 SubBullet("Example code"),
                 ),
          ),

    Slide("Running a Build",
          Bullet("Build class defines each kind of build process",
                 SubBullet("Quick vs. clobber"),
                 SubBullet("Optimized vs. debug"),
                 SubBullet("Different versions of python, gcc, etc"),
                 ),
          Bullet("Sequence of Steps: CVS, Compile, Test",
                 SubBullet("Steps defined by subclasses of BuildStep"),
                 SubBullet("Steps invoke RemoteCommands on a connected slave"),
                 ),
          Bullet("Each Builder attaches to a BuildSlave (by name)"),
          ),
    
    Slide("Describing the Build",
          Bullet("Overall Status: success, fail, in-between"),
          Bullet("Each step has status text, color, log files"),
          Bullet("Progress events are distributed to HTML logger and status clients"),
          ),

    Raw("HTML Build Status",
        """
        <img src="../waterfall.png" alt="waterfall display" width="323" height="457" align="right" />

        <h2>HTML Build Status</h2>
        <ul>
        <li>web server listens on arbitrary port</li>
        <li>waterfall display shows time, commits, build results</li>
        <li>Log files and build information are available through links</li>
        <li>Alternate displays with different URLs</li>
        </ul>
        """
        ),
          
    Slide("Status Delivery",
          Bullet("Build progress and status is given to a delivery object ..",
                 SubBullet(".. which can distribute it through arbitrary protocols"),
                 ),
          Bullet("HTML logger stores events, uses them to build waterfall display"),
          Bullet("PB-based real-time status client",
                 SubBullet("Shows current activity, Time-Remaining for current build"),
                 ),
          ),


    Slide("Configuration",
          Bullet("Everything driven by the buildmaster"),
          # minimal slave setup: buildmaster location, dir, name/pw
          Bullet("Classes provided for common build processes",
                 SubBullet("autoconf (C)"),
                 SubBullet("Makefile.PL (perl)"),
                 ),
          Bullet("Other BuildProcesses created by making subclasses"),
          ),
    
    Slide("Demo",
          Bullet("glib-1.2.10: simple C module with several self-tests"),
          Bullet("python: Twisted BuildBot instance"),
          ),
    
    Slide("Future Projects",
          Bullet("Status Delivery through other protocols",
                 SubBullet("Email with build results and logfiles"),
                 SubBullet("IRC notification, interactive status queries"),
                 SubBullet("panel applet with highly summarized status"),
                 ),
          Bullet("Tracking test failures, history of each test"),
          Bullet("Project-specific blame assignment, owner notification"),
          Bullet("Web-based Builder Configuration"),
          Bullet("bug-tracking integration"),
          Bullet("'try': run tests on not-yet-committed changes"),
          ),

    Slide("More Information",
          Bullet("Home Page: ",
                 URL("http://buildbot.sourceforge.net/")),
          Bullet("Sourceforge project page",
                 SubBullet("This paper and slides"),
                 SubBullet("Source available in CVS"),
                 SubBullet("Mailing list"),
                 SubBullet("Pointers to existing installations"),
                 ),
          Bullet("Please join the mailing list to find out about releases"),
          ),
    
    
    )

lecture.renderHTML("slides", "slide-%02d.html", css="main.css")
