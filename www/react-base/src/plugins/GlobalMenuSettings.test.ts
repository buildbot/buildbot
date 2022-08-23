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

import {GlobalMenuSettings} from "./GlobalMenuSettings";

describe('GlobalMenuSettings', () => {
  it("group sorting", () => {
    const settings = new GlobalMenuSettings();
    settings.addGroup({
      name: '0',
      parentName: null,
      caption: 'c0',
      route: '/0',
      icon: null,
      order: null
    });
    settings.addGroup({
      name: '1',
      parentName: null,
      caption: 'c1',
      route: '/1',
      icon: null,
      order: 10
    });
    settings.addGroup({
      name: '2',
      parentName: null,
      caption: 'c2',
      route: '/2',
      icon: null,
      order: 9
    });
    settings.addGroup({
      name: '3',
      parentName: null,
      caption: 'c3',
      route: '/3',
      icon: null,
      order: 11
    });
    settings.addGroup({
      name: '4',
      parentName: null,
      caption: 'c4',
      route: '/c4',
      icon: null,
      order: 10
    });

    expect(settings.groups).toEqual([
      {
        "caption": "c2",
        "icon": null,
        "name": "2",
        "order": 9,
        "route": "/2",
        "subGroups": []
      },
      {
        "caption": "c1",
        "icon": null,
        "name": "1",
        "order": 10,
        "route": "/1",
        "subGroups": []
      },
      {
        "caption": "c4",
        "icon": null,
        "name": "4",
        "order": 10,
        "route": "/c4",
        "subGroups": []
      },
      {
        "caption": "c3",
        "icon": null,
        "name": "3",
        "order": 11,
        "route": "/3",
        "subGroups": []
      },
      {
        "caption": "c0",
        "icon": null,
        "name": "0",
        "order": 99,
        "route": "/0",
        "subGroups": []
      }
    ]);
  });

  it("group child sorting", () => {
    const settings = new GlobalMenuSettings();
    settings.addGroup({
      name: '1',
      parentName: null,
      caption: 'c1',
      route: '/1',
      icon: null,
      order: 10
    });
    settings.addGroup({
      name: '1.1',
      parentName: '1',
      caption: 'c1.1',
      route: '/1.1',
      icon: null,
      order: 5
    });
    settings.addGroup({
      name: '1.1.1',
      parentName: '1.1',
      caption: 'c1.1.1',
      route: '/1.1.1',
      icon: null,
      order: null
    });
    settings.addGroup({
      name: '1.1.2',
      parentName: '1.1',
      caption: 'c1.1.2',
      route: '/1.1.2',
      icon: null,
      order: 10
    });
    settings.addGroup({
      name: '1.1.3',
      parentName: '1.1',
      caption: 'c1.1.3',
      route: '/1.1.3',
      icon: null,
      order: 9
    });
    settings.addGroup({
      name: '1.1.4',
      parentName: '1.1',
      caption: 'c1.1.4',
      route: '/1.1.4',
      icon: null,
      order: 11
    });
    settings.addGroup({
      name: '1.1.5',
      parentName: '1.1',
      caption: 'c1.1.5',
      route: '/1.1.5',
      icon: null,
      order: 10
    });

    expect(settings.groups).toEqual([
      {
        "caption": "c1",
        "icon": null,
        "name": "1",
        "order": 10,
        "route": "/1",
        "subGroups": [
          {
            "caption": "c1.1",
            "icon": null,
            "name": "1.1",
            "order": 5,
            "route": "/1.1",
            "subGroups": [
              {
                "caption": "c1.1.3",
                "icon": null,
                "name": "1.1.3",
                "order": 9,
                "route": "/1.1.3",
                "subGroups": []
              },
              {
                "caption": "c1.1.2",
                "icon": null,
                "name": "1.1.2",
                "order": 10,
                "route": "/1.1.2",
                "subGroups": []
              },
              {
                "caption": "c1.1.5",
                "icon": null,
                "name": "1.1.5",
                "order": 10,
                "route": "/1.1.5",
                "subGroups": []
              },
              {
                "caption": "c1.1.4",
                "icon": null,
                "name": "1.1.4",
                "order": 11,
                "route": "/1.1.4",
                "subGroups": []
              },
              {
                "caption": "c1.1.1",
                "icon": null,
                "name": "1.1.1",
                "order": 99,
                "route": "/1.1.1",
                "subGroups": []
              }
            ]
          }
        ]
      }]);
  });
});
