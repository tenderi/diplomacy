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
import React, { useContext, useEffect, useState } from "react";
import { Connection } from "../../diplomacy/client/connection";
import { ConnectionForm } from "../forms/connection_form";
import { DipStorage } from "../utils/dipStorage";
import { Helmet } from "react-helmet";
import { Navigation } from "../components/navigation";
import { PageContext } from "../components/page_context";
export const ContentConnection = () => {
    const page = useContext(PageContext);
    const [connection, setConnection] = useState(null);

    const handleSubmit = async (data) => {
        // Validate required fields
        const requiredFields = ["hostname", "port", "username", "password", "showServerFields"];
        const missingFields = requiredFields.filter((field) => !data[field]);
        if (missingFields.length > 0) {
            page.error(`Missing fields: ${missingFields.join(", ")}.`);
            return;
        }

        page.info("Connecting...");
        if (connection?.currentConnectionProcessing?.stop) {
            connection.currentConnectionProcessing.stop();
        }

        const newConnection = new Connection(
            data.hostname,
            data.port,
            window.location.protocol.toLowerCase() === "https:"
        );
        newConnection.onReconnectionError = page.onReconnectionError;

        try {
            // Establish connection
            console.log("Connecting to server...");
            await newConnection.connect(page);
            console.log("Connection established:", newConnection);
            setConnection(newConnection); // Maintain the connection state.
            page.connection = newConnection;
            page.success(`Successfully connected to server ${data.username}:${data.port}`);

            // Authenticate user
            const channel = await page.connection.authenticate(data.username, data.password);
            console.log("Channel initialized:", channel);

            // Fetch available maps
            const availableMaps = await channel.getAvailableMaps();
            Object.keys(availableMaps).forEach((mapName) => {
                availableMaps[mapName].powers.sort();
            });
            page.availableMaps = availableMaps;

            // Fetch user games
            const userGameIndices = DipStorage.getUserGames(page.channel.username);
            console.log("User game indices:", userGameIndices);
            if (userGameIndices?.length > 0) {
                const gamesInfo = await channel.getGamesInfo({ games: userGameIndices });
                console.log("Games info:", gamesInfo);
                page.success(`Found ${gamesInfo.length} user games.`);
                page.updateMyGames(gamesInfo);
            }

            // Load games
            page.loadGames({ success: `Account ${data.username} connected.` });
        } catch (error) {
            console.error("Error during connection:", error);
            page.error(`Error while connecting: ${error.message || error}. Please re-try.`);
            setConnection(null);
        }
    };

    useEffect(() => {
        window.scrollTo(0, 0);
    }, []);

    return (
        <main>
            <Helmet>
                <title>Connection | Diplomacy</title>
            </Helmet>
            <Navigation title="Connection" />
            <ConnectionForm onSubmit={handleSubmit} />
        </main>
    );
};
