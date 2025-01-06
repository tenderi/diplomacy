// ==============================================================================
// Copyright (C) 2019 - Philip Paquette, Steven Bocco
//
//  This program is free software: you can redistribute it and/or modify it under
//  the terms of the GNU Affero General Public License as published by the Free
//  Software Foundation, either version 3 of the License, or (at your option) any
//  later version.
//
//  This program is distributed in the hope that it will be useful, but WITHOUT
//  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
//  FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
//  details.
//
//  You should have received a copy of the GNU Affero General Public License along
//  with this program.  If not, see <https://www.gnu.org/licenses/>.
// ==============================================================================
import React from "react";
import PropTypes from "prop-types";
import { ARMY, coloredStrokeWidth, getUnitCenter } from "./common";

export const SupportMove = ({ loc, srcLoc, dstLoc, powerName, coordinates, symbolSizes, colors }) => {
    const [locX, locY] = getUnitCenter(coordinates, symbolSizes, loc, false);
    const [srcLocX, srcLocY] = getUnitCenter(coordinates, symbolSizes, srcLoc, false);
    let [destLocX, destLocY] = getUnitCenter(coordinates, symbolSizes, dstLoc, false);

    // Adjust destination location
    const deltaX = destLocX - srcLocX;
    const deltaY = destLocY - srcLocY;
    const vectorLength = Math.sqrt(deltaX ** 2 + deltaY ** 2);
    const deltaDec = parseFloat(symbolSizes[ARMY].width) / 2 + 2 * coloredStrokeWidth(symbolSizes);

    destLocX = (
        Math.round((parseFloat(srcLocX) + (vectorLength - deltaDec) / vectorLength * deltaX) * 100) / 100
    ).toString();
    destLocY = (
        Math.round((parseFloat(srcLocY) + (vectorLength - deltaDec) / vectorLength * deltaY) * 100) / 100
    ).toString();

    const pathD = `M ${locX},${locY} C ${srcLocX},${srcLocY} ${srcLocX},${srcLocY} ${destLocX},${destLocY}`;

    return (
        <g>
            <path className="shadowdash" d={pathD} />
            <path
                className="supportorder"
                markerEnd="url(#arrow)"
                stroke={colors[powerName]}
                d={pathD}
            />
        </g>
    );
};

SupportMove.propTypes = {
    loc: PropTypes.string.isRequired,
    srcLoc: PropTypes.string.isRequired,
    dstLoc: PropTypes.string.isRequired,
    powerName: PropTypes.string.isRequired,
    coordinates: PropTypes.object.isRequired,
    symbolSizes: PropTypes.object.isRequired,
    colors: PropTypes.object.isRequired,
};
