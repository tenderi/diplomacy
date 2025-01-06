import { Channel } from "./channel";
import { Game } from "../engine/game";

export class NetworkGame {
    constructor(channel, serverGameState) {
        this.local = new Game(serverGameState); // Local instance to manage game
        this.channel = channel;
        this.notificationCallbacks = {};
        this.local.client = this;
    }

    // Callback Management
    addCallback = (notificationName, notificationCallback) => {
        if (!Object.prototype.hasOwnProperty.call(this.notificationCallbacks, notificationName)) {
            this.notificationCallbacks[notificationName] = [];
        }
        if (!this.notificationCallbacks[notificationName].includes(notificationCallback)) {
            this.notificationCallbacks[notificationName].push(notificationCallback);
        }
    };

    clearCallbacks = (notificationName) => {
        if (Object.prototype.hasOwnProperty.call(this.notificationCallbacks, notificationName)) {
            delete this.notificationCallbacks[notificationName];
        }
    };

    clearAllCallbacks = () => {
        this.notificationCallbacks = {};
    };

    notify = (notification) => {
        if (Object.prototype.hasOwnProperty.call(this.notificationCallbacks, notification.name)) {
            this.notificationCallbacks[notification.name].forEach((callback) =>
                setTimeout(() => callback(this, notification), 0)
            );
        }
    };

    // Request Handling
    _req = (channelMethod, parameters) => {
        if (!this.channel) {
            throw new Error("Invalid client game.");
        }
        return channelMethod.apply(this.channel, [parameters, this]);
    };

    synchronize = () => {
        if (!this.channel) {
            throw new Error("Invalid client game.");
        }
        return this._req(Channel.prototype.synchronize, {
            timestamp: this.local.getLatestTimestamp(),
        });
    };

    // Generalized Methods for Game Requests
    createRequestMethod = (methodName) => (parameters) =>
        this._req(Channel.prototype[methodName], parameters);

    // Game Requests API
    getAllPossibleOrders = this.createRequestMethod("getAllPossibleOrders");
    getPhaseHistory = this.createRequestMethod("getPhaseHistory");
    leave = this.createRequestMethod("leaveGame");
    sendGameMessage = this.createRequestMethod("sendGameMessage");
    setOrders = this.createRequestMethod("setOrders");
    clearCenters = this.createRequestMethod("clearCenters");
    clearOrders = this.createRequestMethod("clearOrders");
    clearUnits = this.createRequestMethod("clearUnits");
    wait = this.createRequestMethod("wait");
    noWait = this.createRequestMethod("noWait");
    setWait = (wait, parameters) => (wait ? this.wait(parameters) : this.noWait(parameters));
    vote = this.createRequestMethod("vote");
    save = this.createRequestMethod("save");

    // Admin/Moderator API
    remove = this.createRequestMethod("deleteGame");
    kickPowers = this.createRequestMethod("kickPowers");
    setState = this.createRequestMethod("setState");
    process = this.createRequestMethod("process");
    querySchedule = this.createRequestMethod("querySchedule");
    start = this.createRequestMethod("start");
    pause = this.createRequestMethod("pause");
    resume = this.createRequestMethod("resume");
    cancel = this.createRequestMethod("cancel");
    draw = this.createRequestMethod("draw");

    // Callback Registration Helpers
    createAddCallbackMethod = (name) => (callback) => this.addCallback(name, callback);
    createClearCallbackMethod = (name) => () => this.clearCallbacks(name);

    // Registering Callbacks
    addOnClearedCenters = this.createAddCallbackMethod("cleared_centers");
    addOnClearedOrders = this.createAddCallbackMethod("cleared_orders");
    addOnClearedUnits = this.createAddCallbackMethod("cleared_units");
    addOnPowersControllers = this.createAddCallbackMethod("powers_controllers");
    addOnGameDeleted = this.createAddCallbackMethod("game_deleted");
    addOnGameMessageReceived = this.createAddCallbackMethod("game_message_received");
    addOnGameProcessed = this.createAddCallbackMethod("game_processed");
    addOnGamePhaseUpdate = this.createAddCallbackMethod("game_phase_update");
    addOnGameStatusUpdate = this.createAddCallbackMethod("game_status_update");
    addOnOmniscientUpdated = this.createAddCallbackMethod("omniscient_updated");
    addOnPowerOrdersUpdate = this.createAddCallbackMethod("power_orders_update");
    addOnPowerOrdersFlag = this.createAddCallbackMethod("power_orders_flag");
    addOnPowerVoteUpdated = this.createAddCallbackMethod("power_vote_updated");
    addOnPowerWaitFlag = this.createAddCallbackMethod("power_wait_flag");
    addOnVoteCountUpdated = this.createAddCallbackMethod("vote_count_updated");
    addOnVoteUpdated = this.createAddCallbackMethod("vote_updated");

    // Clearing Callbacks
    clearOnClearedCenters = this.createClearCallbackMethod("cleared_centers");
    clearOnClearedOrders = this.createClearCallbackMethod("cleared_orders");
    clearOnClearedUnits = this.createClearCallbackMethod("cleared_units");
    clearOnPowersControllers = this.createClearCallbackMethod("powers_controllers");
    clearOnGameDeleted = this.createClearCallbackMethod("game_deleted");
    clearOnGameMessageReceived = this.createClearCallbackMethod("game_message_received");
    clearOnGameProcessed = this.createClearCallbackMethod("game_processed");
    clearOnGamePhaseUpdate = this.createClearCallbackMethod("game_phase_update");
    clearOnGameStatusUpdate = this.createClearCallbackMethod("game_status_update");
    clearOnOmniscientUpdated = this.createClearCallbackMethod("omniscient_updated");
    clearOnPowerOrdersUpdate = this.createClearCallbackMethod("power_orders_update");
    clearOnPowerOrdersFlag = this.createClearCallbackMethod("power_orders_flag");
    clearOnPowerVoteUpdated = this.createClearCallbackMethod("power_vote_updated");
    clearOnPowerWaitFlag = this.createClearCallbackMethod("power_wait_flag");
    clearOnVoteCountUpdated = this.createClearCallbackMethod("vote_count_updated");
    clearOnVoteUpdated = this.createClearCallbackMethod("vote_updated");
}
