import { UTILS } from "../utils/utils";
import { REQUESTS } from "../communication/requests";
import { RESPONSES } from "../communication/responses";
import { NOTIFICATIONS } from "../communication/notifications";
import { RESPONSE_MANAGERS } from "./response_managers";
import { NOTIFICATION_MANAGERS } from "./notification_managers";
import { Diplog } from "../utils/diplog";
import { Future } from "../utils/future";
import { FutureEvent } from "../utils/future_event";
import { RequestFutureContext } from "../client/request_future_context.js";
import { Channel } from "../client/channel.js";

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

        this.connection.requestsWaitingResponses = {};

        Object.values(this.connection.channels).forEach((channel) => {
            Object.values(channel.game_id_to_instances).forEach((gis) => {
                gis.getGames().forEach((game) => {
                    const { game_id, role } = game.local;
                    if (!this.gamesPhases[game_id]) {
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
        Diplog.info("Reconnection completed.");
        this.connection.isReconnecting.set();
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

    handleSocketOpen = () => {
        this.isConnected = true;
        if (this.timeoutID) clearTimeout(this.timeoutID);

        this.connection.socket.onmessage = this.connection.onSocketMessage;
        this.connection.socket.onclose = this.connection.onSocketClose;

        this.connection.isConnecting.set();
        this.logger.info("Connection succeeded.");
    };

    handleSocketTimeout = () => {
        if (!this.isConnected) {
            this.connection.socket.close();
            if (this.attemptIndex >= UTILS.NB_CONNECTION_ATTEMPTS) {
                this.connection.isConnecting.set(
                    new Error(`Connection failed after ${UTILS.NB_CONNECTION_ATTEMPTS} attempts.`)
                );
                return;
            }

            this.logger.warn(`Connection attempt ${this.attemptIndex} failed. Retrying...`);
            this.attemptIndex += 1;
            setTimeout(this.tryConnect, UTILS.ATTEMPT_DELAY_SECONDS * 1000);
        }
    };

    tryConnect = () => {
        try {
            this.connection.socket = new WebSocket(this.connection.getUrl());
            this.connection.socket.onopen = this.handleSocketOpen;
            this.timeoutID = setTimeout(this.handleSocketTimeout, UTILS.ATTEMPT_DELAY_SECONDS * 1000);
        } catch (error) {
            this.connection.isConnecting.set(error);
        }
    };

    stop() {
        // Clear the timeout if it exists
        if (this.timeoutID) {
            clearTimeout(this.timeoutID);
            this.timeoutID = null;
        }

        // Reset isConnected flag
        this.isConnected = false;

        // Close the socket if it exists and is not already closed
        if (this.connection.socket && this.connection.socket.readyState !== WebSocket.CLOSED) {
            this.connection.socket.close();
        }

        this.logger.info("Connection process stopped.");
    }

    process() {
        this.connection.isConnecting.clear();
        if (this.connection.socket) this.connection.socket.close();
        this.tryConnect();
        return this.connection.isConnecting.wait();
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
        this.requestsToSend = {};
        this.requestsWaitingResponses = {};
        this.channels = {}; // Initialize the channels property
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
        this.__connect().then(() => {
            new Reconnection(this).reconnect();
            if (this.onReconnection) this.onReconnection();
        }).catch((error) => {
            if (this.onReconnectionError) this.onReconnectionError(error);
            else throw error;
        });
    }

    __connect(logger) {
        if (this.currentConnectionProcessing) this.currentConnectionProcessing.stop();

        this.currentConnectionProcessing = new ConnectionProcessing(this, logger);
        return this.currentConnectionProcessing.process();
    }

    __writeRequest(requestContext) {
        const request = requestContext.request;
        const writeFuture = new Future();

        const onConnected = () => {
            this.socket.send(JSON.stringify(request));
            this.requestsWaitingResponses[request.request_id] = requestContext;
            writeFuture.setResult(null);
        };

        const onError = (error) => {
            this.requestsToSend[request.request_id] = requestContext;
            Diplog.error(`Error sending request ${request.request_id}`, error);
            writeFuture.setException(error);
        };

        this.isReconnecting.wait().then(onConnected, onError);
        return writeFuture.promise();
    }

    connect(logger) {
        Diplog.info("Attempting to connect...");
        return this.__connect(logger);
    }

    send(request) {
        const requestContext = new RequestFutureContext(request, this);
        this.__writeRequest(requestContext);
        return requestContext.future.promise();
    }        
    
    authenticate(username, password) {
        const request = REQUESTS.create("sign_in", { username, password });
        
        return this.send(request)
            .then((response) => {
                if (!response || !response.token) {
                    throw new Error("Authentication failed: Invalid server response.");
                }
                this.token = response.token;
                this.channels[response.token] = new Channel(this, username, response.token); // Initialize channel
                return this.channels[response.token];
            })
            .catch((error) => {
                Diplog.error("Authentication error:", error);
                throw error;
            });
    }

    close() {
        this.closed = true;
        if (this.socket) this.socket.close();
    }
}
