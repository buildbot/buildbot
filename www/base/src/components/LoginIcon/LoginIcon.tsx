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

import {
  FaBitbucket,
  FaCogs,
  FaFacebook,
  FaGithub,
  FaGitlab,
  FaGoogle,
  FaLinkedin,
  FaMicrosoft,
} from 'react-icons/fa';

export type LoginIconProps = {
  iconName: string;
};

export const LoginIcon = ({iconName}: LoginIconProps) => {
  switch (iconName) {
    case 'fa-github':
      return <FaGithub />;
    case 'fa-gitlab':
      return <FaGitlab />;
    case 'fa-bitbucket':
      return <FaBitbucket />;
    case 'fa-google':
      return <FaGoogle />;
    case 'fa-facebook':
      return <FaFacebook />;
    case 'fa-linkedin':
      return <FaLinkedin />;
    case 'fa-microsoft':
      return <FaMicrosoft />;
    case '':
      return <></>;
    default:
      return <FaCogs />;
  }
};
