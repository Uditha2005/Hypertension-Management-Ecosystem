import React, { useEffect, useState } from "react";
import { jsPDF } from "jspdf";

const initialMetrics = {
  heartRate: 72,
  bodyTemperature: 36.7,
  stressLevel: "Low",
  emotion: "Focused",
};

const metricConfig = [
  {
    key: "heartRate",
    label: "Heart Rate",
    unit: "BPM",
    accent: "coral",
    icon: "HR",
    format: (value) => value,
  },
  {
    key: "bodyTemperature",
    label: "Body Temperature",
    unit: "°C",
    accent: "amber",
    icon: "BT",
    format: (value) => value.toFixed(1),
  },
  {
    key: "stressLevel",
    label: "Stress Level",
    unit: "Current state",
    accent: "teal",
    icon: "SL",
    format: (value) => value,
  },
  {
    key: "emotion",
    label: "Detected Emotion",
    unit: "Live inference",
    accent: "blue",
    icon: "EM",
    format: (value) => value,
  },
];

const statusClass = (value) => value.toLowerCase().replace(" ", "-");

const adaptiveDifficulty = {
  Low: { level: "Steady", adjustment: "+10% challenge", detail: "Building focus" },
  Medium: { level: "Balanced", adjustment: "Maintaining pace", detail: "Regulating intensity" },
  High: { level: "Gentle", adjustment: "-20% challenge", detail: "Creating breathing room" },
};

const wellnessTrend = [
  { time: "08:00", stress: 34, emotion: "Calm" },
  { time: "09:00", stress: 42, emotion: "Focused" },
  { time: "10:00", stress: 57, emotion: "Alert" },
  { time: "11:00", stress: 74, emotion: "Stressed" },
  { time: "12:00", stress: 63, emotion: "Alert" },
  { time: "13:00", stress: 48, emotion: "Focused" },
  { time: "14:00", stress: 39, emotion: "Calm" },
  { time: "15:00", stress: 46, emotion: "Focused" },
];

