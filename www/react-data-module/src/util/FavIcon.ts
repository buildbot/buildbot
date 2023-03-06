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

import axios from "axios";
import {useEffect} from "react";
import {intToColor, SUCCESS, UNKNOWN} from "./Results";

function setFavIconUrl(url: string) {
  const iconElement = document.getElementById('bbicon');
  if (iconElement !== null) {
    (iconElement as HTMLLinkElement).href = url;
  }
}

function setFavIconUrlOriginal() {
  setFavIconUrl(process.env.PUBLIC_URL + "/icon.png");
}

async function setFavIcon(result: number) {
  if (result === UNKNOWN) {
    setFavIconUrlOriginal();
    return;
  }

  const response = await axios.get(process.env.PUBLIC_URL + "/icon.svg");
  const iconSvg = response.data;

  const canvas = document.createElement('canvas');
  canvas.width = 300;
  canvas.height = 300;
  const ctx = canvas.getContext('2d');
  const colorCode = intToColor[result] ?? intToColor[SUCCESS];

  // Note that a regex needs to be used in order to replace all occurrences of the string.
  const replacedSvg = iconSvg.replace(/#8da6d8/g, colorCode);
  const URL = window.URL || window.webkitURL || window;

  const svg = new Blob([replacedSvg], {type: 'image/svg+xml'});
  const url = URL.createObjectURL(svg);

  const img = new Image();
  img.onload = function() {
    ctx?.drawImage(img, 0, 0);
    setFavIconUrl(canvas.toDataURL());
    URL.revokeObjectURL(url);
  };

  img.crossOrigin = 'Anonymous';
  img.src = url;
}

export function useFavIcon(result: number) {
  useEffect(() => {
    setFavIcon(result);
  }, [result]);

  // We only want to clear the favicon once, thus the useEffect hook is split into two parts, one
  // for updates, one for eventual cleanup when navigating out of view.
  useEffect(() => {
    return () => setFavIconUrlOriginal();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}
