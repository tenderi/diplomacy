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
import { ARMY, coloredStrokeWidth, getUnitCenter, plainStrokeWidth } from "./common";

export const Move = ({ srcLoc, dstLoc, powerName, phaseType, coordinates, symbolSizes, colors }) => {
    const isDislodged = phaseType === "R";
    const [srcLocX, srcLocY] = getUnitCenter(coordinates, symbolSizes, srcLoc, isDislodged);
    let [destLocX, destLocY] = getUnitCenter(coordinates, symbolSizes, dstLoc, isDislodged);

    // Adjusting destination
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

    return (
        <g>
            <line
                x1={srcLocX}
                y1={srcLocY}
                x2={destLocX}
                y2={destLocY}
                className="varwidthshadow"
                strokeWidth={`${plainStrokeWidth(symbolSizes)}`}
            />
            <line
                x1={srcLocX}
                y1={srcLocY}
                x2={destLocX}
                y2={destLocY}
                className="varwidthorder"
                markerEnd="url(#arrow)"
                stroke={colors[powerName]}
                strokeWidth={`${coloredStrokeWidth(symbolSizes)}`}
            />
        </g>
    );
};

Move.propTypes = {
    srcLoc: PropTypes.string.isRequired,
    dstLoc: PropTypes.string.isRequired,
    powerName: PropTypes.string.isRequired,
    phaseType: PropTypes.string.isRequired,
    coordinates: PropTypes.object.isRequired,
    symbolSizes: PropTypes.object.isRequired,
    colors: PropTypes.object.isRequired,
};
