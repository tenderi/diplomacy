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

import { STRINGS } from "../utils/strings";
import { UTILS } from "../utils/utils";
import { REQUESTS } from "../communication/requests";
import { RESPONSES } from "../communication/responses";
import { NOTIFICATIONS } from "../communication/notifications";
import { RESPONSE_MANAGERS } from "./response_managers";
import { NOTIFICATION_MANAGERS } from "./notification_managers";
import { Future } from "../utils/future";
import { FutureEvent } from "../utils/future_event";
import { RequestFutureContext } from "./request_future_context";
import { Diplog } from "../utils/diplog";

class Reconnection {
    constructor(connection) {
        this.connection = connection;
        this.gamesPhases = {};
        this.expectedGamesCount = 0;
        this.synchronizedGamesCount = 0;
    }

    generateSyncCallback(game) {
        return (serverSyncResponse) => {
            const { game_id, game_role } = game.local;
            this.gamesPhases[game_id][game_role] = serverSyncResponse;
            this.synchronizedGamesCount += 1;

            if (this.synchronizedGamesCount === this.expectedGamesCount) {
                this.syncDone();
            }
        };
    }

    reconnect() {
        Object.values(this.connection.requestsWaitingResponses).forEach((context) => {
            context.request.re_sent = true;
        });

        const waitingResponses = Object.keys(this.connection.requestsWaitingResponses).length;
        const existingRequests = Object.keys(this.connection.requestsToSend).length;

        Object.assign(this.connection.requestsToSend, this.connection.requestsWaitingResponses);
        const newRequestCount = Object.keys(this.connection.requestsToSend).length;

        if (newRequestCount !== waitingResponses + existingRequests) {
            throw new Error("Programming error: mismatch in request counts.");
        }

        this.connection.requestsWaitingResponses = {};

        const updatedRequestsToSend = {};
        Object.values(this.connection.requestsToSend).forEach((context) => {
            if (context.request.name === STRINGS.SYNCHRONIZE) {
                context.future.setException(
                    new Error(`Sync request invalidated for game ID ${context.request.game_id}`)
                );
            } else {
                updatedRequestsToSend[context.request.request_id] = context;
            }
        });
        this.connection.requestsToSend = updatedRequestsToSend;

        Object.values(this.connection.channels).forEach((channel) => {
            Object.values(channel.game_id_to_instances).forEach((gis) => {
                gis.getGames().forEach((game) => {
                    const { game_id, role } = game.local;
                    if (!(game_id in this.gamesPhases)) {
                        this.gamesPhases[game_id] = {};
                    }
                    this.gamesPhases[game_id][role] = null;
                    this.expectedGamesCount += 1;
                });
            });
        });

        if (this.expectedGamesCount > 0) {
            Object.values(this.connection.channels).forEach((channel) => {
                Object.values(channel.game_id_to_instances).forEach((gis) => {
                    gis.getGames().forEach((game) => {
                        game.synchronize().then(this.generateSyncCallback(game));
                    });
                });
            });
        } else {
            this.syncDone();
        }
    }

    syncDone() {
        const updatedRequestsToSend = {};
        Object.values(this.connection.requestsToSend).forEach((context) => {
            const { request } = context;
            const { name, phase, game_id, game_role } = request;

            if (REQUESTS.isPhaseDependent(name)) {
                const serverPhase = this.gamesPhases[game_id][game_role]?.phase;
                if (phase !== serverPhase) {
                    context.future.setException(
                        new Error(
                            `Game ${game_id}: Request ${name} phase mismatch (request: ${phase}, server: ${serverPhase}).`
                        )
                    );
                    return;
                }
            }
            updatedRequestsToSend[request.request_id] = context;
        });

        Diplog.info(
            `Kept ${Object.keys(updatedRequestsToSend).length}/${Object.keys(
                this.connection.requestsToSend
            ).length} old requests to send.`
        );
        this.connection.requestsToSend = updatedRequestsToSend;

        Object.values(updatedRequestsToSend).forEach((context) => {
            this.connection.__writeRequest(context);
        });

        this.connection.isReconnecting.set();
        Diplog.info("Reconnection completed.");
    }
}

class ConnectionProcessing {
    constructor(connection, logger = Diplog) {
        this.connection = connection;
        this.logger = logger;
        this.isConnected = false;
        this.attemptIndex = 1;
        this.timeoutID = null;
    }

    handleError(error) {
        this.connection.isConnecting.set(error);
    }

    handleSocketOpen() {
        this.isConnected = true;

        if (this.timeoutID) {
            clearTimeout(this.timeoutID);
            this.timeoutID = null;
        }

        this.connection.socket.onmessage = this.connection.onSocketMessage;
        this.connection.socket.onclose = this.connection.onSocketClose;

        this.connection.currentConnectionProcessing = null;
        this.connection.isConnecting.set();
        this.logger.info("Connection succeeded.");
    }

