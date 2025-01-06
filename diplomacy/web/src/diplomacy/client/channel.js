// ==============================================================================
// Copyright (C) 2019 - Philip Paquette, Steven Bocco
//
// This program is free software: you can redistribute it and/or modify it under
// the terms of the GNU Affero General Public License as published by the Free
// Software Foundation, either version 3 of the License, or any
// later version.
//
// This program is distributed in the hope that it will be useful, but WITHOUT
// ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS.
// See the GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License along
// with this program. If not, see <https://www.gnu.org/licenses/>.
// ==============================================================================
import { STRINGS } from "../utils/strings";
import { UTILS } from "../utils/utils";
import { REQUESTS } from "../communication/requests";
import {Future} from "../utils/future";


export class Channel {
    constructor(connection, username, token) {
        this.connection = connection;
        this.username = username;
        this.token = token;
        this.game_id_to_instances = {};
    }

    localJoinGame = (joinParameters) => {
        const { game_id, power_name } = joinParameters;

        if (this.game_id_to_instances[game_id]) {
            if (power_name) {
                return this.game_id_to_instances[game_id].get(power_name);
            }
            return this.game_id_to_instances[game_id].getSpecial();
        }
        return null;
    };

    _req(name, forcedParameters, localChannelFunction, parameters, game) {
        parameters = { ...(parameters || {}), ...(forcedParameters || {}) };
    
        const level = REQUESTS.getLevel(name);
        if (level === STRINGS.GAME) {
            if (!game) throw new Error("A game object is required to send a game request.");
            Object.assign(parameters, {
                token: this.token,
                game_id: game.local.game_id,
                game_role: game.local.role,
                phase: game.local.phase,
            });
        } else if (level === STRINGS.CHANNEL) {
            parameters.token = this.token;
        }
    
        if (localChannelFunction) {
            const localResult = localChannelFunction.call(this, parameters);
            if (localResult) return localResult;
        }
    
        const request = REQUESTS.create(name, parameters);
        const future = this.connection.send(request);
        const timeoutID = setTimeout(() => {
            if (future instanceof Future && !future.done()) {
                future.setException(new Error(`Timeout reached for request ${name}/${request.request_id}`));
            }
        }, UTILS.REQUEST_TIMEOUT_SECONDS * 1000);
    
        // Ensure the future is properly resolved and its promise method is valid
        return future.promise().then(
            (result) => {
                clearTimeout(timeoutID);
                return result;
            },
            (error) => {
                clearTimeout(timeoutID);
                throw error;
            }
        );
    }
            // Public channel API
    createGame = (parameters) => this._req("create_game", {}, null, parameters);

    getAvailableMaps = (parameters) => this._req("get_available_maps", {}, null, parameters);

    getPlayablePowers = (parameters) => this._req("get_playable_powers", {}, null, parameters);

    joinGame = (parameters) => this._req("join_game", {}, this.localJoinGame, parameters);

    listGames = (parameters) => this._req("list_games", {}, null, parameters);

    getGamesInfo = (parameters) => this._req("get_games_info", {}, null, parameters);

    deleteAccount = (parameters) => this._req("delete_account", {}, null, parameters);

    logout = (parameters) => this._req("logout", {}, null, parameters);

    makeOmniscient = (parameters) =>
        this._req("set_grade", { grade: STRINGS.OMNISCIENT, grade_update: STRINGS.PROMOTE }, null, parameters);

    removeOmniscient = (parameters) =>
        this._req("set_grade", { grade: STRINGS.OMNISCIENT, grade_update: STRINGS.DEMOTE }, null, parameters);

    promoteAdministrator = (parameters) =>
        this._req("set_grade", { grade: STRINGS.ADMIN, grade_update: STRINGS.PROMOTE }, null, parameters);

    demoteAdministrator = (parameters) =>
        this._req("set_grade", { grade: STRINGS.ADMIN, grade_update: STRINGS.DEMOTE }, null, parameters);

    promoteModerator = (parameters) =>
        this._req("set_grade", { grade: STRINGS.MODERATOR, grade_update: STRINGS.PROMOTE }, null, parameters);

    demoteModerator = (parameters) =>
        this._req("set_grade", { grade: STRINGS.MODERATOR, grade_update: STRINGS.DEMOTE }, null, parameters);

    // Public game API
    getAllPossibleOrders = (parameters, game) => this._req("get_all_possible_orders", {}, null, parameters, game);

    getPhaseHistory = (parameters, game) => this._req("get_phase_history", {}, null, parameters, game);

    leaveGame = (parameters, game) => this._req("leave_game", {}, null, parameters, game);

    sendGameMessage = (parameters, game) => this._req("send_game_message", {}, null, parameters, game);

    setOrders = (parameters, game) => this._req("set_orders", {}, null, parameters, game);

    clearCenters = (parameters, game) => this._req("clear_centers", {}, null, parameters, game);

    clearOrders = (parameters, game) => this._req("clear_orders", {}, null, parameters, game);

    clearUnits = (parameters, game) => this._req("clear_units", {}, null, parameters, game);

    wait = (parameters, game) => this._req("set_wait_flag", { wait: true }, null, parameters, game);

    noWait = (parameters, game) => this._req("set_wait_flag", { wait: false }, null, parameters, game);

    vote = (parameters, game) => this._req("vote", {}, null, parameters, game);

    save = (parameters, game) => this._req("save_game", {}, null, parameters, game);

    synchronize = (parameters, game) => this._req("synchronize", {}, null, parameters, game);

    deleteGame = (parameters, game) => this._req("delete_game", {}, null, parameters, game);

    kickPowers = (parameters, game) => this._req("set_dummy_powers", {}, null, parameters, game);

    setState = (parameters, game) => this._req("set_game_state", {}, null, parameters, game);

    process = (parameters, game) => this._req("process_game", {}, null, parameters, game);

    querySchedule = (parameters, game) => this._req("query_schedule", {}, null, parameters, game);

    start = (parameters, game) => this._req("set_game_status", { status: STRINGS.ACTIVE }, null, parameters, game);

    pause = (parameters, game) => this._req("set_game_status", { status: STRINGS.PAUSED }, null, parameters, game);

    resume = (parameters, game) => this._req("set_game_status", { status: STRINGS.ACTIVE }, null, parameters, game);

    cancel = (parameters, game) => this._req("set_game_status", { status: STRINGS.CANCELED }, null, parameters, game);

    draw = (parameters, game) => this._req("set_game_status", { status: STRINGS.COMPLETED }, null, parameters, game);
}
