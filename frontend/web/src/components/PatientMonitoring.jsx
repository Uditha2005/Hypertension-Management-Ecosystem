import React, { useEffect, useState } from "react";

const cameras = [
  { room: "Room 101", label: "North corridor", code: "CAM-01", tone: "amber" },
  { room: "Room 102", label: "Patient lounge", code: "CAM-02", tone: "teal" },
  { room: "Room 103", label: "Bedroom", code: "CAM-03", tone: "blue" },
  { room: "Room 104", label: "Therapy bay", code: "CAM-04", tone: "coral" },
];

const baseActivities = [
  { name: "Walking", room: "Room 101", confidence: 94, color: "teal", icon: "W" },
  { name: "Sitting", room: "Room 102", confidence: 88, color: "blue", icon: "S" },
  { name: "Limping", room: "Room 104", confidence: 76, color: "coral", icon: "L" },
  { name: "Sleeping", room: "Room 103", confidence: 97, color: "violet", icon: "Z" },
];

const eventLog = [
  { time: "14:32", type: "Inactivity warning", location: "Room 103", severity: "Review" },
  { time: "13:08", type: "Wandering detected", location: "North corridor", severity: "Resolved" },
  { time: "11:46", type: "Inactivity warning", location: "Room 102", severity: "Resolved" },
];

