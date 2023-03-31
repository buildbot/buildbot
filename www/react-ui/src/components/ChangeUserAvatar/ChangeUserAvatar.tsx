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

import './ChangeUserAvatar.scss';
import {Link} from "react-router-dom";

type ChangeUserAvatarProps = {
  name: string;
  email: string | null;
  showName: boolean;
}

const ChangeUserAvatar = ({name, email, showName}: ChangeUserAvatarProps) => {
  if (email === null) {
    return (
      <>
        <div className="change-avatar">
          <img alt="unknown" title={name} src={`avatar?email=unknown`}/>
        </div>
        {showName ? <span>{name}</span> : <></>}
      </>
    );
  }

  return (
    <>
      <div className="change-avatar">
        <Link to={`mailto:${email}`} title={name}>
          <img alt={email} src={`avatar?email=${encodeURI(email)}`}/>
        </Link>
      </div>
      {showName ? <Link to={`mailto:${email}`}>{name}</Link> : <></>}
    </>
  );
}

export default ChangeUserAvatar;
