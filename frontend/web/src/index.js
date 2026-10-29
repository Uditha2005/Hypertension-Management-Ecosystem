import React, { useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom/client";

import MentalWellness from "./components/MentalWellness";
import NutritionalIntelligence from "./components/NutritionalIntelligence";
import TrayVerification from "./components/TrayVerification";
import PatientMonitoring from "./components/PatientMonitoring";
import PhysiologicalRecommendations from "./components/PhysiologicalRecommendations";
import NotificationHistory from "./components/NotificationHistory";
import PatientDashboard from "./components/PatientDashboard";

import HomePage, {
  CARE_MODULES,
  CareIcon,
} from "./components/HomePage";

import Login from "./Login";
import Register from "./Register";
import "./Auth.css";

const API_URL = "http://localhost:5000/api/auth";
const TOKEN_KEY = "hypercare-auth-token";
const ACTIVE_TAB_KEY = "hypercare-active-web-tab";

const caregiverTabs = [
  {
    id: "home",
    navLabel: "Home",
    title: "Home",
    icon: "home",
  },
  ...CARE_MODULES,
  {
    id: "notifications",
    navLabel: "Notifications",
    title: "Notification History",
    icon: "monitoring",
  },
  {
    id: "physiological",
    navLabel: "Recommendations",
    title: "Physiological Recommendations (XAI)",
    icon: "wellness",
  },
];

const patientTabs = [
  {
    id: "patient-profile",
    navLabel: "My Health Profile",
    title: "My Health Profile",
    icon: "wellness",
  },
  {
    id: "patient-assessment",
    navLabel: "Latest Assessment",
    title: "Latest Assessment",
    icon: "monitoring",
  },
  {
    id: "patient-xai",
    navLabel: "AI & SHAP",
    title: "AI Assessment Explanation",
    icon: "wellness",
  },
  {
    id: "patient-recommendations",
    navLabel: "Recommendations",
    title: "My Recommendations",
    icon: "wellness",
  },
  {
    id: "patient-history",
    navLabel: "Assessment History",
    title: "Assessment History",
    icon: "monitoring",
  },
  {
    id: "patient-falls",
    navLabel: "My Fall History",
    title: "My Fall History",
    icon: "monitoring",
  },
];

const App = () => {
  const [activeTab, setActiveTab] = useState("home");
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState("login");
  const [checkingSession, setCheckingSession] = useState(true);
  const [logoutError, setLogoutError] = useState("");

  const contentRef = useRef(null);
  const firstRender = useRef(true);

  const isPatient = user?.role === "patient";
  const tabs = isPatient ? patientTabs : caregiverTabs;

  // Restore and validate the current browser session.
  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      let token;

      try {
        token = window.sessionStorage.getItem(TOKEN_KEY);
      } catch {
        token = null;
      }

      if (!token) {
        if (!cancelled) {
          setCheckingSession(false);
        }
        return;
      }

      try {
        const response = await fetch(`${API_URL}/me`, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        const data = await response.json();

        if (!response.ok || !data.user) {
          throw new Error("Session expired");
        }

        if (!cancelled) {
          setUser(data.user);
          setActiveTab("patient-profile");
        }
      } catch {
        try {
          window.sessionStorage.removeItem(TOKEN_KEY);
          window.sessionStorage.removeItem(ACTIVE_TAB_KEY);
        } catch {
          // Storage may be unavailable.
        }

        if (!cancelled) {
          setUser(null);
          setAuthMode("login");
          setActiveTab("home");
        }
      } finally {
        if (!cancelled) {
          setCheckingSession(false);
        }
      }
    }

    restoreSession();

    return () => {
      cancelled = true;
    };
  }, []);

  // Ensure the selected tab is allowed for the user's role.
  useEffect(() => {
    if (!user) return;

    if (!tabs.some((tab) => tab.id === activeTab)) {
      setActiveTab(isPatient ? "patient-profile" : "home");
    }
  }, [activeTab, user?.role]);

  // Remember the active tab and update the page title.
  useEffect(() => {
    try {
      window.sessionStorage.setItem(
        ACTIVE_TAB_KEY,
        activeTab
      );
    } catch {
      // Navigation works without session storage.
    }

    const current = tabs.find(
      (tab) => tab.id === activeTab
    );

    document.title = `${current?.title || "Home"} | HyperCare`;

    if (firstRender.current) {
      firstRender.current = false;
      return;
    }

    window.scrollTo({
      top: 0,
      behavior: "auto",
    });

    contentRef.current?.focus({
      preventScroll: true,
    });
  }, [activeTab, user?.role]);

  function handleAuthenticated(data) {
    if (!data?.token || !data?.user) {
      setLogoutError(
        "The server returned an invalid authentication response."
      );
      return;
    }

    try {
      window.sessionStorage.setItem(TOKEN_KEY, data.token);
      window.sessionStorage.removeItem(ACTIVE_TAB_KEY);
    } catch {
      setLogoutError(
        "Browser session storage is unavailable. Enable it and try again."
      );
      return;
    }

    setUser(data.user);
    setLogoutError("");
    setActiveTab(
      data.user.role === "patient"
        ? "patient-profile"
        : "home"
    );
  }

  async function handleLogout() {
    let token;

    try {
      token = window.sessionStorage.getItem(TOKEN_KEY);
    } catch {
      token = null;
    }

    try {
      if (token) {
        const response = await fetch(`${API_URL}/logout`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          throw new Error(
            "Could not confirm logout with the server."
          );
        }
      }

      setLogoutError("");
    } catch (error) {
      setLogoutError(
        `${error.message} This browser session will still be cleared.`
      );
    } finally {
      try {
        window.sessionStorage.removeItem(TOKEN_KEY);
        window.sessionStorage.removeItem(ACTIVE_TAB_KEY);
      } catch {
        // Continue to the sign-in screen.
      }

      setUser(null);
      setAuthMode("login");
      setActiveTab("home");
    }
  }

  if (checkingSession) {
    return (
      <div className="auth-loading" role="status">
        Checking your session...
      </div>
    );
  }

  if (!user) {
    return (
      <>
        {logoutError && (
          <div
            className="auth-session-message"
            role="alert"
          >
            {logoutError}
          </div>
        )}

        {authMode === "login" ? (
          <Login
            onLogin={handleAuthenticated}
            onRegister={() => {
              setLogoutError("");
              setAuthMode("register");
            }}
          />
        ) : (
          <Register
            onRegisterSuccess={handleAuthenticated}
            onLogin={() => {
              setLogoutError("");
              setAuthMode("login");
            }}
          />
        )}
      </>
    );
  }

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
            onClick={() =>
              setActiveTab(
                isPatient ? "patient-profile" : "home"
              )
            }
            aria-label="HyperCare Home"
          >
            <span className="hc-brand-mark">
              <CareIcon name="wellness" />
            </span>

            <span>
              <strong>HyperCare</strong>
              <small>
                {isPatient
                  ? "Patient Portal"
                  : "Elderly-care management"}
              </small>
            </span>
          </button>

          <nav
            className="hc-nav"
            aria-label={
              isPatient ? "Patient dashboard sections" : "Care workspaces"
            }
          >
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

          <div className="hc-account-actions">
            <span className="hc-research-label">
              {isPatient
                ? "Patient Account"
                : "Research prototype"}
            </span>

            <span
              className="hc-account-name"
              title={user.email}
            >
              {user.name}
            </span>

            <span className="hc-account-role">
              {isPatient ? "Patient" : "Caregiver"}
            </span>

            <button
              type="button"
              className="hc-logout-button"
              onClick={handleLogout}
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <div
        id="hc-content"
        ref={contentRef}
        tabIndex={-1}
        className="hc-content"
      >
        {isPatient ? (
          <PatientDashboard activeSection={activeTab} />
        ) : (
          <>
            {activeTab === "home" && (
              <HomePage onNavigate={setActiveTab} />
            )}

            {activeTab === "mental" && (
              <MentalWellness />
            )}

            {activeTab === "nutrition" && (
              <NutritionalIntelligence />
            )}

            {activeTab === "medicine" && (
              <TrayVerification />
            )}

            {activeTab === "monitoring" && (
              <PatientMonitoring />
            )}

            {activeTab === "notifications" && (
              <NotificationHistory />
            )}

            {activeTab === "physiological" && (
              <PhysiologicalRecommendations />
            )}
          </>
        )}
      </div>
    </div>
  );
};

const root = ReactDOM.createRoot(
  document.getElementById("root")
);

root.render(<App />);