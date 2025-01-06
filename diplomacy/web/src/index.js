// ==============================================================================
// Copyright (C) 2019 - Philip Paquette, Steven Bocco
//
//  This program is free software: you can redistribute it and/or modify it under
//  the terms of the GNU Affero General Public License as published by the Free
//  Software Foundation, either version 3 of the License, or (at your option)
//  any later version.
//
//  This program is distributed in the hope that it will be useful, but WITHOUT
//  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
//  FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
//  details.
//
//  You should have received a copy of the GNU Affero General Public License along
//  with this program.  If not, see <https://www.gnu.org/licenses/>.
// ==============================================================================
import React from 'react';
import ReactDOM from 'react-dom/client'; // Updated import for React 18+
import { HelmetProvider } from 'react-helmet-async'; // Import HelmetProvider
import { Page } from "./gui/pages/page";
import 'popper.js';
import 'bootstrap/dist/js/bootstrap';
import 'bootstrap/dist/css/bootstrap.min.css';
import './index.css';

// ========================================

const root = ReactDOM.createRoot(document.getElementById('root')); // Use createRoot for React 18+
root.render(
  <React.StrictMode>
    <HelmetProvider> {/* Wrap your app with HelmetProvider */}
      <Page />
    </HelmetProvider>
  </React.StrictMode>
);