    handleSocketTimeout() {
        if (!this.isConnected) {
            this.connection.socket.close();
            if (this.attemptIndex >= UTILS.NB_CONNECTION_ATTEMPTS) {
                this.connection.isConnecting.set(
                    new Error(`Connection failed after ${UTILS.NB_CONNECTION_ATTEMPTS} attempts.`)
                );
                return;
            }

            this.logger.warn(`Connection attempt ${this.attemptIndex}/${UTILS.NB_CONNECTION_ATTEMPTS} failed. Retrying...`);
            this.attemptIndex += 1;
            setTimeout(() => this.tryConnect(), 0);
        }
    }

    tryConnect() {
        try {
            this.connection.socket = new WebSocket(this.connection.getUrl());
            this.connection.socket.onopen = () => this.handleSocketOpen();
            this.timeoutID = setTimeout(() => this.handleSocketTimeout(), UTILS.ATTEMPT_DELAY_SECONDS * 1000);
        } catch (error) {
            this.handleError(error);
        }
    }

    process() {
        this.connection.isConnecting.clear();
        if (this.connection.socket) {
            this.connection.socket.close();
        }
        this.tryConnect();
        return this.connection.isConnecting.wait();
    }

    stop() {
        if (!this.isConnected && this.timeoutID) {
            clearTimeout(this.timeoutID);
            this.timeoutID = null;
        }
    }
}

export class Connection {
    constructor(hostname, port, useSSL) {
        this.protocol = useSSL ? "wss" : "ws";
        this.hostname = hostname;
        this.port = port;

        this.socket = null;
        this.isConnecting = new FutureEvent();
        this.isReconnecting = new FutureEvent();
        this.channels = {};
        this.requestsToSend = {};
        this.requestsWaitingResponses = {};
        this.currentConnectionProcessing = null;
        this.closed = false;

        this.onSocketMessage = this.onSocketMessage.bind(this);
        this.onSocketClose = this.onSocketClose.bind(this);
        this.isReconnecting.set();

        this.onReconnection = null;
        this.onReconnectionError = null;
    }

    getUrl() {
        return `${this.protocol}://${this.hostname}:${this.port}`;
    }

    onSocketMessage(messageEvent) {
        try {
            const message = JSON.parse(messageEvent.data);

            if (message.request_id) {
                const context = this.requestsWaitingResponses[message.request_id];
                if (!context) {
                    Diplog.error(`Unknown request ID: ${message.request_id}`);
                    return;
                }

                delete this.requestsWaitingResponses[message.request_id];

                try {
                    const parsedResponse = RESPONSES.parse(message);
                    context.future.setResult(RESPONSE_MANAGERS.handleResponse(context, parsedResponse));
                } catch (error) {
                    context.future.setException(error);
                }
            } else if (message.notification_id) {
                NOTIFICATION_MANAGERS.handleNotification(this, NOTIFICATIONS.parse(message));
            } else {
                Diplog.error("Unknown socket message received.");
            }
        } catch (error) {
            Diplog.error("Error processing socket message:", error);
        }
    }

    onSocketClose() {
        if (this.closed) {
            Diplog.info("Socket disconnected.");
            return;
        }

        Diplog.error("Socket closed unexpectedly. Attempting to reconnect...");
        this.isReconnecting.clear();
        this.__connect()
            .then(() => {
                new Reconnection(this).reconnect();
                if (this.onReconnection) {
                    this.onReconnection();
                }
            })
            .catch((error) => {
                if (this.onReconnectionError) {
                    this.onReconnectionError(error);
                } else {
                    throw error;
                }
            });
    }

    __connect(logger) {
        if (this.currentConnectionProcessing) {
            this.currentConnectionProcessing.stop();
            this.currentConnectionProcessing = null;
        }

        this.currentConnectionProcessing = new ConnectionProcessing(this, logger);
        return this.currentConnectionProcessing.process();
    }

    __writeRequest(requestContext) {
        const request = requestContext.request;
        const writeFuture = new Future();

        const onConnected = () => {
            this.socket.send(JSON.stringify(request));
            this.requestsWaitingResponses[request.request_id] = requestContext;
            delete this.requestsToSend[request.request_id];
            writeFuture.setResult(null);
        };

        const onError = (error) => {
            this.requestsToSend[request.request_id] = requestContext;
            Diplog.error(`Error sending request ${request.request_id}`, error);
            writeFuture.setException(error);
        };

        const waitEvent = request.name === STRINGS.SYNCHRONIZE ? this.isConnecting : this.isReconnecting;
        waitEvent.wait().then(onConnected, onError);

        return writeFuture.promise();
    }

    connect(logger) {
        Diplog.info("Attempting to connect...");
        return this.__connect(logger);
    }

    send(request, game = null) {
        const requestContext = new RequestFutureContext(request, this, game);
        this.__writeRequest(requestContext);
        return requestContext.future;
    }

    authenticate(username, password) {
        return this.send(REQUESTS.create("sign_in", { username, password })).promise();
    }

    close() {
        this.closed = true;
        if (this.socket) {
            this.socket.close();
        }
    }
}
