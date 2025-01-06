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
import { centerSymbolAroundUnit, getUnitCenter } from "./common";

export const SupportHold = ({ loc, dstLoc, powerName, coordinates, symbolSizes, colors }) => {
    const symbol = "SupportHoldUnit";

    // Center the symbol around the destination unit
    const [symbolLocX, symbolLocY] = centerSymbolAroundUnit(coordinates, symbolSizes, dstLoc, false, symbol);
    const [locX, locY] = getUnitCenter(coordinates, symbolSizes, loc, false);
    let [destLocX, destLocY] = getUnitCenter(coordinates, symbolSizes, dstLoc, false);

    // Adjust destination location
    const deltaX = destLocX - locX;
    const deltaY = destLocY - locY;
    const vectorLength = Math.sqrt(deltaX ** 2 + deltaY ** 2);
    const deltaDec = parseFloat(symbolSizes[symbol].height) / 2;

    destLocX = (
        Math.round((parseFloat(locX) + (vectorLength - deltaDec) / vectorLength * deltaX) * 100) / 100
    ).toString();
    destLocY = (
        Math.round((parseFloat(locY) + (vectorLength - deltaDec) / vectorLength * deltaY) * 100) / 100
    ).toString();

    return (
        <g stroke={colors[powerName]}>
            <line x1={locX} y1={locY} x2={destLocX} y2={destLocY} className="shadowdash" />
            <line x1={locX} y1={locY} x2={destLocX} y2={destLocY} className="supportorder" stroke={colors[powerName]} />
            <use
                x={symbolLocX}
                y={symbolLocY}
                width={symbolSizes[symbol].width}
                height={symbolSizes[symbol].height}
                href={`#${symbol}`}
            />
        </g>
    );
};

SupportHold.propTypes = {
    loc: PropTypes.string.isRequired,
    dstLoc: PropTypes.string.isRequired,
    powerName: PropTypes.string.isRequired,
    coordinates: PropTypes.object.isRequired,
    symbolSizes: PropTypes.object.isRequired,
    colors: PropTypes.object.isRequired,
};
