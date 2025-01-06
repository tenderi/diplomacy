// ==============================================================================
// Copyright (C) 2019 - Philip Paquette, Steven Bocco
//
// This program is free software: you can redistribute it and/or modify it under
// the terms of the GNU Affero General Public License as published by the Free
// Software Foundation, either version 3 of the License, or (at your option) any
// later version.
//
// This program is distributed in the hope that it will be useful, but WITHOUT
// ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
// FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
// details.
//
// You should have received a copy of the GNU Affero General Public License along
// with this program.  If not, see <https://www.gnu.org/licenses/>.
// ==============================================================================

class Dict {}

/** Utility functions. **/
export const UTILS = {
    NB_CONNECTION_ATTEMPTS: 12,
    ATTEMPT_DELAY_SECONDS: 5,
    REQUEST_TIMEOUT_SECONDS: 30,

    /** Generate a random integer within the range [from, to). **/
    randomInteger: (from, to) => Math.floor(Math.random() * (to - from) + from),

    /** Generate a unique ID string based on current time and random integers. **/
    createID: () =>
        `${Date.now()}${Array.from({ length: 5 }, () => UTILS.randomInteger(1e9, 1e10)).join("")}`,

    /** Generate a game-specific ID using username and current time. **/
    createGameID: (username) => `${username}_${Date.now()}`,

    /** Get the current date and time as a locale string with milliseconds. **/
    date: () => {
        const d = new Date();
        return `${d.toLocaleString()}.${d.getMilliseconds()}`;
    },

    /** Convert microseconds to a JavaScript Date object. **/
    microsecondsToDate: (time) => new Date(Math.floor(time / 1000)),

    /** Binary search utilities for sorted arrays. **/
    binarySearch: {
        find: (array, element) => {
            let low = 0;
            let high = array.length - 1;

            while (low <= high) {
                const mid = Math.floor((low + high) / 2);
                if (array[mid] === element) return mid;
                if (array[mid] < element) low = mid + 1;
                else high = mid - 1;
            }
            return -1;
        },

        insert: (array, element) => {
            let low = 0;
            let high = array.length - 1;

            while (low <= high) {
                const mid = Math.floor((low + high) / 2);
                if (array[mid] === element) return mid;
                if (array[mid] < element) low = mid + 1;
                else high = mid - 1;
            }
            array.splice(low, 0, element);
            return low;
        },
    },

    javascript: {
        /** Check if an array is empty or undefined. **/
        arrayIsEmpty: (array) => !array?.length,

        /** Check if an array exists and has elements. **/
        hasArray: (array) => !!array?.length,

        /** Clear all keys in an object. **/
        clearObject: (obj) => {
            Object.keys(obj).forEach((key) => delete obj[key]);
        },

        /** Convert an array to a dictionary using a specified field as the key. **/
        arrayToDict: (array, field) =>
            array.reduce((dict, entry) => {
                dict[entry[field]] = entry;
                return dict;
            }, {}),

        /** Count the number of keys in an object. **/
        count: (obj) => Object.keys(obj).length,

        /** Add a unique value to an array within an object under a specified key. **/
        extendArrayWithUniqueValues: (obj, key, value) => {
            obj[key] = obj[key] || [];
            if (!obj[key].includes(value)) obj[key].push(value);
        },

        /** Add a value to a tree-like object structure based on a path. **/
        extendTreeValue: (obj, path, value, allowMultipleValues = true) => {
            let current = obj;

            path.slice(0, -1).forEach((step) => {
                current[step] = current[step] || new Dict();
                current = current[step];
            });

            const leaf = path[path.length - 1];
            current[leaf] = current[leaf] || [];

            if (allowMultipleValues || !current[leaf].includes(value)) {
                current[leaf].push(value);
            }
        },

        /** Retrieve a value from a tree-like object structure based on a path. **/
        getTreeValue: (obj, path) => {
            let current = obj;
            for (const step of path) {
                if (!(step in current)) return null;
                current = current[step];
            }
            return current instanceof Dict ? Object.keys(current) : current;
        },
    },

    html: {
        // Unicode symbols for UI elements.
        UNICODE_LEFT_ARROW: "\u25C0",
        UNICODE_RIGHT_ARROW: "\u25B6",
        UNICODE_TOP_ARROW: "\u25BC",
        UNICODE_BOTTOM_ARROW: "\u25B2",
        CROSS: "\u00D7",
        UNICODE_SMALL_RIGHT_ARROW: "\u2192",
        UNICODE_SMALL_LEFT_ARROW: "\u2190",

        /** Check if an element is a `<select>`. **/
        isSelect: (element) => element.tagName.toLowerCase() === "select",

        /** Check if an element is an `<input>`. **/
        isInput: (element) => element.tagName.toLowerCase() === "input",

        /** Check if an element is a checkbox input. **/
        isCheckBox: (element) =>
            UTILS.html.isInput(element) && element.type === "checkbox",

        /** Check if an element is a radio button input. **/
        isRadioButton: (element) =>
            UTILS.html.isInput(element) && element.type === "radio",

        /** Check if an element is a text input. **/
        isTextInput: (element) =>
            UTILS.html.isInput(element) && element.type === "text",

        /** Check if an element is a password input. **/
        isPasswordInput: (element) =>
            UTILS.html.isInput(element) && element.type === "password",
    },
};
