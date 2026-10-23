
import React, { useEffect, useState } from "react";

const API_BASE = "http://localhost:5000/api/behavioral";
const CAMERA_STREAM_URL = "http://127.0.0.1:8000/video_feed";

const cameras = [
  {
    room: "Room 101",
    label: "North corridor",
    code: "CAM-01",
    connected: true,
  },
  {
    room: "Room 102",
    label: "Patient lounge",
    code: "CAM-02",
    connected: false,
  },
  {
    room: "Room 103",
    label: "Bedroom",
    code: "CAM-03",
    connected: false,
  },
  {
    room: "Room 104",
    label: "Therapy bay",
    code: "CAM-04",
    connected: false,
  },
];

function PatientMonitoring() {
  const [aiStatus, setAiStatus] = useState(null);
  const [connectionError, setConnectionError] = useState(false);
  const [streamError, setStreamError] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [uploadedVideo, setUploadedVideo] = useState(null);
  const [uploadedVideoUrl, setUploadedVideoUrl] = useState("");
  const [videoError, setVideoError] = useState("");
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState("");
  const [videoAnalysis, setVideoAnalysis] = useState(null);

  useEffect(() => {
    if (!uploadedVideo) {
      setUploadedVideoUrl("");
      return undefined;
    }

    const objectUrl = URL.createObjectURL(uploadedVideo);
    setUploadedVideoUrl(objectUrl);

    return () => URL.revokeObjectURL(objectUrl);
  }, [uploadedVideo]);

  const handleVideoChange = (event) => {
    const file = event.target.files?.[0];
    setVideoError("");
    setAnalysisError("");
    setVideoAnalysis(null);

    if (!file) return;

    if (!file.type.startsWith("video/")) {
      setUploadedVideo(null);
      setVideoError("Please choose a valid video file.");
      event.target.value = "";
      return;
    }

    setUploadedVideo(file);
  };

  const clearUploadedVideo = () => {
    setUploadedVideo(null);
    setUploadedVideoUrl("");
    setVideoError("");
    setAnalysisError("");
    setVideoAnalysis(null);
  };

  const analyzeUploadedVideo = async () => {
    if (!uploadedVideo) {
      setAnalysisError("Please choose a video before starting AI analysis.");
      return;
    }

    setAnalysisLoading(true);
    setAnalysisError("");
    setVideoAnalysis(null);

    try {
      const formData = new FormData();
      formData.append("file", uploadedVideo);

      const response = await fetch(
        "http://127.0.0.1:8000/api/behavioral/analyze-video",
        {
          method: "POST",
          body: formData,
        }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.detail || result.message || "The AI service could not analyze this video."
        );
      }

      setVideoAnalysis(result);
    } catch (error) {
      setAnalysisError(
        error.message ||
          "Could not connect to the AI service. Check that live_fall_detection.py is running."
      );
    } finally {
      setAnalysisLoading(false);
    }
  };

  useEffect(() => {
    let active = true;

    const fetchStatus = async () => {
      try {
        const response = await fetch(`${API_BASE}/status`);

        if (!response.ok) {
          throw new Error("AI status endpoint unavailable");
        }

        const data = await response.json();

        if (active) {
          setAiStatus(data);
          setConnectionError(false);
          setLastUpdated(new Date());
        }
      } catch {
        if (active) {
          setConnectionError(true);
        }
      }
    };

    fetchStatus();

    const interval = window.setInterval(fetchStatus, 2000);

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    if (aiStatus?.fallDetected) {
      setAcknowledged(false);
    }
  }, [aiStatus?.fallDetected, aiStatus?.updatedAt]);

  const fallDetected = Boolean(aiStatus?.fallDetected);
  const liveResident = aiStatus?.resident;
  const liveResidentName =
    typeof liveResident === "string"
      ? liveResident
      : liveResident?.name || aiStatus?.residentName || null;
  const liveResidentId =
    typeof liveResident === "object" && liveResident !== null
      ? liveResident.id || liveResident.residentId
      : aiStatus?.residentId;

  // Use uploaded-video identity only when live status has no identity.
  const residentName =
    liveResidentName ||
    videoAnalysis?.resident?.residentName ||
    "Unknown resident";
  const residentId =
    liveResidentId ||
    videoAnalysis?.resident?.residentId ||
    null;

  const liveLastEvent = aiStatus?.lastEvent;
  const uploadedFallEvent =
    videoAnalysis?.events?.length > 0
      ? videoAnalysis.events[0]
      : null;
  const lastEvent = liveLastEvent || uploadedFallEvent;
  const eventTime = liveLastEvent?.timestamp
    ? new Date(liveLastEvent.timestamp).toLocaleTimeString()
    : uploadedFallEvent &&
        typeof uploadedFallEvent.confirmedTimeSeconds === "number"
      ? `Video ${uploadedFallEvent.confirmedTimeSeconds.toFixed(2)} s`
      : lastUpdated
        ? lastUpdated.toLocaleTimeString()
        : "Waiting for data";

  const cameraConnected = Boolean(aiStatus?.connected);

  return (
    <main className="patient-monitoring">
      <style>{`
        .patient-monitoring {
          --ink: #192b2f;
          --muted: #718083;
          --line: #d7e1df;
          --teal: #167d72;
          --teal-dark: #0c514d;
          box-sizing: border-box;
          min-height: 100vh;
          padding: clamp(22px, 4vw, 58px);
          color: var(--ink);
          background: linear-gradient(135deg, #e9f2ef 0%, #f7f8f3 52%, #f8efe4 100%);
          font-family: Georgia, "Times New Roman", serif;
        }

        .patient-monitoring * { box-sizing: border-box; }
        .monitoring-shell { max-width: 1240px; margin: 0 auto; }

        .monitoring-header {
          display: flex;
          align-items: end;
          justify-content: space-between;
          gap: 24px;
          margin-bottom: 28px;
        }

        .monitoring-kicker {
          margin: 0 0 10px;
          color: var(--teal);
          font: 700 .72rem Arial, sans-serif;
          letter-spacing: .14em;
          text-transform: uppercase;
        }

        .monitoring-title {
          margin: 0;
          font-size: clamp(2.2rem, 5vw, 4.35rem);
          font-weight: 400;
          line-height: .98;
        }

        .monitoring-intro {
          max-width: 570px;
          margin: 15px 0 0;
          color: var(--muted);
          font: 1rem/1.55 Arial, sans-serif;
        }

        .monitoring-clock {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 13px;
          border: 1px solid var(--line);
          background: rgba(255,255,255,.75);
          color: var(--teal-dark);
          font: 700 .72rem Arial, sans-serif;
          white-space: nowrap;
        }

        .live-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #d59b36;
        }

        .live-dot.is-live { background: #168274; }
        .live-dot.is-error { background: #c74f42; }

        .alert-banner {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 20px;
          margin-bottom: 18px;
          padding: 17px 20px;
          border: 1px solid var(--line);
          background: rgba(255,255,255,.88);
        }

        .alert-banner.has-fall {
          border-color: #e7b2a9;
          background: #fff3ef;
        }

        .alert-copy { display: flex; align-items: center; gap: 13px; }

        .alert-symbol {
          display: grid;
          width: 36px;
          height: 36px;
          flex: 0 0 auto;
          place-items: center;
          border-radius: 50%;
          color: #fff;
          background: var(--teal);
          font: 700 1.1rem Arial, sans-serif;
        }

        .has-fall .alert-symbol { background: #b84e42; }

        .alert-banner h2 {
          margin: 0;
          font: 700 .84rem Arial, sans-serif;
          letter-spacing: .05em;
          text-transform: uppercase;
        }

        .alert-banner p {
          margin: 5px 0 0;
          color: var(--muted);
          font: .78rem/1.5 Arial, sans-serif;
        }

        .feed-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 14px;
        }

        .feed-card, .panel {
          border: 1px solid var(--line);
          background: rgba(255,255,255,.9);
          box-shadow: 0 12px 28px rgba(38,65,60,.07);
        }

        .feed-card { overflow: hidden; }

        .video-upload-panel { margin-top: 38px; }
        .video-upload-controls {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 12px;
          margin-top: 18px;
        }
        .video-file-input {
          position: absolute;
          width: 1px;
          height: 1px;
          padding: 0;
          margin: -1px;
          overflow: hidden;
          clip: rect(0, 0, 0, 0);
          white-space: nowrap;
          border: 0;
        }
        .video-upload-button, .video-clear-button {
          display: inline-flex;
          min-height: 43px;
          align-items: center;
          justify-content: center;
          padding: 0 16px;
          border: 1px solid var(--teal);
          font: 700 .78rem Arial, sans-serif;
          cursor: pointer;
        }
        .video-upload-button { color: #fff; background: var(--teal); }
        .video-clear-button { color: var(--teal-dark); background: #fff; }
        .video-analyze-button {
          display: inline-flex;
          min-height: 43px;
          align-items: center;
          justify-content: center;
          padding: 0 16px;
          border: 1px solid #b84e42;
          color: #fff;
          background: #b84e42;
          font: 700 .78rem Arial, sans-serif;
          cursor: pointer;
        }
        .video-analyze-button:disabled { opacity: .6; cursor: wait; }
        .video-analysis-result {
          margin-top: 18px;
          padding: 16px;
          border: 1px solid var(--line);
          background: #f6f9f7;
          font: .82rem/1.65 Arial, sans-serif;
        }
        .video-analysis-result.is-fall {
          border-color: #e7b2a9;
          background: #fff3ef;
        }
        .video-analysis-result h3 { margin: 0 0 8px; font: 700 .95rem Arial, sans-serif; }
        .video-analysis-result p { margin: 5px 0; }
        .video-file-name { color: var(--muted); font: .75rem/1.5 Arial, sans-serif; overflow-wrap: anywhere; }
        .uploaded-video-wrap {
          margin-top: 20px;
          overflow: hidden;
          border: 1px solid var(--line);
          background: #152523;
        }
        .uploaded-video-player { display: block; width: 100%; max-height: 520px; background: #152523; }
        .video-help-text { margin: 14px 0 0; color: var(--muted); font: .75rem/1.6 Arial, sans-serif; }
        .video-error { margin: 12px 0 0; color: #b34237; font: .78rem Arial, sans-serif; }

        .feed-visual {
          position: relative;
          height: clamp(190px, 24vw, 270px);
          overflow: hidden;
          background: #263c3b;
        }

        .feed-visual img {
          display: block;
          width: 100%;
          height: 100%;
          object-fit: contain;
          background: #152523;
        }

        .feed-placeholder {
          display: flex;
          width: 100%;
          height: 100%;
          align-items: center;
          justify-content: center;
          flex-direction: column;
          gap: 10px;
          padding: 20px;
          color: #dce8e2;
          text-align: center;
          font: .82rem/1.5 Arial, sans-serif;
          background: #263c3b;
        }

        .feed-placeholder strong {
          color: #fff;
          font-size: .95rem;
        }

        .feed-top, .feed-bottom {
          position: absolute;
          right: 14px;
          left: 14px;
          z-index: 1;
          display: flex;
          justify-content: space-between;
          gap: 8px;
          color: #f1f6ee;
          font: .66rem Arial, sans-serif;
        }

        .feed-top { top: 13px; }
        .feed-bottom { bottom: 13px; align-items: end; }

        .camera-code {
          padding: 5px 7px;
          background: rgba(17,31,32,.78);
          letter-spacing: .08em;
        }

        .feed-meta {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          padding: 13px 15px;
        }

        .feed-name { margin: 0; font: 700 .85rem Arial, sans-serif; }
        .feed-location { margin: 4px 0 0; color: var(--muted); font: .7rem Arial, sans-serif; }

        .status-badge {
          display: inline-block;
          padding: 6px 8px;
          color: #167366;
          background: #ddf0e9;
          font: 700 .64rem Arial, sans-serif;
          white-space: nowrap;
        }

        .status-badge.offline {
          color: #6d7475;
          background: #e9edec;
        }

        .status-badge.warning {
          color: #986526;
          background: #fff0d7;
        }

        .section-heading {
          display: flex;
          align-items: baseline;
          justify-content: space-between;
          gap: 16px;
          margin: 38px 0 15px;
        }

        .section-heading h2 { margin: 0; font-size: 1.6rem; font-weight: 400; }
        .section-heading p { margin: 0; color: var(--muted); font: .75rem Arial, sans-serif; }

        .dashboard-grid {
          display: grid;
          grid-template-columns: minmax(0, .85fr) minmax(0, 1.15fr);
          gap: 14px;
        }

        .panel { min-width: 0; padding: 21px; }
        .panel h3 { margin: 0; font-size: 1.15rem; font-weight: 400; }

        .panel-note {
          margin: 6px 0 22px;
          color: var(--muted);
          font: .74rem/1.5 Arial, sans-serif;
        }

        .resident-card {
          margin-top: 20px;
          padding: 14px;
          border: 1px solid var(--line);
          background: #f6f9f7;
        }

        .resident-label {
          margin: 0 0 8px;
          color: var(--muted);
          font: 700 .66rem Arial, sans-serif;
          letter-spacing: .07em;
          text-transform: uppercase;
        }

        .resident-name { margin: 0; font: 1.2rem Georgia, serif; }
        .resident-id { margin: 5px 0 0; color: var(--muted); font: .75rem Arial, sans-serif; }

        .event-state { color: #53736a; }
        .event-review { color: #a87328; }

        .event-table {
          width: 100%;
          border-collapse: collapse;
          font: .74rem Arial, sans-serif;
        }

        .event-table th {
          padding: 0 8px 11px 0;
          color: var(--muted);
          font-size: .64rem;
          text-align: left;
          letter-spacing: .07em;
          text-transform: uppercase;
        }

        .event-table td {
          padding: 13px 8px 13px 0;
          border-top: 1px solid var(--line);
          vertical-align: top;
        }

        .empty-row { color: var(--muted); }

        .alert-modal {
          position: fixed;
          inset: 0;
          z-index: 4;
          display: grid;
          place-items: center;
          padding: 20px;
          background: rgba(27,40,39,.48);
        }

        .alert-modal-card {
          width: min(100%, 420px);
          padding: 27px;
          border-top: 5px solid #c74f42;
          background: #fff;
          box-shadow: 0 25px 65px rgba(25,37,35,.28);
        }

        .modal-label {
          margin: 0 0 10px;
          color: #b34237;
          font: 700 .7rem Arial, sans-serif;
          letter-spacing: .1em;
          text-transform: uppercase;
        }

        .modal-title { margin: 0; font-size: 2rem; font-weight: 400; }

        .modal-details {
          margin: 20px 0 24px;
          padding: 14px;
          background: #fff3ef;
          color: #70443e;
          font: .8rem/1.8 Arial, sans-serif;
          overflow-wrap: anywhere;
        }

        .acknowledge-button {
          width: 100%;
          min-height: 46px;
          border: 0;
          color: #fff;
          background: #b84e42;
          font: 700 .8rem Arial, sans-serif;
          cursor: pointer;
        }

        .acknowledge-button:disabled {
          background: #6b9a8b;
          cursor: default;
        }

        @media (max-width: 760px) {
          .monitoring-header, .alert-banner { align-items: flex-start; flex-direction: column; }
          .monitoring-clock { align-self: stretch; }
          .feed-grid, .dashboard-grid { grid-template-columns: 1fr; }
          .section-heading { align-items: flex-start; flex-direction: column; }
        }
      `}</style>

      <div className="monitoring-shell">
        <header className="monitoring-header">
          <div>
            <p className="monitoring-kicker">
              Behavioral intelligence / ward 04
            </p>
            <h1 className="monitoring-title">Patient monitoring</h1>
            <p className="monitoring-intro">
              A continuous view of camera connectivity, resident identity,
              and AI-detected safety events.
            </p>
          </div>

          <div className="monitoring-clock">
            <span
              className={`live-dot ${
                connectionError
                  ? "is-error"
                  : cameraConnected
                    ? "is-live"
                    : ""
              }`}
            />
            {connectionError
              ? "AI SERVICE UNAVAILABLE"
              : cameraConnected
                ? "AI CONNECTED"
                : "CONNECTING TO AI"}
          </div>
        </header>

        <section
          className={`alert-banner ${fallDetected ? "has-fall" : ""}`}
          aria-live="polite"
        >
          <div className="alert-copy">
            <span className="alert-symbol">{fallDetected ? "!" : "✓"}</span>
            <div>
              <h2>
                {fallDetected
                  ? "Fall detected — attention required"
                  : "Fall detection & emergency monitoring"}
              </h2>
              <p>
                {connectionError
                  ? "Cannot retrieve AI status. Check that the backend is running."
                  : fallDetected
                    ? "The AI service has reported a possible fall. Verify the situation immediately."
                    : "Fall status is based on updates received from the AI backend."}
              </p>
            </div>
          </div>
          <span className={`status-badge ${connectionError ? "warning" : fallDetected ? "warning" : ""}`}>
            {connectionError
              ? "Connection error"
              : fallDetected
                ? "Review required"
                : "No active fall alert"}
          </span>
        </section>

        <section aria-labelledby="feeds-heading">
          <div className="section-heading">
            <h2 id="feeds-heading">Live camera grid</h2>
            <p>1 configured camera / 3 not connected</p>
          </div>

          <div className="feed-grid">
            {cameras.map((camera) => {
              const isCam01 = camera.code === "CAM-01";
              const camOnline = isCam01 && cameraConnected && !streamError;

              return (
                <article className="feed-card" key={camera.code}>
                  <div className="feed-visual">
                    {isCam01 && !streamError ? (
                      <img
                        src={CAMERA_STREAM_URL}
                        alt="CAM-01 live AI camera feed"
                        onError={() => setStreamError(true)}
                        onLoad={() => setStreamError(false)}
                      />
                    ) : (
                      <div className="feed-placeholder">
                        <strong>{camera.code}</strong>
                        <span>
                          {isCam01
                            ? "Live stream unavailable"
                            : "Camera not connected"}
                        </span>
                      </div>
                    )}

                    <div className="feed-top">
                      <span className="camera-code">{camera.code}</span>
                      <span>
                        {camOnline ? "LIVE" : "OFFLINE"}
                      </span>
                    </div>

                    <div className="feed-bottom">
                      <span>{camera.label}</span>
                      <span>{camOnline ? "AI feed" : "No signal"}</span>
                    </div>
                  </div>

                  <div className="feed-meta">
                    <div>
                      <p className="feed-name">{camera.room}</p>
                      <p className="feed-location">{camera.label}</p>
                    </div>
                    <span
                      className={`status-badge ${
                        camOnline ? "" : "offline"
                      }`}
                    >
                      {camOnline ? "Connected" : "Not connected"}
                    </span>
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        <section className="video-upload-panel" aria-labelledby="video-upload-heading">
          <div className="section-heading">
            <h2 id="video-upload-heading">Recorded video fall detection</h2>
            <p>Offline demonstration mode</p>
          </div>

          <article className="panel">
            <h3>Upload a recorded video</h3>
            <p className="panel-note">
              Select a previously recorded video, preview it, then run the existing AI pipeline against the video.
              Analysis runs on the Python AI service and does not require a live camera for this mode.
            </p>

            <input
              id="fall-video-upload"
              className="video-file-input"
              type="file"
              accept="video/*"
              onChange={handleVideoChange}
            />
            <div className="video-upload-controls">
              <label className="video-upload-button" htmlFor="fall-video-upload">
                Choose video
              </label>
              {uploadedVideo && (
                <>
                  <button
                    className="video-analyze-button"
                    type="button"
                    onClick={analyzeUploadedVideo}
                    disabled={analysisLoading}
                  >
                    {analysisLoading ? "Analyzing video..." : "Analyze for falls"}
                  </button>
                  <button
                    className="video-clear-button"
                    type="button"
                    onClick={clearUploadedVideo}
                    disabled={analysisLoading}
                  >
                    Remove video
                  </button>
                </>
              )}
              <span className="video-file-name">
                {uploadedVideo ? uploadedVideo.name : "No video selected"}
              </span>
            </div>

            {videoError && <p className="video-error" role="alert">{videoError}</p>}
            {analysisError && <p className="video-error" role="alert">{analysisError}</p>}

            {uploadedVideoUrl && (
              <div className="uploaded-video-wrap">
                <video
                  className="uploaded-video-player"
                  src={uploadedVideoUrl}
                  controls
                  playsInline
                  preload="metadata"
                >
                  Your browser does not support HTML video playback.
                </video>
              </div>
            )}

            {videoAnalysis && (
              <div
                className={`video-analysis-result ${
                  videoAnalysis.fallDetected ? "is-fall" : ""
                }`}
                role="status"
                aria-live="polite"
              >
                <h3>
                  {videoAnalysis.fallDetected
                    ? "Possible fall detected in uploaded video"
                    : "No confirmed fall detected"}
                </h3>
                <p>{videoAnalysis.message}</p>
                <p>
                  <strong>Frames processed:</strong>{" "}
                  {videoAnalysis.processedFrames ?? "N/A"}
                </p>
                <p>
                  <strong>Highest fall probability:</strong>{" "}
                  {typeof videoAnalysis.bestFallProbability === "number"
                    ? `${(videoAnalysis.bestFallProbability * 100).toFixed(1)}%`
                    : "N/A"}
                </p>
                <p>
                  <strong>Recognized resident:</strong>{" "}
                  {videoAnalysis.resident?.residentName || "Unknown resident"}
                </p>
                <p>
                  <strong>Resident ID:</strong>{" "}
                  {videoAnalysis.resident?.residentId || "Not identified"}
                </p>
                <p>
                  <strong>Confirmed fall events:</strong>{" "}
                  {Array.isArray(videoAnalysis.events)
                    ? videoAnalysis.events.length
                    : 0}
                </p>

                {Array.isArray(videoAnalysis.events) &&
                  videoAnalysis.events.length > 0 && (
                    <div className="uploaded-fall-events">
                      <h3>Fall event details</h3>
                      {videoAnalysis.events.map((event, index) => (
                        <div
                          className="resident-card"
                          key={`${event.trackId ?? "track"}-${index}`}
                        >
                          <p><strong>Event:</strong> Fall detected</p>
                          <p>
                            <strong>Resident:</strong>{" "}
                            {event.residentName || videoAnalysis.resident?.residentName || "Unknown resident"}
                          </p>
                          <p>
                            <strong>Resident ID:</strong>{" "}
                            {event.residentId || videoAnalysis.resident?.residentId || "Not identified"}
                          </p>
                          <p>
                            <strong>Fall-positive sequence started:</strong>{" "}
                            {typeof event.startTimeSeconds === "number"
                              ? `${event.startTimeSeconds.toFixed(2)} s`
                              : "Not provided"}
                          </p>
                          <p>
                            <strong>Fall confirmed:</strong>{" "}
                            {typeof event.confirmedTimeSeconds === "number"
                              ? `${event.confirmedTimeSeconds.toFixed(2)} s`
                              : "Not provided"}
                          </p>
                          <p>
                            <strong>Fall probability at confirmation:</strong>{" "}
                            {typeof event.probability === "number"
                              ? `${(event.probability * 100).toFixed(1)}%`
                              : "N/A"}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
              </div>
            )}

            <p className="video-help-text">
              Supported formats depend on your browser and the Python video decoder. AI analysis processes the uploaded
              file separately from the live camera feed. This is a research demo, not a substitute for emergency monitoring.
            </p>
          </article>
        </section>

        <section aria-labelledby="identity-heading">
          <div className="section-heading">
            <h2 id="identity-heading">AI resident recognition</h2>
            <p>Identity supplied by the behavioral AI service</p>
          </div>

          <div className="dashboard-grid">
            <article className="panel">
              <h3>Recognized resident</h3>
              <p className="panel-note">
                Resident information is shown only when received from the AI backend.
              </p>

              <div className="resident-card">
                <p className="resident-label">Current identity</p>
                <p className="resident-name">
                  {residentName}
                </p>
                <p className="resident-id">
                  Resident ID: {residentId || "Not identified"}
                </p>
              </div>

              <div className="resident-card">
                <p className="resident-label">AI service status</p>
                <p className="resident-name">
                  {connectionError
                    ? "Disconnected"
                    : cameraConnected
                      ? "Connected"
                      : "Waiting for connection"}
                </p>
                <p className="resident-id">
                  Last status update: {eventTime}
                </p>
              </div>
            </article>

            <article className="panel">
              <h3>Latest AI event</h3>
              <p className="panel-note">
                Most recent event received from the backend.
              </p>

              <table className="event-table">
                <thead>
                  <tr>
                    <th>Field</th>
                    <th>Value</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Event</td>
                    <td>{lastEvent?.type || (fallDetected ? "Fall detected" : "No event received")}</td>
                  </tr>
                  <tr>
                    <td>Resident</td>
                    <td>{lastEvent?.residentName || residentName}</td>
                  </tr>
                  <tr>
                    <td>Camera</td>
                    <td>{lastEvent?.camera || aiStatus?.camera || "CAM-01"}</td>
                  </tr>
                  <tr>
                    <td>Updated</td>
                    <td>{eventTime}</td>
                  </tr>
                  <tr>
                    <td>Status</td>
                    <td className={fallDetected ? "event-review" : "event-state"}>
                      {fallDetected ? "Review required" : "No active fall alert"}
                    </td>
                  </tr>
                </tbody>
              </table>
            </article>
          </div>
        </section>
      </div>

      {fallDetected && !acknowledged && (
        <div
          className="alert-modal"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="fall-title"
        >
          <div className="alert-modal-card">
            <p className="modal-label">AI safety alert</p>
            <h2 className="modal-title" id="fall-title">
              Fall detected
            </h2>

            <div className="modal-details">
              <div>
                <strong>Resident:</strong> {residentName}
              </div>
              <div>
                <strong>Resident ID:</strong> {residentId || "Unknown"}
              </div>
              <div>
                <strong>Camera:</strong> {aiStatus?.camera || "CAM-01"}
              </div>
              <div>
                <strong>Event time:</strong> {eventTime}
              </div>
              <div>
                <strong>Signal:</strong>{" "}
                {lastEvent?.type || "Fall detection event from AI service"}
              </div>
            </div>

            <button
              className="acknowledge-button"
              type="button"
              onClick={() => setAcknowledged(true)}
            >
              Acknowledge alert
            </button>
          </div>
        </div>
      )}
    </main>
  );
}

export default PatientMonitoring;
