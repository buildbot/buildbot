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

import './UrlNotFoundView.scss';

const UrlNotFoundView = () => {
  return (
    <div className="container bb-url-not-found-view">
      <div>
        <div>
          <h1>404</h1>
        </div>
        <div className="break"/>
        <div>
          <b>Page Not Found</b>
        </div>
        <div className="break"/>
        <div>
          Make sure the address is correct
        </div>
      </div>
    </div>
  );
}

export default UrlNotFoundView;