function MentalWellness() {
  const [metrics, setMetrics] = useState(initialMetrics);
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const [history, setHistory] = useState([{ recordedAt: new Date().toISOString(), ...initialMetrics }]);
  const [cameraActive, setCameraActive] = useState(false);
  const [emotionOverlayVisible, setEmotionOverlayVisible] = useState(true);
  const [headMovementEnabled, setHeadMovementEnabled] = useState(false);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setMetrics((current) => {
        const nextMetrics = {
          ...current,
          heartRate: Math.max(64, Math.min(84, current.heartRate + (Math.random() > 0.5 ? 1 : -1))),
          bodyTemperature: Number((current.bodyTemperature + (Math.random() > 0.5 ? 0.1 : -0.1)).toFixed(1)),
          stressLevel: ["Low", "Medium", "High"][Math.floor(Date.now() / 5000) % 3],
        };

        setHistory((currentHistory) => [
          ...currentHistory,
          { recordedAt: new Date().toISOString(), ...nextMetrics },
        ]);
        return nextMetrics;
      });
      setLastUpdated(new Date());
    }, 5000);

    return () => window.clearInterval(interval);
  }, []);

  const downloadHistory = () => {
    const firstReading = history[0];
    const latestReading = history[history.length - 1];
    const report = {
      reportTitle: "Mental and Physiological Wellness History",
      exportedAt: new Date().toISOString(),
      source: "AI-Powered Multimodal Mental and Physiological Wellness Intelligence System",
      sessionSummary: {
        readings: history.length,
        startedAt: firstReading.recordedAt,
        lastRecordedAt: latestReading.recordedAt,
        currentStatus: metrics,
      },
      mentalWellness: history.map(({ recordedAt, stressLevel, emotion }) => ({
        recordedAt,
        stressLevel,
        detectedEmotion: emotion,
      })),
      physiologicalWellness: history.map(({ recordedAt, heartRate, bodyTemperature }) => ({
        recordedAt,
        heartRateBpm: heartRate,
        bodyTemperatureCelsius: bodyTemperature,
      })),
      changes: {
        heartRateBpm: latestReading.heartRate - firstReading.heartRate,
        bodyTemperatureCelsius: Number((latestReading.bodyTemperature - firstReading.bodyTemperature).toFixed(1)),
        stress: { from: firstReading.stressLevel, to: latestReading.stressLevel },
        emotion: { from: firstReading.emotion, to: latestReading.emotion },
        trend: wellnessTrend,
      },
      facialEmotionRecognition: {
        cameraStatus: cameraActive ? "active" : "standby",
        overlayVisible: emotionOverlayVisible,
        latestInference: "Stress Detected: 82%",
      },
      therapeuticSession: {
        adaptiveDifficulty: adaptiveDifficulty[metrics.stressLevel],
        headMovementTracking: headMovementEnabled,
      },
    };
    const pdf = new jsPDF();
    const pageHeight = pdf.internal.pageSize.getHeight();
    const pageWidth = pdf.internal.pageSize.getWidth();
    let cursorY = 18;

    const addText = (text, options = {}) => {
      const { size = 10, color = [48, 65, 63], bold = false, gap = 5 } = options;
      pdf.setFont("helvetica", bold ? "bold" : "normal");
      pdf.setFontSize(size);
      pdf.setTextColor(...color);
      const lines = pdf.splitTextToSize(String(text), pageWidth - 28);
      if (cursorY + lines.length * 5 + gap > pageHeight - 14) {
        pdf.addPage();
        cursorY = 18;
      }
      pdf.text(lines, 14, cursorY);
      cursorY += lines.length * 5 + gap;
    };

    const addSection = (title) => {
      cursorY += 3;
      addText(title, { size: 13, color: [22, 125, 114], bold: true, gap: 6 });
    };

    addText(report.reportTitle, { size: 19, color: [21, 42, 48], bold: true, gap: 7 });
    addText(`Exported: ${new Date(report.exportedAt).toLocaleString()}`, { size: 9, color: [107, 126, 128], gap: 3 });
    addText(`Readings captured: ${report.sessionSummary.readings}`, { size: 9, color: [107, 126, 128], gap: 8 });

    addSection("Current Summary");
    addText(`Heart rate: ${report.sessionSummary.currentStatus.heartRate} BPM | Body temperature: ${report.sessionSummary.currentStatus.bodyTemperature} C`);
    addText(`Stress level: ${report.sessionSummary.currentStatus.stressLevel} | Detected emotion: ${report.sessionSummary.currentStatus.emotion}`);

    addSection("Mental Wellness History");
    report.mentalWellness.forEach((reading) => {
      addText(`${new Date(reading.recordedAt).toLocaleString()} - Stress: ${reading.stressLevel}; Emotion: ${reading.detectedEmotion}`, { size: 9, gap: 3 });
    });

    addSection("Physiological Wellness History");
    report.physiologicalWellness.forEach((reading) => {
      addText(`${new Date(reading.recordedAt).toLocaleString()} - Heart rate: ${reading.heartRateBpm} BPM; Temperature: ${reading.bodyTemperatureCelsius} C`, { size: 9, gap: 3 });
    });

    addSection("Changes and Trends");
    addText(`Heart rate change: ${report.changes.heartRateBpm} BPM | Temperature change: ${report.changes.bodyTemperatureCelsius} C`);
    addText(`Stress changed from ${report.changes.stress.from} to ${report.changes.stress.to} | Emotion changed from ${report.changes.emotion.from} to ${report.changes.emotion.to}`);
    report.changes.trend.forEach((point) => {
      addText(`${point.time} - Stress: ${point.stress}% | Emotion: ${point.emotion}`, { size: 9, gap: 3 });
    });

    addSection("Recognition and Therapeutic Session");
    addText(`Camera: ${report.facialEmotionRecognition.cameraStatus} | Emotion overlay: ${report.facialEmotionRecognition.overlayVisible ? "visible" : "hidden"}`);
    addText(`Latest inference: ${report.facialEmotionRecognition.latestInference}`);
    addText(`Adaptive mode: ${report.therapeuticSession.adaptiveDifficulty.level} (${report.therapeuticSession.adaptiveDifficulty.adjustment})`);
    addText(`Head movement tracking: ${report.therapeuticSession.headMovementTracking ? "enabled" : "disabled"}`);

    pdf.save(`wellness-history-${new Date().toISOString().slice(0, 10)}.pdf`);
  };

  return (
    <main className="mental-wellness-dashboard">
      <style>{`
        .mental-wellness-dashboard {
          --ink: #152a30;
          --muted: #6b7e80;
          --surface: #ffffff;
          --line: #dce8e5;
          --canvas: #f3f8f5;
          min-height: 100vh;
          box-sizing: border-box;
          padding: clamp(24px, 5vw, 64px);
          color: var(--ink);
          background: radial-gradient(circle at 92% 8%, #d4ebe0 0, transparent 28%), var(--canvas);
          font-family: Georgia, "Times New Roman", serif;
        }
        .wellness-header {
          display: flex;
          align-items: end;
          justify-content: space-between;
          gap: 24px;
          max-width: 1180px;
          margin: 0 auto 34px;
        }
        .wellness-kicker {
          margin: 0 0 10px;
          color: #17877d;
          font: 700 0.75rem/1.2 Arial, sans-serif;
          letter-spacing: 0.12em;
          text-transform: uppercase;
        }
        .wellness-title {
          margin: 0;
          font-size: clamp(2.25rem, 5vw, 4.5rem);
          font-weight: 400;
          line-height: 0.98;
        }
        .wellness-subtitle {
          max-width: 470px;
          margin: 16px 0 0;
          color: var(--muted);
          font: 400 1rem/1.6 Arial, sans-serif;
        }
        .wellness-actions {
          display: flex;
          align-items: center;
          gap: 12px;
          flex-wrap: wrap;
          justify-content: flex-end;
        }
        .download-history-button {
          min-height: 42px;
          padding: 0 15px;
          border: 1px solid #166b63;
          border-radius: 4px;
          color: #fff;
          background: #167d72;
          cursor: pointer;
          font: 700 0.74rem Arial, sans-serif;
        }
        .download-history-button:hover { background: #0f5e57; }
        .download-history-button:focus-visible { outline: 3px solid #f0bd68; outline-offset: 2px; }
        .live-indicator {
          display: inline-flex;
          align-items: center;
          gap: 9px;
          padding: 10px 14px;
          border: 1px solid var(--line);
          border-radius: 999px;
          color: #39756d;
          background: rgba(255, 255, 255, 0.7);
          font: 700 0.74rem Arial, sans-serif;
          white-space: nowrap;
        }
        .live-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #ed785c;
          box-shadow: 0 0 0 5px #fbe4dc;
        }
        .metric-grid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 14px;
          max-width: 1180px;
          margin: 0 auto;
        }
        .metric-card {
          position: relative;
          overflow: hidden;
          min-height: 216px;
          padding: 24px;
          border: 1px solid var(--line);
          border-radius: 8px;
          background: var(--surface);
          box-shadow: 0 12px 28px rgba(42, 72, 67, 0.06);
          animation: rise-in 500ms both;
        }
        .metric-card:nth-child(2) { animation-delay: 80ms; }
        .metric-card:nth-child(3) { animation-delay: 160ms; }
        .metric-card:nth-child(4) { animation-delay: 240ms; }
        .metric-card::after {
          position: absolute;
          right: -32px;
          bottom: -40px;
          width: 120px;
          height: 120px;
          border-radius: 50%;
          background: var(--card-tint);
          content: "";
          opacity: 0.45;
        }
        .accent-coral { --card-tint: #f9d9cf; --accent: #dd6d55; }
        .accent-amber { --card-tint: #f8e6b6; --accent: #c48a29; }
        .accent-teal { --card-tint: #cbe9df; --accent: #228d7d; }
        .accent-blue { --card-tint: #d6e5f0; --accent: #4c7fa4; }
        .metric-topline {
          display: flex;
          align-items: center;
          justify-content: space-between;
          position: relative;
          z-index: 1;
        }
        .metric-icon {
          display: grid;
          width: 38px;
          height: 38px;
          place-items: center;
          border-radius: 50%;
          color: var(--accent);
          background: var(--card-tint);
          font: 700 0.66rem Arial, sans-serif;
          letter-spacing: 0.04em;
        }
        .metric-label {
          margin: 0;
          color: var(--muted);
          font: 700 0.75rem Arial, sans-serif;
          letter-spacing: 0.04em;
          text-transform: uppercase;
        }
        .metric-value {
          position: relative;
          z-index: 1;
          margin: 38px 0 8px;
          color: var(--ink);
          font-size: clamp(2rem, 3vw, 3rem);
          font-weight: 400;
          line-height: 1;
        }
        .metric-unit {
          position: relative;
          z-index: 1;
          margin: 0;
          color: var(--accent);
          font: 700 0.75rem Arial, sans-serif;
        }
        .status-pill {
          display: inline-block;
          padding: 5px 9px;
          border-radius: 999px;
          font: 700 0.68rem Arial, sans-serif;
        }
        .low { color: #227c6e; background: #dff1eb; }
        .medium { color: #9a6a1c; background: #fff0c9; }
        .high { color: #b04c3e; background: #fbe1da; }
        .focused { color: #3e7192; background: #e0edf6; }
        .stressed { color: #b04c3e; background: #fbe1da; }
        .wellness-footer {
          max-width: 1180px;
          margin: 20px auto 0;
          color: var(--muted);
          font: 0.75rem Arial, sans-serif;
        }
        .recognition-card {
          display: grid;
          grid-template-columns: minmax(0, 1.5fr) minmax(240px, 0.8fr);
          gap: 24px;
          max-width: 1180px;
          margin: 34px auto 0;
          padding: 24px;
          border: 1px solid #cbded9;
          border-radius: 8px;
          background: #1b3637;
          color: #f3faf5;
          box-shadow: 0 16px 32px rgba(28, 67, 61, 0.12);
        }
        .camera-heading {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          margin-bottom: 18px;
        }
        .camera-heading h2 {
          margin: 0;
          font-size: 1.45rem;
          font-weight: 400;
        }
        .camera-heading p {
          margin: 5px 0 0;
          color: #abc5be;
          font: 0.8rem Arial, sans-serif;
        }
        .camera-status {
          color: #b9e8c9;
          font: 700 0.7rem Arial, sans-serif;
          letter-spacing: 0.06em;
          white-space: nowrap;
        }
        .video-placeholder {
          position: relative;
          display: grid;
          min-height: 270px;
          overflow: hidden;
          place-items: center;
          border: 1px solid #456b68;
          border-radius: 6px;
          background: linear-gradient(145deg, #294d4d, #132a30 68%);
        }
        .video-placeholder::before,
        .video-placeholder::after {
          position: absolute;
          width: 110px;
          height: 110px;
          border: 1px solid rgba(176, 232, 210, 0.18);
          content: "";
          transform: rotate(45deg);
        }
        .video-placeholder::before { top: -58px; left: 13%; }
        .video-placeholder::after { right: 10%; bottom: -58px; }
        .camera-placeholder-copy {
          position: relative;
          z-index: 1;
          color: #a8c6bf;
          font: 700 0.75rem Arial, sans-serif;
          letter-spacing: 0.1em;
          text-align: center;
          text-transform: uppercase;
        }
        .camera-placeholder-copy strong {
          display: block;
          margin-bottom: 8px;
          color: #effaf2;
          font: 400 1.65rem Georgia, "Times New Roman", serif;
          letter-spacing: 0;
          text-transform: none;
        }
        .emotion-overlay {
          position: absolute;
          z-index: 2;
          top: 18px;
          left: 18px;
          padding: 12px 14px;
          border-left: 3px solid #ee8b6c;
          background: rgba(10, 29, 32, 0.84);
          font: 700 0.78rem Arial, sans-serif;
        }
        .emotion-overlay strong {
          display: block;
          margin-top: 4px;
          color: #ffb49d;
          font-size: 1rem;
        }
        .recognition-controls {
          display: flex;
          flex-direction: column;
          justify-content: center;
          gap: 12px;
        }
        .recognition-controls h3 {
          margin: 0 0 4px;
          color: #f3faf5;
          font-size: 1.1rem;
          font-weight: 400;
        }
        .recognition-controls p {
          margin: 0 0 12px;
          color: #abc5be;
          font: 0.82rem/1.5 Arial, sans-serif;
        }
        .camera-button {
          padding: 12px 15px;
          border: 1px solid #8bd3b1;
          border-radius: 4px;
          color: #173c38;
          background: #a9e0bd;
          cursor: pointer;
          font: 700 0.75rem Arial, sans-serif;
          text-align: left;
        }
        .camera-button:hover { background: #c2efd0; }
        .camera-button.secondary {
          color: #d2e7df;
          background: transparent;
          border-color: #587d78;
        }
        .camera-button.secondary:hover { background: #284b4b; }
        .game-card {
          display: grid;
          grid-template-columns: minmax(0, 1.45fr) minmax(250px, 0.75fr);
          gap: 24px;
          max-width: 1180px;
          margin: 20px auto 0;
          padding: 24px;
          border: 1px solid #e2d7c7;
          border-radius: 8px;
          background: #fffaf1;
          box-shadow: 0 12px 28px rgba(99, 76, 48, 0.07);
        }
        .game-heading h2 { margin: 0; color: #352e29; font-size: 1.45rem; font-weight: 400; }
        .game-heading p { margin: 5px 0 18px; color: #8a786a; font: 0.8rem Arial, sans-serif; }
        .game-canvas {
          position: relative;
          display: grid;
          min-height: 245px;
          overflow: hidden;
          place-items: center;
          border: 1px solid #d7c2a5;
          border-radius: 6px;
          background: linear-gradient(135deg, #f4d9aa 0%, #d9bda2 48%, #a8c7b5 100%);
        }
        .game-canvas::before {
          position: absolute;
          width: 170px;
          height: 170px;
          border: 1px solid rgba(75, 91, 69, 0.25);
          border-radius: 50%;
          content: "";
        }
        .game-canvas-copy { position: relative; color: #4b5144; font: 700 0.75rem Arial, sans-serif; letter-spacing: 0.08em; text-align: center; text-transform: uppercase; }
        .game-canvas-copy strong { display: block; margin-bottom: 8px; color: #2f453d; font: 400 1.65rem Georgia, "Times New Roman", serif; letter-spacing: 0; text-transform: none; }
        .game-hud {
          position: absolute;
          top: 16px;
          right: 16px;
          padding: 12px 14px;
          border: 1px solid rgba(255, 255, 255, 0.55);
          border-radius: 4px;
          color: #fefcf4;
          background: rgba(42, 57, 48, 0.85);
          font: 0.74rem/1.45 Arial, sans-serif;
        }
        .game-hud strong { display: block; color: #f4d9aa; font-size: 0.95rem; }
        .game-controls { display: flex; flex-direction: column; justify-content: center; gap: 14px; }
        .game-controls h3 { margin: 0; color: #352e29; font-size: 1.1rem; font-weight: 400; }
        .game-controls p { margin: 0; color: #8a786a; font: 0.82rem/1.5 Arial, sans-serif; }
        .difficulty-readout { padding: 14px; border-left: 3px solid #d18d51; background: #f5ead7; color: #604b38; font: 0.78rem/1.5 Arial, sans-serif; }
        .difficulty-readout strong { display: block; color: #352e29; font-size: 1.05rem; }
        .accessibility-toggle { display: flex; align-items: center; justify-content: space-between; gap: 14px; color: #4d453e; font: 700 0.78rem Arial, sans-serif; }
        .toggle-button { width: 42px; height: 24px; padding: 3px; border: 0; border-radius: 999px; background: #c8b8a4; cursor: pointer; text-align: left; }
        .toggle-button span { display: block; width: 18px; height: 18px; border-radius: 50%; background: #fffaf1; transition: transform 180ms ease; }
        .toggle-button.active { background: #4b9180; }
        .toggle-button.active span { transform: translateX(18px); }
        .trend-card { max-width: 1180px; margin: 20px auto 0; padding: 24px; border: 1px solid #dce8e5; border-radius: 8px; background: #ffffff; box-shadow: 0 12px 28px rgba(42, 72, 67, 0.06); }
        .trend-heading { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 24px; }
        .trend-heading h2 { margin: 0; font-size: 1.45rem; font-weight: 400; }
        .trend-heading p { margin: 6px 0 0; color: #6b7e80; font: 0.8rem Arial, sans-serif; }
        .trend-legend { display: flex; gap: 14px; color: #6b7e80; font: 700 0.7rem Arial, sans-serif; white-space: nowrap; }
        .legend-item { display: inline-flex; align-items: center; gap: 6px; }
        .legend-swatch { width: 9px; height: 9px; border-radius: 50%; background: #df775c; }
        .legend-swatch.emotion { background: #4b9180; }
        .trend-chart { display: grid; grid-template-columns: 56px minmax(0, 1fr); gap: 12px; }
        .trend-axis { display: flex; flex-direction: column; justify-content: space-between; padding: 0 0 22px; color: #9aaba8; font: 0.68rem Arial, sans-serif; text-align: right; }
        .trend-plot { display: grid; grid-template-columns: repeat(8, minmax(28px, 1fr)); align-items: end; gap: 10px; min-height: 180px; padding: 10px 0 0; border-bottom: 1px solid #dce8e5; background: repeating-linear-gradient(to bottom, transparent 0, transparent 59px, #edf3f0 60px); }
        .trend-column { display: flex; height: 170px; flex-direction: column; align-items: center; justify-content: end; gap: 8px; }
        .stress-bar { width: min(24px, 100%); min-height: 4px; border-radius: 4px 4px 0 0; background: linear-gradient(to top, #df775c, #f3b268); }
        .emotion-marker { width: 10px; height: 10px; border: 2px solid #ffffff; border-radius: 50%; background: #4b9180; box-shadow: 0 0 0 1px #4b9180; }
        .trend-time { color: #7d8e8a; font: 0.68rem Arial, sans-serif; }
        .trend-summary { margin: 18px 0 0 68px; color: #6b7e80; font: 0.75rem/1.5 Arial, sans-serif; }
        @media (max-width: 800px) {
          .wellness-header { align-items: start; flex-direction: column; }
          .wellness-actions { justify-content: flex-start; }
          .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
          .recognition-card { grid-template-columns: 1fr; }
          .game-card { grid-template-columns: 1fr; }
        }
        @keyframes rise-in { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        @media (max-width: 480px) {
          .mental-wellness-dashboard { padding: 28px 16px; }
          .metric-grid { grid-template-columns: 1fr; }
          .metric-card { min-height: 180px; }
          .trend-heading { align-items: start; flex-direction: column; }
          .trend-legend { white-space: normal; }
          .trend-plot { gap: 5px; }
          .trend-summary { margin-left: 0; }
        }
      `}</style>

      <header className="wellness-header">
        <div>
          <p className="wellness-kicker">Mind + body monitor</p>
          <h1 className="wellness-title">Mental wellness</h1>
          <p className="wellness-subtitle">
            A quiet read on the signals shaping your day, updated as your body and mind shift.
          </p>
        </div>
        <div className="wellness-actions">
          <button className="download-history-button" type="button" onClick={downloadHistory}>
            Download total history
          </button>
          <div className="live-indicator" aria-label="Live metrics active">
            <span className="live-dot" aria-hidden="true" /> LIVE MONITORING
          </div>
        </div>
      </header>

      <section className="metric-grid" aria-label="Current wellness metrics">
        {metricConfig.map((metric) => {
          const value = metrics[metric.key];
          const isStatus = metric.key === "stressLevel" || metric.key === "emotion";

          return (
            <article className={`metric-card accent-${metric.accent}`} key={metric.key}>
              <div className="metric-topline">
                <p className="metric-label">{metric.label}</p>
                <span className="metric-icon" aria-hidden="true">{metric.icon}</span>
              </div>
              <p className={`metric-value${isStatus ? " status-pill" : ""}${isStatus ? ` ${statusClass(value)}` : ""}`}>
                {metric.format(value)}
              </p>
              <p className="metric-unit">{metric.unit}</p>
            </article>
          );
        })}
      </section>

      <section className="recognition-card" aria-labelledby="recognition-title">
        <div>
          <div className="camera-heading">
            <div>
              <h2 id="recognition-title">Facial emotion recognition</h2>
              <p>Private, on-device signal preview</p>
            </div>
            <span className="camera-status">{cameraActive ? "STREAM ACTIVE" : "STANDBY"}</span>
          </div>
          <div className="video-placeholder" aria-label="Mock webcam video feed">
            {emotionOverlayVisible && (
              <div className="emotion-overlay" aria-live="polite">
                CURRENT ANALYSIS
                <strong>Stress Detected: 82%</strong>
              </div>
            )}
            <div className="camera-placeholder-copy">
              <strong>{cameraActive ? "Camera stream ready" : "Webcam feed placeholder"}</strong>
              {cameraActive ? "Simulated facial landmarks active" : "Start a stream to begin analysis"}
            </div>
          </div>
        </div>
        <div className="recognition-controls">
          <div>
            <h3>Emotion signal</h3>
            <p>Use the simulated feed to preview how live facial cues could complement your wellness metrics.</p>
          </div>
          <button className="camera-button" type="button" onClick={() => setCameraActive((active) => !active)}>
            {cameraActive ? "Stop Camera Stream" : "Start Camera Stream"}
          </button>
          <button
            className="camera-button secondary"
            type="button"
            aria-pressed={emotionOverlayVisible}
            onClick={() => setEmotionOverlayVisible((visible) => !visible)}
          >
            {emotionOverlayVisible ? "Hide Emotion Overlay" : "Toggle Emotion Overlay"}
          </button>
        </div>
      </section>

      <section className="game-card" aria-labelledby="game-title">
        <div>
          <div className="game-heading">
            <h2 id="game-title">Adaptive Therapeutic Game</h2>
            <p>A calming prototype that responds to your current stress signal</p>
          </div>
          <div className="game-canvas" role="img" aria-label="Therapeutic game canvas placeholder">
            <div className="game-canvas-copy">
              <strong>Game area placeholder</strong>
              Guided focus exercise
            </div>
            <div className="game-hud" aria-live="polite">
              STRESS-RESPONSIVE HUD
              <strong>{adaptiveDifficulty[metrics.stressLevel].level} mode</strong>
              {adaptiveDifficulty[metrics.stressLevel].adjustment}
            </div>
          </div>
        </div>
        <div className="game-controls">
          <div>
            <h3>Adaptive difficulty</h3>
            <p>The simulated {metrics.stressLevel.toLowerCase()} stress signal is guiding the session pace.</p>
          </div>
          <div className="difficulty-readout">
            <strong>{adaptiveDifficulty[metrics.stressLevel].detail}</strong>
            {adaptiveDifficulty[metrics.stressLevel].adjustment}
          </div>
          <div className="accessibility-toggle">
            <span>Head Movement Tracking</span>
            <button
              className={`toggle-button${headMovementEnabled ? " active" : ""}`}
              type="button"
              role="switch"
              aria-checked={headMovementEnabled}
              aria-label="Toggle Head Movement Tracking accessibility mode"
              onClick={() => setHeadMovementEnabled((enabled) => !enabled)}
            >
              <span />
            </button>
          </div>
        </div>
      </section>

      <section className="trend-card" aria-labelledby="trend-title">
        <div className="trend-heading">
          <div>
            <h2 id="trend-title">Wellness trends</h2>
            <p>Stress progression and emotional state across today</p>
          </div>
          <div className="trend-legend" aria-label="Chart legend">
            <span className="legend-item"><span className="legend-swatch" /> Stress intensity</span>
            <span className="legend-item"><span className="legend-swatch emotion" /> Emotion state</span>
          </div>
        </div>
        <div className="trend-chart" role="img" aria-label="Historical stress and emotional state chart">
          <div className="trend-axis" aria-hidden="true"><span>High</span><span>Medium</span><span>Low</span></div>
          <div className="trend-plot">
            {wellnessTrend.map((point) => (
              <div className="trend-column" key={point.time} title={`${point.time}: ${point.stress}% stress, ${point.emotion}`}>
                <span className="emotion-marker" aria-hidden="true" />
                <span className="stress-bar" style={{ height: `${point.stress}%` }} aria-hidden="true" />
                <span className="trend-time">{point.time}</span>
              </div>
            ))}
          </div>
        </div>
        <p className="trend-summary">Emotional state moved from Calm to Focused as stress eased after midday.</p>
      </section>

      <p className="wellness-footer">
        Last synced {lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
      </p>
    </main>
  );
}

export default MentalWellness;
