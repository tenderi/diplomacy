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
/** Class Future (like Python's Tornado future). **/
export class Future {
    constructor() {
        this.__resolveFn = null; // Function to resolve the promise
        this.__rejectFn = null; // Function to reject the promise
        this.__done = false; // Track whether the promise is completed

        // Create a promise and store its resolve/reject handlers
        this.__promise = new Promise((resolve, reject) => {
            this.__resolveFn = resolve;
            this.__rejectFn = reject;
        });
    }

    /**
     * Returns the internal promise.
     * @returns {Promise}
     */
    promise() {
        return this.__promise;
    }

    /**
     * Resolves the promise with the given result.
     * @param {*} result - The result to resolve the promise with.
     */
    setResult(result) {
        if (this.isDone()) {
            console.warn("Future.setResult called on a completed promise.");
            return;
        }
        this.__done = true;
        this.__resolveFn(result);
    }

    /**
     * Rejects the promise with the given exception.
     * @param {Error} exception - The exception to reject the promise with.
     */
    setException(exception) {
        if (this.isDone()) {
            console.warn("Future.setException called on a completed promise.");
            return;
        }
        this.__done = true;
        this.__rejectFn(exception);
    }

    /**
     * Checks if the promise has been resolved or rejected.
     * @returns {boolean} True if the promise is completed.
     */
    isDone() {
        return this.__done;
    }
    done() {
        return this.__isDone;
    }
}
