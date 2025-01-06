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
import { STRINGS } from "../utils/strings";
import { UTILS } from "../utils/utils";
import { REQUESTS } from "../communication/requests";

/** Class Channel. **/
export class Channel {
    constructor(connection, username, token) {
        this.connection = connection;
        this.token = token;
        this.username = username;
        this.game_id_to_instances = {};
    }

    localJoinGame(joinParameters) {
        // Game ID must be known.
        if (Object.prototype.hasOwnProperty.call(this.game_id_to_instances, joinParameters.game_id)) {
            // If there is a power name, we return associated power game.
            if (joinParameters.power_name) {
                return this.game_id_to_instances[joinParameters.game_id].get(joinParameters.power_name);
            }
            // Otherwise, we return current special game (if exists).
            return this.game_id_to_instances[joinParameters.game_id].getSpecial();
        }
        return null;
    }

    _req(name, forcedParameters, localChannelFunction, parameters, game) {
        /** Send a request object for given request name with (optional) given forced parameters..
         * If a local channel function is given, it will be used to try retrieving data
         * locally instead of sending a request. If local channel function returns something, this value is returned.
         * Otherwise, normal procedure (request sending) is used. Local channel function would be called with
         * request parameters passed to channel request method.
         * **/
        parameters = Object.assign(parameters || {}, forcedParameters || {});
        const level = REQUESTS.getLevel(name);
        if (level === STRINGS.GAME) {
            if (!game) {
                throw new Error("A game object is required to send a game request.");
            }
            parameters.token = this.token;
            parameters.game_id = game.local.game_id;
            parameters.game_role = game.local.role;
            parameters.phase = game.local.phase;
        } else {
            if (game) {
                throw new Error("A game object should not be provided for a non-game request.");
            }
            if (level === STRINGS.CHANNEL) parameters.token = this.token;
        }
        if (localChannelFunction) {
            const localResult = localChannelFunction.apply(this, [parameters]);
            if (localResult) return localResult;
        }
        const request = REQUESTS.create(name, parameters);
        const future = this.connection.send(request, game);
        const timeoutID = setTimeout(function () {
            if (!future.done())
                future.setException(
                    "Timeout reached when trying to send a request " +
                        name +
                        "/" +
                        request.request_id +
                        "."
                );
        }, UTILS.REQUEST_TIMEOUT_SECONDS * 1000);
        return future.promise().then((result) => {
            clearTimeout(timeoutID);
            return result;
        });
    }

    // (Rest of the code remains unchanged)

    // For all other methods: Make sure to use the same safe pattern for checking properties if needed.
}
