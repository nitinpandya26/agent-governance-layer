import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {/* basename matches where app/main.py serves this SPA from (see
       dashboard_spa in app/main.py) so client-side routes resolve on a
       hard refresh, not just on in-app navigation. */}
    <BrowserRouter basename="/dashboard">
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
