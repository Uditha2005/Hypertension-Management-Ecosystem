import React from "react";
import ReactDOM from "react-dom/client";

const App = () => (
  <div style={{ fontFamily: "Arial, sans-serif", padding: "24px" }}>
    <h1>Hypertension Management Ecosystem</h1>
    <p>Web frontend scaffold is ready.</p>
  </div>
);

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
