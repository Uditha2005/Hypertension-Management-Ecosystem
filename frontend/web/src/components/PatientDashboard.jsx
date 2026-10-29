import React, { useEffect, useState } from "react";
import "./PatientDashboard.css";

const API_URL = "http://localhost:5000/api";
const TOKEN_KEY = "hypercare-auth-token";

export default function PatientDashboard() {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadFallHistory() {
      try {
        const token = window.sessionStorage.getItem(TOKEN_KEY);

        if (!token) {
          throw new Error("Please sign in again.");
        }

        const response = await fetch(
          `${API_URL}/patient/fall-history`,
          {
            method: "GET",
            headers: {
              Authorization: `Bearer ${token}`,
              Accept: "application/json",
            },
          }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.error || "Unable to load fall history."
          );
        }

        if (!cancelled) {
          // Backend returns { events: [...], count: number }.
          setIncidents(
            Array.isArray(data.events) ? data.events : []
          );
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Something went wrong.");
          setIncidents([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadFallHistory();

    return () => {
      cancelled = true;
    };
  }, []);

  function formatDate(value) {
    if (!value) return "Date and time unavailable";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return "Date and time unavailable";
    }

    return date.toLocaleString();
  }

  function formatProbability(value) {
    if (value === null || value === undefined || value === "") {
      return null;
    }

    const number = Number(value);

    if (!Number.isFinite(number)) {
      return null;
    }

    return `${(number * 100).toFixed(1)}%`;
  }

  function formatSource(source) {
    if (source === "live_camera") return "Live camera";
    if (source === "uploaded_video") return "Uploaded video";
    return source || null;
  }

  return (
    <main className="patient-dashboard">
      <section className="patient-welcome">
        <p className="patient-eyebrow">
          HYPERCARE PATIENT PORTAL
        </p>

        <h1>My Fall History</h1>

        <p>
          View fall incidents recorded for your patient account.
        </p>
      </section>

      <section
        className="patient-history-card"
        aria-labelledby="fall-history-title"
      >
        <div className="patient-card-heading">
          <div>
            <h2 id="fall-history-title">Fall incidents</h2>
            <p>Your recorded incident history</p>
          </div>

          <span className="patient-count">
            {incidents.length}
          </span>
        </div>

        {loading ? (
          <p className="patient-message" role="status">
            Loading your fall history...
          </p>
        ) : error ? (
          <div className="patient-error" role="alert">
            {error}
          </div>
        ) : incidents.length === 0 ? (
          <div className="patient-empty">
            <div
              className="patient-empty-icon"
              aria-hidden="true"
            >
              ✓
            </div>

            <h3>No fall incidents to display</h3>

            <p>
              There are currently no recorded incidents associated
              with your account.
            </p>
          </div>
        ) : (
          <div className="patient-incident-list">
            {incidents.map((incident) => {
              const probability = formatProbability(
                incident.probability
              );

              const source = formatSource(incident.source);

              return (
                <article
                  className="patient-incident"
                  key={incident.id}
                >
                  <div
                    className="patient-incident-marker"
                    aria-hidden="true"
                  />

                  <div className="patient-incident-details">
                    <h3>
                      {incident.residentName || "Fall incident"}
                    </h3>

                    <p>{formatDate(incident.occurredAt)}</p>

                    {source && (
                      <p>
                        <strong>Source:</strong> {source}
                      </p>
                    )}

                    {probability && (
                      <p>
                        <strong>Detection confidence:</strong>{" "}
                        {probability}
                      </p>
                    )}

                    {incident.trackId != null && (
                      <p>
                        <strong>Track ID:</strong>{" "}
                        {incident.trackId}
                      </p>
                    )}

                    {incident.videoTimeSeconds != null && (
                      <p>
                        <strong>Video time:</strong>{" "}
                        {Number(
                          incident.videoTimeSeconds
                        ).toFixed(1)}{" "}
                        seconds
                      </p>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <p className="patient-privacy-note">
        This page is intended to show incidents linked to your
        account only.
      </p>
    </main>
  );
}