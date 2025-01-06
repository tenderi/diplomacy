import { STRINGS } from "../utils/strings";

/** Responses. **/
export const RESPONSES = {
    names: new Set([
        "error",
        "ok",
        "data_game_phase",
        "data_token",
        "data_maps",
        "data_power_names",
        "data_games",
        "data_possible_orders",
        "data_game_info",
        "data_time_stamp",
        "data_game_phases",
        "data_game",
        "data_game_schedule",
        "data_saved_game",
    ]),

    // Parse a JSON response
    parse: (jsonObject) => {
        if (!Object.prototype.hasOwnProperty.call(jsonObject, "name")) {
            throw new Error("Missing 'name' field in response object.");
        }

        if (!RESPONSES.names.has(jsonObject.name)) {
            throw new Error(`Invalid response name: '${jsonObject.name}'.`);
        }

        if (jsonObject.name === STRINGS.ERROR) {
            throw new Error(`${jsonObject.name}: ${jsonObject.message}`);
        }

        return jsonObject;
    },

    // Check if the response indicates success
    isOk: (response) => response.name === STRINGS.OK,

    // Check if the response contains unique data
    isUniqueData: (response) => {
        return (
            Object.prototype.hasOwnProperty.call(response, "data") &&
            Object.keys(response).length === 3
        );
    },
};
