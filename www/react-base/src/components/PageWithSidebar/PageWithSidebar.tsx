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

import './PageWithSidebar.scss';
import {observer} from "mobx-react";
import {GlobalMenuSettings} from "../../plugins/GlobalMenuSettings";
import SidebarStore from "../../stores/SidebarStore";
import {Link} from "react-router-dom";

type PageWithSidebarProps = {
  menuSettings: GlobalMenuSettings,
  sidebarStore: SidebarStore,
  children: JSX.Element[] | JSX.Element,
}

const PageWithSidebar = observer(({menuSettings, sidebarStore, children}: PageWithSidebarProps) => {
  const {appTitle, groups, footerItems} = menuSettings;

  const pageWithSidebarClass = "gl-page-with-sidebar" +
    (sidebarStore.active ? " active": "") +
    (sidebarStore.pinned ? " pinned": "");

  let sidebarIcon: JSX.Element;
  if (sidebarStore.active) {
    sidebarIcon = (
      <span onClick={() => sidebarStore.togglePinned()}
            className={"menu-icon fa fa-thumb-tack" + (sidebarStore.pinned ? "" : " fa-45")}/>
    );
  } else {
    sidebarIcon = (
      <span onClick={() => sidebarStore.show()} className="menu-icon fa fa-bars"/>
    );
  }

  const groupElements = groups.map((group, groupIndex) => {
    if (group.subGroups.length > 0) {
      const subGroups = group.subGroups.map(subGroup => {
          const subClassName = "sidebar-list subitem" +
            (sidebarStore.activeGroup === group.name ? " active": "");

          return (
            <li key={`group-${subGroup.name}`} className={subClassName}>
              {subGroup.route === null
                ? <span>{subGroup.caption}</span>
                : <Link to={subGroup.route} onClick={() => sidebarStore.hide()}>{subGroup.caption}</Link>
              }
            </li>
          )
        });

      return [
        <li key={`group-${group.name}`} className="sidebar-list">
          <button onClick={() => {sidebarStore.toggleGroup(group.name); }}>
            <i className="fa fa-angle-right"></i>&nbsp;{group.caption}
            <span className={"menu-icon fa fa-" + group.icon}></span>
          </button>
        </li>,
        ...subGroups
      ];
    }

    const elements: JSX.Element[] = [];
    if (groupIndex > 0) {
      elements.push(<li key={`groupsep-${group.name}`} className="sidebar-separator"></li>);
    }
    elements.push(
      <li key={`group-${group.name}`} className="sidebar-list">
        {group.route === null
          ? <button onClick={() => sidebarStore.toggleGroup(group.name)}>{group.caption}
            <span className={"menu-icon fa fa-" + group.icon}></span>
          </button>
          : <Link to={group.route} onClick={() => sidebarStore.toggleGroup(group.name)}>{group.caption}
            <span className={"menu-icon fa fa-" + group.icon}></span>
          </Link>
        }
      </li>
    )
    return elements;
  });

  const footerElements = footerItems.map((footerItem, index) => {
    return (
      <div key={index} className="col-xs-4">
        <Link to={footerItem.route}>{footerItem.caption}</Link>
      </div>
    );
  });

  return (
    <div className={pageWithSidebarClass}>
      <div onMouseEnter={() => sidebarStore.enter()} onMouseLeave={() => sidebarStore.leave()}
           onClick={() => sidebarStore.show()} className="sidebar sidebar-blue">
        <ul>
          <li key="sidebar-main" className="sidebar-main"><Link to="/">{appTitle}{sidebarIcon}</Link></li>
          <li key="sidebar-title" className="sidebar-title"><span>NAVIGATION</span></li>
          {groupElements}
        </ul>
        <div className="sidebar-footer">
          {footerElements}
        </div>
      </div>
      <div className="content">
        {children}
      </div>
    </div>
  );
});

export default PageWithSidebar;
