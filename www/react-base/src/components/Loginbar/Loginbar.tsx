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

import {useContext, useState} from "react";
import {ConfigContext} from "../../contexts/Config";
import {useLocation} from "react-router-dom";

const Loginbar = () => {
  const config = useContext(ConfigContext);
  const location = useLocation();

  const [collapsed, setCollapsed] = useState(true);

  const user = config.user;

  if (config.auth.name === "NoAuth") {
    return <></>
  }

  const redirect = location.pathname + location.search + location.hash;

  if (user.anonymous) {
    return (
      <ul className="nav navbar-nav navbar-right">
        <li className={"dropdown" + (collapsed ? "" : " open")}>
          <a onClick={() => setCollapsed(!collapsed)}>Anonymous<b className="caret"></b></a>
          <ul uib-dropdown-menu="uib-dropdown-menu" className="dropdown-menu">
            <li>
              <a href={"/auth/login?redirect=" + encodeURI(redirect)}>
                {
                  config.auth.oauth2
                    ? <span>
                        <i className={"fa " + config.auth.fa_icon}></i>&nbsp;Login with {config.auth.name}
                      </span>
                    : <span><i className="fa fa-sign-in"></i>&nbsp;Login</span>
                }
              </a>
            </li>
          </ul>
        </li>
      </ul>
    );
  }

  const avatarURL = `avatar?username=${encodeURI(user.username ?? "")}&amp;email=${encodeURI(user.email ?? "")}`;

  const dropdownToggle = config.avatar_methods.length > 0
    ? <img src={avatarURL} className="avatar"/>
    : <span>{user.full_name ?? user.username ?? ""}<b className="caret"></b></span>;

  const userDropdownHeader = (user.full_name || user.email)
    ? <li className="dropdown-header">
        <i className="fa fa-user"/>
        <span>{config.user.full_name ?? ""} {config.user.email ?? ""}</span>
      </li>
    : <></>

  return (
    <ul className="nav navbar-nav navbar-right">
      <li className={"dropdown" + (collapsed ? "" : " open")}>
        <a onClick={() => setCollapsed(!collapsed)}>
          {dropdownToggle}
        </a>
        <ul uib-dropdown-menu="uib-dropdown-menu" className="dropdown-menu">
          {userDropdownHeader}
          <li className="divider"></li>
          <li>
            <a href={"auth/logout?redirect=" + encodeURI(redirect)}>
              <i className="fa fa-sign-out"></i>
              Logout
            </a>
          </li>
        </ul>
      </li>
    </ul>
  );
};

export default Loginbar;
