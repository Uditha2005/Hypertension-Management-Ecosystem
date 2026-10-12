import React from "react";
import ReactDOM from "react-dom/client";
import TrayVerification from "./components/TrayVerification";

const App = () => (
  <>
    <div style={{ fontFamily: "Arial, sans-serif", padding: "24px" }}>
      <h1>Hypertension Management Ecosystem</h1>
    </div>

    <TrayVerification />
  </>
);

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);