import React, { useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom/client";

import MentalWellness from "./components/MentalWellness";
import NutritionalIntelligence from "./components/NutritionalIntelligence";
import TrayVerification from "./components/TrayVerification";
import PatientMonitoring from "./components/PatientMonitoring";
import PhysiologicalRecommendations from "./components/PhysiologicalRecommendations";

import HomePage, {
  CARE_MODULES,
  CareIcon,
} from "./components/HomePage";

const tabs = [
  {
    id: "home",
    navLabel: "Home",
    title: "Home",
    icon: "home",
  },
  ...CARE_MODULES,
  {
    id: "physiological",
    navLabel: "Recommendations",
    title: "Physiological Recommendations (XAI)",
    icon: "wellness",
  },
];

const App = () => {
  const [activeTab, setActiveTab] = useState("home");
  const contentRef = useRef(null);
  const firstRender = useRef(true);

  useEffect(() => {
    const current = tabs.find((tab) => tab.id === activeTab);
    document.title = `${current?.title || "Home"} | HyperCare`;

    if (firstRender.current) {
      firstRender.current = false;
      return;
    }

    window.scrollTo({ top: 0, behavior: "auto" });
    contentRef.current?.focus({ preventScroll: true });
  }, [activeTab]);

  return (
    <div className="hc-portal">
      <a className="hc-skip" href="#hc-content">
        Skip to content
      </a>

      <header className="hc-header">
        <div className="hc-header-inner">
          <button
            type="button"
            className="hc-brand"
            onClick={() => setActiveTab("home")}
            aria-label="HyperCare Home"
          >
            <span className="hc-brand-mark">
              <CareIcon name="wellness" />
            </span>

            <span>
              <strong>HyperCare</strong>
              <small>Elderly-care management</small>
            </span>
          </button>

          <nav className="hc-nav" aria-label="Care workspaces">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={`hc-nav-button ${
                  activeTab === tab.id ? "is-active" : ""
                }`}
                aria-current={
                  activeTab === tab.id ? "page" : undefined
                }
                title={tab.title}
                onClick={() => setActiveTab(tab.id)}
              >
                <CareIcon name={tab.icon} />
                <span>{tab.navLabel}</span>
              </button>
            ))}
          </nav>

          <span className="hc-research-label">
            Research prototype
          </span>
        </div>
      </header>

      <div
        id="hc-content"
        ref={contentRef}
        tabIndex={-1}
        className="hc-content"
      >
        {activeTab === "home" && (
          <HomePage onNavigate={setActiveTab} />
        )}

        {activeTab === "mental" && <MentalWellness />}

        {activeTab === "nutrition" && (
          <NutritionalIntelligence />
        )}

        {activeTab === "medicine" && <TrayVerification />}

        {activeTab === "monitoring" && <PatientMonitoring />}

        {activeTab === "physiological" && (
          <PhysiologicalRecommendations />
        )}
      </div>
    </div>
  );
};

const root = ReactDOM.createRoot(
  document.getElementById("root")
);

root.render(<App />);