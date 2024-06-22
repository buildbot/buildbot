/*
  This file is part of Buildbot.  Buildbot is free software: you can
  redistribute it and/or modify it under the terms of the GNU General Public
  License as published by the Free Software Foundation, version 2.

  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
  FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
  details.

  You should have received a copy of the GNU General Public License along with
  this program; if not, write to the Free Software Foundation, Inc., 51
  Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

  Copyright Buildbot Team Members
*/

// The browser list here must correspond to the browser list in
// babel config which is located at vite.config.ts
outdatedBrowserRework({
   browserSupport: {
       'Chrome': 56, // Includes Chrome for mobile devices
       'Chromium': 56, // same as Chrome, but needs to be listed explicitly
                       // (https://github.com/mikemaccana/outdated-browser-rework/issues/49)
       'Edge': 15,
       'Safari': 10,
       'Mobile Safari': 10,
       'Firefox': 54,
       'Opera': 43, // uses Chrome 56 internally
       'IE': false
   },
   requireChromeOnAndroid: false,
   isUnknownBrowserOK: true,
});
