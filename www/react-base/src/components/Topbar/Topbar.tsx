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

import './Topbar.scss'
import {Link} from "react-router-dom";
import TopbarStore from "../../stores/TopbarStore";
import {computed} from "mobx";
import {observer} from "mobx-react";
import {Nav, Navbar} from "react-bootstrap";

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
  const elements = computed(() => store.items.map((item, index) => {
    if (item.route === null) {
      return (
        <li className="nav-item" key={index}><span>{item.caption}</span></li>
      );
    }
    return (
      <li className="nav-item" key={index}>
        <Link className="nav-link" to={item.route}>{item.caption}</Link>
      </li>
    );
  })).get();

  return (
    <Navbar bg="light" expand="lg">
      <Navbar.Brand>{appTitle}</Navbar.Brand>
      <Navbar.Toggle aria-controls="bb-topbar-navbar-nav" />
      <Navbar.Collapse id="bb-topbar-navbar-nav">
        <Nav className="mr-auto bb-topbar-navbar-elements">
          {elements}
        </Nav>
        {children}
      </Navbar.Collapse>
    </Navbar>
  );
});

export default Topbar;
