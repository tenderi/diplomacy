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
import { Province } from "./province";

export class MapData {
    constructor(mapInfo, game) {
        this.game = game;
        this.powers = new Set(mapInfo.powers);
        this.supplyCenters = new Set(mapInfo.supply_centers);
        this.aliases = new Map(Object.entries(mapInfo.aliases));
        this.provinces = {};

        for (const [provinceName, provinceType] of Object.entries(mapInfo.loc_type)) {
            this.provinces[provinceName] = new Province(
                provinceName,
                provinceType,
                this.supplyCenters.has(provinceName)
            );
        }

        for (const [provinceName, neighbors] of Object.entries(mapInfo.loc_abut)) {
            const province = this.getProvince(provinceName);
            if (province) {
                province.setNeighbors(neighbors.map(name => this.getProvince(name)));
            }
        }

        for (const province of Object.values(this.provinces)) {
            province.setCoasts(this.provinces);
        }

        for (const power of Object.values(this.game.powers)) {
            power.centers?.forEach(center => {
                const province = this.getProvince(center);
                province?.setController(power.name, 'C');
            });

            power.influence?.forEach(loc => {
                const province = this.getProvince(loc);
                province?.setController(power.name, 'I');
            });

            power.units?.forEach(unit => {
                this.__add_unit(unit, power.name);
            });

            Object.keys(power.retreats ?? {}).forEach(unit => {
                this.__add_retreat(unit, power.name);
            });
        }

        for (const [alias, provinceName] of this.aliases.entries()) {
            const province = this.getProvince(provinceName);
            if (province) province.aliases.push(alias);
        }
    }

    __add_unit(unit, powerName) {
        const [unitType, location] = unit.split(/ +/);
        const province = this.getProvince(location);
        if (province) {
            province.setController(powerName, 'U');
            province.unit = unitType;
        }
    }

    __add_retreat(unit, powerName) {
        const [, location] = unit.split(/ +/);
        const province = this.getProvince(location);
        if (province) {
            province.retreatController = powerName;
            province.retreatUnit = unit;
        }
    }

    getProvince(abbr) {
        if (!abbr) return null;

        const normalizedAbbr = abbr.startsWith('_') ? abbr.substr(1, 3) : abbr;
        if (!normalizedAbbr) return null;

        const { provinces, aliases } = this;

        return (
            provinces[normalizedAbbr] ??
            provinces[normalizedAbbr.toUpperCase()] ??
            provinces[normalizedAbbr.toLowerCase()] ??
            provinces[aliases.get(normalizedAbbr)] ??
            provinces[aliases.get(normalizedAbbr.toUpperCase())] ??
            provinces[aliases.get(normalizedAbbr.toLowerCase())] ??
            null
        );
    }
}
