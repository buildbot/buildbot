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

import './Topbar.less'
import {Link} from "react-router-dom";
import {useState} from "react";
import TopbarStore from "../../stores/TopbarStore";
import {computed} from "mobx";
import {observer} from "mobx-react";

export type TopbarItem = {
  route: string | null,
  caption: string
}

type TopbarProps = {
  store: TopbarStore,
  appTitle: string,
  children: JSX.Element | JSX.Element[]
}

const Topbar = observer(({store, appTitle, children}: TopbarProps) => {
  const [collapse, setCollapse] = useState(true);

  const elements = computed(() => store.items.map((item, index) => {
    if (item.route === null) {
      return (
        <li key={index}><span>{item.caption}</span></li>
      );
    }
    return (
      <li key={index}><Link to={item.route}>{item.caption}</Link></li>
    );
  })).get();

  return (
    <nav className="navbar navbar-default">
      <div className="container-fluid">
        <div className="navbar-header">
          <button type="button" onClick={() => setCollapse(!collapse)}
                  aria-expanded="false" className="navbar-toggle collapsed">
            <span className="sr-only">Toggle navigation</span>
            <span className="icon-bar"></span>
            <span className="icon-bar"></span>
            <span className="icon-bar"></span>
          </button>
          <a className="navbar-brand">{appTitle}</a>
          <ol className="breadcrumb">
            {elements}
          </ol>
        </div>
        <div className={"navbar-collapse collapse pull-right" + (collapse ? "" : " in")}>
          <ul className="nav navbar-nav">
            {children}
          </ul>
        </div>
      </div>
    </nav>
  );
});

export default Topbar;
