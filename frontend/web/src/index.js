import React, { useState } from "react";
import ReactDOM from "react-dom/client";
import MentalWellness from "./components/MentalWellness";
import NutritionalIntelligence from "./components/NutritionalIntelligence";
import MedicineVerification from "./components/MedicineVerification";
import PatientMonitoring from "./components/PatientMonitoring";

const tabs = [
  { id: "mental", label: "Mental & Physiological Wellness" },
  { id: "nutrition", label: "Personalized Nutritional Intelligence" },
  { id: "medicine", label: "Medicine Intelligence & Verification" },
  { id: "monitoring", label: "Smart Patient Monitoring" },
];

const App = () => {
  const [activeTab, setActiveTab] = useState("mental");

  return (
    <>
      <style>{`
        * { box-sizing: border-box; }
        html, body, #root { margin: 0; min-height: 100%; }
        body {
          background: #edf3ef;
          color: #172d32;
          font-family: Arial, sans-serif;
        }
        .module-shell {
          min-height: 100vh;
          background: linear-gradient(180deg, #f3f8f5 0%, #edf4ef 100%);
        }
        .module-header {
          position: sticky;
          top: 0;
          z-index: 10;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 18px 20px 14px;
          border-bottom: 1px solid #d9e6df;
          background: rgba(255, 255, 255, 0.8);
          backdrop-filter: blur(12px);
        }
        .module-inner {
          width: min(1280px, 100%);
        }
        .module-nav {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
          justify-content: center;
        }
        .module-tab {
          border: 1px solid #d1e4dc;
          border-radius: 999px;
          background: #fff;
          color: #214d46;
          padding: 10px 18px;
          font-size: 0.78rem;
          font-weight: 700;
          letter-spacing: 0.02em;
          cursor: pointer;
          transition: all 180ms ease;
        }
        .module-tab:hover {
          border-color: #9cc5b4;
          transform: translateY(-1px);
        }
        .module-tab.active {
          color: #fff;
          background: linear-gradient(135deg, #1a7e76 0%, #0f5e57 100%);
          border-color: #0f5e57;
          box-shadow: 0 8px 18px rgba(15, 94, 87, 0.18);
        }
        @media (max-width: 700px) {
          .module-header {
            padding-left: 12px;
            padding-right: 12px;
          }
          .module-nav {
            justify-content: flex-start;
            overflow-x: auto;
            white-space: nowrap;
          }
        }
      `}</style>

      <div className="module-shell">
        <header className="module-header">
          <div className="module-inner">
            <nav className="module-nav" aria-label="Healthcare intelligence modules">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  className={`module-tab ${activeTab === tab.id ? "active" : ""}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>
        </header>

        {activeTab === "mental" && <MentalWellness />}
        {activeTab === "nutrition" && <NutritionalIntelligence />}
        {activeTab === "medicine" && <MedicineVerification />}
        {activeTab === "monitoring" && <PatientMonitoring />}
      </div>
    </>
  );
};

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