function PatientMonitoring() {
  const [fallDetected, setFallDetected] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [activities, setActivities] = useState(baseActivities);
  const [mobilityScore, setMobilityScore] = useState(78);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setActivities((current) => current.map((activity) => ({
        ...activity,
        confidence: Math.max(68, Math.min(99, activity.confidence + (Math.random() > 0.5 ? 1 : -1))),
      })));
      setMobilityScore((current) => Math.max(72, Math.min(84, current + (Math.random() > 0.5 ? 1 : -1))));
    }, 5000);

    return () => window.clearInterval(interval);
  }, []);

  const triggerFallAlert = () => {
    setAcknowledged(false);
    setFallDetected(true);
  };

  const acknowledgeAlert = () => {
    setAcknowledged(true);
    window.setTimeout(() => setFallDetected(false), 900);
  };

  return (
    <main className="patient-monitoring">
      <style>{`
        .patient-monitoring { --ink: #192b2f; --muted: #718083; --line: #d7e1df; --canvas: #edf3f0; --teal: #167d72; --teal-dark: #0c514d; box-sizing: border-box; min-height: 100vh; padding: clamp(22px, 4vw, 58px); color: var(--ink); background: linear-gradient(135deg, #e9f2ef 0%, #f7f8f3 52%, #f8efe4 100%); font-family: Georgia, "Times New Roman", serif; }
        .patient-monitoring * { box-sizing: border-box; }
        .monitoring-shell { max-width: 1240px; margin: 0 auto; }
        .monitoring-header { display: flex; align-items: end; justify-content: space-between; gap: 24px; margin-bottom: 28px; }
        .monitoring-kicker { margin: 0 0 10px; color: var(--teal); font: 700 .72rem Arial, sans-serif; letter-spacing: .14em; text-transform: uppercase; }
        .monitoring-title { margin: 0; font-size: clamp(2.2rem, 5vw, 4.35rem); font-weight: 400; line-height: .98; }
        .monitoring-intro { max-width: 570px; margin: 15px 0 0; color: var(--muted); font: 1rem/1.55 Arial, sans-serif; }
        .monitoring-clock { display: flex; align-items: center; gap: 10px; padding: 10px 13px; border: 1px solid var(--line); background: rgba(255,255,255,.62); color: var(--teal-dark); font: 700 .72rem Arial, sans-serif; white-space: nowrap; }
        .live-dot { width: 8px; height: 8px; border-radius: 50%; background: #e45e4f; box-shadow: 0 0 0 5px #f8deda; }
        .alert-banner { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 18px; padding: 17px 20px; border: 1px solid #e7b2a9; background: #fff3ef; }
        .alert-copy { display: flex; align-items: center; gap: 13px; }
        .alert-symbol { display: grid; width: 36px; height: 36px; flex: 0 0 auto; place-items: center; border-radius: 50%; color: #a83e34; background: #f7d6d0; font: 700 1.1rem Arial, sans-serif; }
        .alert-banner h2 { margin: 0; color: #7f312b; font: 700 .84rem Arial, sans-serif; letter-spacing: .05em; text-transform: uppercase; }
        .alert-banner p { margin: 4px 0 0; color: #9b6058; font: .78rem Arial, sans-serif; }
        .alert-button { min-height: 40px; padding: 0 15px; border: 1px solid #bb5145; color: #fff; background: #b84e42; font: 700 .76rem Arial, sans-serif; cursor: pointer; }
        .alert-button:hover { background: #963d35; }
        .feed-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
        .feed-card, .panel { border: 1px solid var(--line); background: rgba(255,255,255,.88); box-shadow: 0 12px 28px rgba(38, 65, 60, .07); }
        .feed-card { overflow: hidden; }
        .feed-visual { position: relative; height: clamp(190px, 24vw, 270px); overflow: hidden; background: #263c3b; }
        .feed-visual::before { position: absolute; inset: 0; background: repeating-linear-gradient(0deg, rgba(255,255,255,.045) 0 1px, transparent 1px 5px), linear-gradient(135deg, transparent 44%, rgba(222, 186, 124, .2) 45% 47%, transparent 48%), linear-gradient(90deg, #1e3838 0 24%, #54706a 25% 26%, #263e3d 27% 67%, #667c70 68% 69%, #1d3435 70%); content: ""; opacity: .92; }
        .feed-visual::after { position: absolute; right: 14%; bottom: 18%; width: 42px; height: 82px; border-radius: 45% 45% 20% 20%; background: rgba(238, 196, 132, .48); box-shadow: -72px 15px 0 -13px rgba(204, 227, 205, .3); content: ""; filter: blur(1px); }
        .feed-top, .feed-bottom { position: absolute; right: 14px; left: 14px; z-index: 1; display: flex; justify-content: space-between; color: #f1f6ee; font: .66rem Arial, sans-serif; }
        .feed-top { top: 13px; } .feed-bottom { bottom: 13px; align-items: end; }
        .camera-code { padding: 5px 7px; background: rgba(17, 31, 32, .7); letter-spacing: .08em; }
        .recording { display: flex; align-items: center; gap: 6px; } .recording::before { width: 6px; height: 6px; border-radius: 50%; background: #f06b5a; content: ""; }
        .feed-meta { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 13px 15px; }
        .feed-name { margin: 0; font: 700 .85rem Arial, sans-serif; } .feed-location { margin: 4px 0 0; color: var(--muted); font: .7rem Arial, sans-serif; }
        .status-badge { padding: 6px 8px; color: #167366; background: #ddf0e9; font: 700 .64rem Arial, sans-serif; white-space: nowrap; }
        .section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; margin: 38px 0 15px; }
        .section-heading h2 { margin: 0; font-size: 1.6rem; font-weight: 400; } .section-heading p { margin: 0; color: var(--muted); font: .75rem Arial, sans-serif; }
        .har-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
        .har-card { padding: 16px; border: 1px solid var(--line); background: #fff; }
        .har-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
        .posture-icon { display: grid; width: 32px; height: 32px; place-items: center; border-radius: 50%; color: var(--accent); background: var(--tint); font: 700 .75rem Arial, sans-serif; }
        .har-state { margin: 18px 0 4px; font-size: 1.25rem; } .har-room { margin: 0; color: var(--muted); font: .72rem Arial, sans-serif; }
        .confidence-line { display: flex; justify-content: space-between; margin: 19px 0 7px; color: var(--muted); font: .66rem Arial, sans-serif; } .confidence-line strong { color: var(--ink); }
        .meter, .mobility-meter { height: 6px; overflow: hidden; background: #e5ecea; } .meter span, .mobility-meter span { display: block; height: 100%; background: var(--accent); transition: width 500ms ease; }
        .tone-teal { --accent: #168274; --tint: #d9eee8; } .tone-blue { --accent: #4c789b; --tint: #e0ebf2; } .tone-coral { --accent: #d36b57; --tint: #f8e0d9; } .tone-violet { --accent: #7c7198; --tint: #eae6f1; }
        .dashboard-grid { display: grid; grid-template-columns: minmax(0, .85fr) minmax(0, 1.15fr); gap: 14px; }
        .panel { padding: 21px; } .panel h3 { margin: 0; font-size: 1.15rem; font-weight: 400; } .panel-note { margin: 6px 0 22px; color: var(--muted); font: .74rem/1.4 Arial, sans-serif; }
        .mobility-score { display: flex; align-items: end; justify-content: space-between; margin: 24px 0 9px; } .score-number { font-size: 3.6rem; line-height: .9; } .score-label { color: var(--teal); font: 700 .7rem Arial, sans-serif; }
        .mobility-meter { height: 10px; } .mobility-meter span { background: #218b79; } .analytics { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 22px; } .analytic { padding-top: 12px; border-top: 1px solid var(--line); } .analytic strong { display: block; font-size: 1.25rem; font-weight: 400; } .analytic span { color: var(--muted); font: .68rem Arial, sans-serif; }
        .event-table { width: 100%; border-collapse: collapse; font: .74rem Arial, sans-serif; } .event-table th { padding: 0 0 11px; color: var(--muted); font-size: .64rem; text-align: left; letter-spacing: .07em; text-transform: uppercase; } .event-table td { padding: 13px 5px 13px 0; border-top: 1px solid var(--line); } .event-table td:last-child, .event-table th:last-child { text-align: right; } .event-state { color: #53736a; } .event-review { color: #a87328; }
        .alert-modal { position: fixed; inset: 0; z-index: 4; display: grid; place-items: center; padding: 20px; background: rgba(27, 40, 39, .48); } .alert-modal-card { width: min(100%, 420px); padding: 27px; border-top: 5px solid #c74f42; background: #fff; box-shadow: 0 25px 65px rgba(25, 37, 35, .28); } .modal-label { margin: 0 0 10px; color: #b34237; font: 700 .7rem Arial, sans-serif; letter-spacing: .1em; text-transform: uppercase; } .modal-title { margin: 0; font-size: 2rem; font-weight: 400; } .modal-details { margin: 20px 0 24px; padding: 14px; background: #fff3ef; color: #70443e; font: .8rem/1.8 Arial, sans-serif; } .modal-details strong { color: #3b2b29; } .acknowledge-button { width: 100%; min-height: 46px; border: 0; color: #fff; background: #b84e42; font: 700 .8rem Arial, sans-serif; cursor: pointer; } .acknowledge-button:disabled { background: #6b9a8b; cursor: default; }
        @media (max-width: 760px) { .monitoring-header, .alert-banner { align-items: flex-start; flex-direction: column; } .monitoring-clock { align-self: stretch; justify-content: center; } .alert-button { width: 100%; } .feed-grid, .dashboard-grid { grid-template-columns: 1fr; } .har-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
        @media (max-width: 430px) { .har-grid { grid-template-columns: 1fr; } .feed-meta { align-items: flex-start; flex-direction: column; } }
        @media (prefers-reduced-motion: no-preference) { .feed-card, .har-card, .panel { animation: reveal 480ms both; } .feed-card:nth-child(2), .har-card:nth-child(2) { animation-delay: 70ms; } .feed-card:nth-child(3), .har-card:nth-child(3) { animation-delay: 140ms; } .feed-card:nth-child(4), .har-card:nth-child(4) { animation-delay: 210ms; } @keyframes reveal { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } } }
      `}</style>

      <div className="monitoring-shell">
        <header className="monitoring-header">
          <div><p className="monitoring-kicker">Behavioral intelligence / ward 04</p><h1 className="monitoring-title">Patient monitoring</h1><p className="monitoring-intro">A calm, continuous view of movement, posture, and mobility across the care floor.</p></div>
          <div className="monitoring-clock"><span className="live-dot" /> LIVE MONITORING</div>
        </header>

        <section className="alert-banner" aria-labelledby="alert-heading">
          <div className="alert-copy"><span className="alert-symbol">!</span><div><h2 id="alert-heading">Fall detection & emergency alert</h2><p>Simulation controls are active. Trigger a test event to rehearse the response workflow.</p></div></div>
          <button className="alert-button" type="button" onClick={triggerFallAlert}>Trigger fall event</button>
        </section>

        <section aria-labelledby="feeds-heading"><div className="section-heading"><h2 id="feeds-heading">Live camera grid</h2><p>4 feeds connected / encrypted relay</p></div><div className="feed-grid">{cameras.map((camera) => <article className="feed-card" key={camera.code}><div className={`feed-visual tone-${camera.tone}`}><div className="feed-top"><span className="camera-code">{camera.code}</span><span className="recording">REC 00:24:18</span></div><div className="feed-bottom"><span>Behavioral feed</span><span>1080p</span></div></div><div className="feed-meta"><div><p className="feed-name">{camera.room}</p><p className="feed-location">{camera.label}</p></div><span className="status-badge">Active</span></div></article>)}</div></section>

        <section aria-labelledby="har-heading"><div className="section-heading"><h2 id="har-heading">Human activity recognition</h2><p>Posture inference / refreshed every 5 sec</p></div><div className="har-grid">{activities.map((activity) => <article className={`har-card tone-${activity.color}`} key={activity.name}><div className="har-top"><span className="posture-icon">{activity.icon}</span><span className="status-badge">Tracked</span></div><h3 className="har-state">{activity.name}</h3><p className="har-room">{activity.room}</p><div className="confidence-line"><span>Model confidence</span><strong>{activity.confidence}%</strong></div><div className="meter"><span style={{ width: `${activity.confidence}%` }} /></div></article>)}</div></section>

        <section aria-labelledby="rehab-heading"><div className="section-heading"><h2 id="rehab-heading">Rehabilitation & mobility</h2><p>Daily mobility overview</p></div><div className="dashboard-grid"><article className="panel"><h3>Mobility score</h3><p className="panel-note">Composite score from gait, balance, and active minutes.</p><div className="mobility-score"><span className="score-number">{mobilityScore}</span><span className="score-label">GOOD / 100</span></div><div className="mobility-meter"><span style={{ width: `${mobilityScore}%` }} /></div><div className="analytics"><div className="analytic"><strong>86%</strong><span>Walking stability</span></div><div className="analytic"><strong>42 min</strong><span>Active time today</span></div><div className="analytic"><strong>1.8 km</strong><span>Distance covered</span></div><div className="analytic"><strong>+6%</strong><span>Vs. last week</span></div></div></article><article className="panel"><h3>Emergency event log</h3><p className="panel-note">Recent inactivity and wandering warnings.</p><table className="event-table"><thead><tr><th>Time</th><th>Event</th><th>Location</th><th>Status</th></tr></thead><tbody>{eventLog.map((event) => <tr key={`${event.time}-${event.type}`}><td>{event.time}</td><td>{event.type}</td><td>{event.location}</td><td className={event.severity === "Review" ? "event-review" : "event-state"}>{event.severity}</td></tr>)}</tbody></table></article></div></section>
      </div>

      {fallDetected && <div className="alert-modal" role="dialog" aria-modal="true" aria-labelledby="fall-title"><div className="alert-modal-card"><p className="modal-label">Priority emergency / event 0042</p><h2 className="modal-title" id="fall-title">Fall detected event</h2><div className="modal-details"><div><strong>Patient location:</strong> Room 104 - Therapy bay</div><div><strong>Detected:</strong> Today, 14:38:21</div><div><strong>Signal:</strong> Sudden downward movement</div></div><button className="acknowledge-button" type="button" onClick={acknowledgeAlert} disabled={acknowledged}>{acknowledged ? "Emergency acknowledged" : "Acknowledge emergency"}</button></div></div>}
    </main>
  );
}

export default PatientMonitoring;