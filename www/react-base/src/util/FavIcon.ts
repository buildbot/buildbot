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

import {useEffect, useState} from "react";
import iconSvg from '../assets/icon.svg';
import {intToColor, SUCCESS} from "./Results";

function setFavIconUrl(url: string) {
  const iconElement = document.getElementById('bbicon');
  if (iconElement !== null) {
    (iconElement as HTMLLinkElement).href = url;
  }
}

function setFavIcon(result: number) {
  if (result === SUCCESS) {
    setFavIconUrl(process.env.PUBLIC_URL + "/icon.png");
  }
  const canvas = document.createElement('canvas');
  canvas.width = 300;
  canvas.height = 300;
  const ctx = canvas.getContext('2d');
  const colorCode = intToColor[result] ?? intToColor[SUCCESS];

  const replacedSvg = iconSvg.replace("#8da6d8", colorCode);
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
  const [wasUpdated, setWasUpdated] = useState(false);

  useEffect(() => {
    if (result === SUCCESS && !wasUpdated) {
      return;
    }
    setFavIcon(result);
    if (!wasUpdated) {
      setWasUpdated(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  // We only want to clear the favicon once, thus the useEffect hook is split into two parts, one
  // for updates, one for eventual cleanup when navigating out of view.
  useEffect(() => {
    return () => {
      if (wasUpdated) {
        setFavIcon(SUCCESS);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}
