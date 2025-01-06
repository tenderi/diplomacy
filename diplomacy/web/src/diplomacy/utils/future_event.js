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
import {Future} from "./future";

/** Class FutureEvent (like Python's Tornado FutureEvent). **/
export class FutureEvent {
    constructor() {
        this.__future = new Future(); // Ensure Future is correctly initialized
    }

    /**
     * Sets the future's result or exception based on the input.
     * @param {Error|null} error - If null, resolves the future; otherwise, rejects it.
     */
    set(error) {
        if (!this.__future.isDone()) { // Use isDone() instead of done()
            if (error) {
                this.__future.setException(error);
            } else {
                this.__future.setResult(null);
            }
        }
    }

    /**
     * Clears the future, reinitializing it.
     */
    clear() {
        if (this.__future.isDone()) {
            this.__future = new Future();
        }
    }

    /**
     * Returns a promise that resolves or rejects based on the future's state.
     * @returns {Promise} - The underlying promise.
     */
    wait() {
        return this.__future.promise();
    }

    /**
     * Checks if the future is still waiting to be resolved or rejected.
     * @returns {boolean} - True if the future is not yet completed.
     */
    isWaiting() {
        return !this.__future.isDone();
    }
}