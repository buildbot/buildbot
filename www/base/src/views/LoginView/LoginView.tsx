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

import {FaSignInAlt} from 'react-icons/fa';
import {getBaseUrl} from 'buildbot-data-js';
import {ConfigContext} from 'buildbot-ui';
import {useContext} from 'react';
import {useLocation} from 'react-router-dom';
import {LoginIcon} from '../../components/LoginIcon/LoginIcon';

export const LoginView = () => {
  const config = useContext(ConfigContext);
  const location = useLocation();

  const redirect = location.pathname + location.search + location.hash;

  return (
    <div
      className="container bb-login-view d-flex justify-content-center align-items-center"
      style={{height: '80vh'}}
    >
      <a
        href={getBaseUrl(window.location, 'auth/login?redirect=' + encodeURI(redirect))}
        className="btn btn-primary btn-lg px-4 py-2"
      >
        {config.auth.oauth2 ? (
          <>
            <LoginIcon iconName={config.auth.fa_icon} />
            &nbsp;Login with {config.auth.name}
          </>
        ) : (
          <>
            <FaSignInAlt />
            &nbsp;Login
          </>
        )}
      </a>
    </div>
  );
};
