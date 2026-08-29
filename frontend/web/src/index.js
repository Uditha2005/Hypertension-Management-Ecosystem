import React from "react";
import ReactDOM from "react-dom/client";
import PatientMonitoring from "./components/PatientMonitoring";

const App = () => <PatientMonitoring />;

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
