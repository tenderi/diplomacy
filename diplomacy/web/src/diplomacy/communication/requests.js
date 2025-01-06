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

/** Requests **/
export const REQUESTS = {
    /** Abstract request models */
    abstract: {
        basic: { request_id: null, name: null, re_sent: false },
        channel: { token: null },
        game: { game_id: null, game_role: null, phase: null },
    },

    /** Request models with levels and defaults */
    models: {
        sign_in: { level: null, model: { username: null, password: null } },
        create_game: {
            level: STRINGS.CHANNEL,
            model: {
                game_id: null,
                n_controls: null,
                deadline: 300,
                registration_password: null,
                power_name: null,
                state: null,
                map_name: "standard",
                rules: null,
            },
        },
        delete_account: { level: STRINGS.CHANNEL, model: { username: null } },
        get_all_possible_orders: { level: STRINGS.GAME, model: {} },
        get_available_maps: { level: STRINGS.CHANNEL, model: {} },
        get_playable_powers: { level: STRINGS.CHANNEL, model: { game_id: null } },
        join_game: {
            level: STRINGS.CHANNEL,
            model: { game_id: null, power_name: null, registration_password: null },
        },
        list_games: {
            level: STRINGS.CHANNEL,
            model: {
                game_id: null,
                status: null,
                map_name: null,
                include_protected: true,
                for_omniscience: false,
            },
        },
        get_games_info: { level: STRINGS.CHANNEL, model: { games: null } },
        logout: { level: STRINGS.CHANNEL, model: {} },
        set_grade: {
            level: STRINGS.CHANNEL,
            model: { grade: null, grade_update: null, username: null, game_id: null },
        },
        clear_centers: { level: STRINGS.GAME, model: { power_name: null } },
        clear_orders: { level: STRINGS.GAME, model: { power_name: null } },
        clear_units: { level: STRINGS.GAME, model: { power_name: null } },
        delete_game: { level: STRINGS.GAME, phase_dependent: false, model: {} },
        get_phase_history: {
            level: STRINGS.GAME,
            phase_dependent: false,
            model: { from_phase: null, to_phase: null },
        },
        leave_game: { level: STRINGS.GAME, model: {} },
        process_game: { level: STRINGS.GAME, model: {} },
        query_schedule: { level: STRINGS.GAME, model: {} },
        send_game_message: { level: STRINGS.GAME, model: { message: null } },
        set_dummy_powers: { level: STRINGS.GAME, model: { username: null, power_names: null } },
        set_game_state: {
            level: STRINGS.GAME,
            model: { state: null, orders: null, results: null, messages: null },
        },
        set_game_status: { level: STRINGS.GAME, model: { status: null } },
        set_orders: { level: STRINGS.GAME, model: { power_name: null, orders: null } },
        set_wait_flag: { level: STRINGS.GAME, model: { power_name: null, wait: null } },
        synchronize: { level: STRINGS.GAME, phase_dependent: false, model: { timestamp: null } },
        vote: { level: STRINGS.GAME, model: { vote: null } },
        save_game: { level: STRINGS.GAME, model: {} },
    },

    /** Determine if the request is phase dependent */
    isPhaseDependent(name) {
        const model = REQUESTS.models[name];
        if (!model) throw new Error(`Unknown request name: ${name}`);
        return model.level === STRINGS.GAME && (model.phase_dependent ?? true);
    },

    /** Get the level for a given request name */
    getLevel(name) {
        const model = REQUESTS.models[name];
        if (!model) throw new Error(`Unknown request name: ${name}`);
        return model.level;
    },

    /** Create a request object */
    create(name, parameters = {}) {
        const modelDefinition = REQUESTS.models[name];
        if (!modelDefinition) throw new Error(`Unknown request name: ${name}`);

        const models = [
            {},
            modelDefinition.model,
            ...(modelDefinition.level === STRINGS.GAME ? [REQUESTS.abstract.game, REQUESTS.abstract.channel] : []),
            ...(modelDefinition.level === STRINGS.CHANNEL ? [REQUESTS.abstract.channel] : []),
            REQUESTS.abstract.basic,
            { name },
        ];

        const request = Object.assign({}, ...models);

        Object.entries(parameters).forEach(([key, value]) => {
            if (key in request) request[key] = value;
        });

        if (!request.request_id) {
            request.request_id = UTILS.createID();
        }

        return request;
    },
};
