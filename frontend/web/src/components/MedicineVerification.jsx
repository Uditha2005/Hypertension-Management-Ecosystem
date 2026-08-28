import React, { useEffect, useRef, useState } from "react";

const scanTypes = [
  { id: "strip", label: "Medicine strip", hint: "Blister packs and tablets" },
  { id: "bottle", label: "Pill bottle", hint: "Labels and dosage details" },
  { id: "prescription", label: "Prescription", hint: "Handwritten instructions" },
];

const comparisonRows = [
  { field: "Medicine name", prescribed: "Amlodipine", scanned: "Amlodipine", status: "Match" },
  { field: "Strength", prescribed: "5 mg", scanned: "10 mg", status: "Incorrect Dosage Risk" },
  { field: "Instructions", prescribed: "Once daily", scanned: "Twice daily", status: "Mismatch" },
];

const xaiSignals = [
  { label: "Strength differs from prescription", detail: "Detected 10 mg; prescribed strength is 5 mg.", tone: "risk" },
  { label: "Instructions differ", detail: "The provided label says twice daily; the prescription says once daily.", tone: "risk" },
  { label: "Medicine name is consistent", detail: "The detected name matches the prescribed medicine.", tone: "clear" },
];

const interactionRisks = [
  { medicine: "Simvastatin", risk: "Moderate interaction risk", tone: "moderate" },
  { medicine: "Grapefruit products", risk: "Use caution", tone: "caution" },
  { medicine: "Lisinopril", risk: "No known interaction", tone: "clear" },
];

const specialistDoctors = [
  { name: "Dr. Maya Patel", specialty: "Cardiologist", availability: "Today, 3:30 PM" },
  { name: "Dr. Daniel Okafor", specialty: "Clinical Pharmacist", availability: "Today, 4:15 PM" },
  { name: "Dr. Elena Rossi", specialty: "Internal Medicine", availability: "Tomorrow, 9:00 AM" },
];

function MedicineVerification() {
  const [selectedType, setSelectedType] = useState("strip");
  const [previewUrl, setPreviewUrl] = useState("");
  const [fileName, setFileName] = useState("");
  const [cameraActive, setCameraActive] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [scanStatus, setScanStatus] = useState("Ready for a clear image");
  const [symptoms, setSymptoms] = useState("");
  const [urgency, setUrgency] = useState("Soon");
  const [symptomStatus, setSymptomStatus] = useState("");
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  useEffect(() => {
    if (cameraActive && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [cameraActive]);

  const useImage = (file) => {
    if (!file || !file.type.startsWith("image/")) {
      setScanStatus("Please choose an image file");
      return;
    }

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(URL.createObjectURL(file));
    setFileName(file.name);
    setScanStatus("Image ready to verify");
  };

  const handleFileChange = (event) => {
    useImage(event.target.files[0]);
    event.target.value = "";
  };

  const toggleCamera = async () => {
    if (cameraActive) {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setCameraActive(false);
      setScanStatus("Camera paused");
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      setScanStatus("Camera is not available in this browser");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });
      streamRef.current = stream;
      setCameraActive(true);
      setScanStatus("Camera active - center the medicine");
    } catch (error) {
      setScanStatus("Camera access was not granted");
    }
  };

  const capturePhoto = () => {
    if (!videoRef.current || !cameraActive) return;

    const canvas = document.createElement("canvas");
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    canvas.getContext("2d").drawImage(videoRef.current, 0, 0);
    canvas.toBlob((blob) => {
      if (blob) {
        useImage(new File([blob], "medicine-camera-scan.jpg", { type: "image/jpeg" }));
        toggleCamera();
      }
    }, "image/jpeg", 0.92);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);
    useImage(event.dataTransfer.files[0]);
  };

  return (
    <main className="medicine-verification">
      <style>{`
        .medicine-verification {
          --ink: #172d32;
          --muted: #6d7d7e;
          --line: #d8e5e0;
          --canvas: #f3f8f5;
          --teal: #177d75;
          box-sizing: border-box;
          min-height: 100vh;
          padding: clamp(24px, 5vw, 64px);
          color: var(--ink);
          background: radial-gradient(circle at 8% 0%, #dcefe8 0, transparent 30%), var(--canvas);
          font-family: Georgia, "Times New Roman", serif;
        }
        .medicine-verification * { box-sizing: border-box; }
        .medicine-header, .medicine-content { max-width: 1120px; margin: 0 auto; }
        .medicine-header { margin-bottom: 30px; }
        .medicine-kicker {
          margin: 0 0 10px;
          color: var(--teal);
          font: 700 0.74rem/1.2 Arial, sans-serif;
          letter-spacing: 0.12em;
          text-transform: uppercase;
        }
        .medicine-title { margin: 0; font-size: clamp(2.3rem, 5vw, 4.2rem); font-weight: 400; line-height: 1; }
        .medicine-subtitle { max-width: 590px; margin: 16px 0 0; color: var(--muted); font: 1rem/1.6 Arial, sans-serif; }
        .medicine-content { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(260px, 0.8fr); gap: 18px; }
        .scan-panel, .type-panel { border: 1px solid var(--line); border-radius: 8px; background: #fff; box-shadow: 0 14px 32px rgba(39, 76, 69, 0.07); }
        .scan-panel { padding: clamp(18px, 3vw, 30px); }
        .scan-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 18px; }
        .panel-label { margin: 0; font: 700 0.74rem Arial, sans-serif; letter-spacing: 0.08em; text-transform: uppercase; }
        .status { color: var(--teal); font: 0.78rem Arial, sans-serif; text-align: right; }
        .drop-zone { position: relative; display: grid; min-height: 360px; place-items: center; overflow: hidden; border: 1px dashed #9dbab1; border-radius: 6px; background: #eef6f1; transition: border-color 180ms, background 180ms; }
        .drop-zone.dragging { border-color: var(--teal); background: #e1f2eb; }
        .drop-zone.has-preview { background: #172d32; }
        .scan-preview, .camera-view { width: 100%; height: 100%; min-height: 360px; object-fit: contain; }
        .camera-view { object-fit: cover; }
        .scan-guide { position: absolute; inset: 12% 12%; border: 1px solid rgba(255, 255, 255, 0.8); border-radius: 5px; pointer-events: none; }
        .drop-prompt { padding: 24px; text-align: center; }
        .drop-icon { display: grid; width: 54px; height: 54px; margin: 0 auto 16px; place-items: center; border-radius: 50%; color: var(--teal); background: #d7eee5; font: 700 1.5rem Arial, sans-serif; }
        .drop-prompt h2 { margin: 0; font-size: 1.45rem; font-weight: 400; }
        .drop-prompt p { margin: 9px 0 20px; color: var(--muted); font: 0.86rem/1.5 Arial, sans-serif; }
        .actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; }
        .action-button { min-height: 42px; padding: 0 16px; border: 1px solid var(--teal); border-radius: 5px; color: #fff; background: var(--teal); font: 700 0.8rem Arial, sans-serif; cursor: pointer; }
        .action-button.secondary { color: var(--teal); background: #fff; }
        .action-button:hover { filter: brightness(0.94); }
        .action-button:focus-visible, .type-option:focus-visible { outline: 3px solid #f0bd68; outline-offset: 2px; }
        .file-name { margin: 14px 0 0; color: var(--muted); font: 0.78rem Arial, sans-serif; text-align: center; overflow-wrap: anywhere; }
        .type-panel { padding: 24px; align-self: start; }
        .type-panel h2 { margin: 0 0 6px; font-size: 1.55rem; font-weight: 400; }
        .type-panel > p { margin: 0 0 20px; color: var(--muted); font: 0.84rem/1.5 Arial, sans-serif; }
        .type-list { display: grid; gap: 10px; }
        .type-option { width: 100%; padding: 15px; border: 1px solid var(--line); border-radius: 6px; color: var(--ink); background: #fff; text-align: left; cursor: pointer; }
        .type-option.selected { border-color: var(--teal); background: #e8f5ef; box-shadow: inset 3px 0 var(--teal); }
        .type-option strong { display: block; margin-bottom: 5px; font: 700 0.86rem Arial, sans-serif; }
        .type-option span { color: var(--muted); font: 0.78rem Arial, sans-serif; }
        .privacy-note { margin: 22px 0 0; padding-top: 18px; border-top: 1px solid var(--line); color: var(--muted); font: 0.75rem/1.5 Arial, sans-serif; }
        .comparison-panel { max-width: 1120px; margin: 18px auto 0; padding: clamp(18px, 3vw, 30px); border: 1px solid var(--line); border-radius: 8px; background: #fff; box-shadow: 0 14px 32px rgba(39, 76, 69, 0.07); }
        .comparison-heading { display: flex; align-items: end; justify-content: space-between; gap: 18px; margin-bottom: 18px; }
        .comparison-heading h2 { margin: 0; font-size: 1.65rem; font-weight: 400; }
        .comparison-heading p { max-width: 350px; margin: 0; color: var(--muted); font: 0.78rem/1.5 Arial, sans-serif; text-align: right; }
        .comparison-table { width: 100%; border-collapse: collapse; font-family: Arial, sans-serif; }
        .comparison-table th { padding: 0 14px 12px; color: var(--muted); font: 700 0.7rem Arial, sans-serif; letter-spacing: 0.06em; text-align: left; text-transform: uppercase; }
        .comparison-table th:first-child, .comparison-table td:first-child { padding-left: 0; }
        .comparison-table th:last-child, .comparison-table td:last-child { padding-right: 0; }
        .comparison-table td { padding: 15px 14px; border-top: 1px solid var(--line); color: var(--ink); font-size: 0.87rem; vertical-align: middle; }
        .comparison-table td:first-child { color: var(--muted); font-size: 0.78rem; font-weight: 700; }
        .comparison-badge { display: inline-flex; align-items: center; min-height: 26px; padding: 5px 9px; border-radius: 999px; font: 700 0.68rem Arial, sans-serif; white-space: nowrap; }
        .comparison-badge.match { color: #227c6e; background: #dff1eb; }
        .comparison-badge.mismatch { color: #b04c3e; background: #fbe1da; }
        .comparison-badge.dosage-risk { color: #9a6a1c; background: #fff0c9; }
        .xai-panel { max-width: 1120px; margin: 18px auto 0; padding: clamp(18px, 3vw, 30px); border: 1px solid #e5cdbd; border-radius: 8px; background: #fffaf6; box-shadow: 0 14px 32px rgba(92, 61, 42, 0.06); }
        .xai-heading { display: flex; align-items: end; justify-content: space-between; gap: 18px; margin-bottom: 22px; }
        .xai-heading h2 { margin: 0; font-size: 1.65rem; font-weight: 400; }
        .xai-heading p { max-width: 430px; margin: 0; color: var(--muted); font: 0.78rem/1.5 Arial, sans-serif; text-align: right; }
        .xai-grid { display: grid; grid-template-columns: 1.2fr 0.8fr 0.9fr; gap: 20px; }
        .xai-column { min-width: 0; }
        .xai-column + .xai-column { padding-left: 20px; border-left: 1px solid #eadbd1; }
        .xai-column h3 { margin: 0 0 14px; font: 700 0.72rem Arial, sans-serif; letter-spacing: 0.07em; text-transform: uppercase; }
        .reason-list, .interaction-list { display: grid; gap: 12px; margin: 0; padding: 0; list-style: none; }
        .reason-item { display: grid; grid-template-columns: 9px 1fr; gap: 10px; }
        .reason-dot { width: 9px; height: 9px; margin-top: 5px; border-radius: 50%; background: #d67a5d; }
        .reason-dot.clear { background: #2b9583; }
        .reason-item strong { display: block; margin-bottom: 4px; font: 700 0.8rem/1.3 Arial, sans-serif; }
        .reason-item span { display: block; color: var(--muted); font: 0.76rem/1.45 Arial, sans-serif; }
        .authenticity-options { display: grid; gap: 9px; }
        .authenticity-option { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 11px 12px; border: 1px solid var(--line); border-radius: 5px; background: #fff; font: 700 0.78rem Arial, sans-serif; }
        .authenticity-option.selected { border-color: #d67a5d; background: #fff0e9; }
        .xai-badge { display: inline-flex; align-items: center; min-height: 24px; padding: 4px 8px; border-radius: 999px; font: 700 0.65rem Arial, sans-serif; white-space: nowrap; }
        .xai-badge.original, .xai-badge.clear { color: #227c6e; background: #dff1eb; }
        .xai-badge.suspicious, .xai-badge.moderate { color: #b04c3e; background: #fbe1da; }
        .xai-badge.caution { color: #9a6a1c; background: #fff0c9; }
        .interaction-item { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding-bottom: 11px; border-bottom: 1px solid #eadbd1; font: 0.78rem Arial, sans-serif; }
        .interaction-item:last-child { padding-bottom: 0; border-bottom: 0; }
        .symptom-panel { max-width: 1120px; margin: 18px auto 0; padding: clamp(18px, 3vw, 30px); border: 1px solid #cbdde6; border-radius: 8px; background: #f7fbfc; box-shadow: 0 14px 32px rgba(42, 75, 85, 0.06); }
        .symptom-heading { display: flex; align-items: end; justify-content: space-between; gap: 18px; margin-bottom: 22px; }
        .symptom-heading h2 { margin: 0; font-size: 1.65rem; font-weight: 400; }
        .symptom-heading p { max-width: 430px; margin: 0; color: var(--muted); font: 0.78rem/1.5 Arial, sans-serif; text-align: right; }
        .symptom-form { display: grid; grid-template-columns: minmax(0, 1fr) 190px auto; align-items: end; gap: 12px; }
        .symptom-field { display: grid; gap: 7px; }
        .symptom-field label { color: var(--ink); font: 700 0.72rem Arial, sans-serif; letter-spacing: 0.06em; text-transform: uppercase; }
        .symptom-field textarea, .symptom-field select { width: 100%; min-height: 44px; padding: 11px 12px; border: 1px solid #b9d0d8; border-radius: 5px; color: var(--ink); background: #fff; font: 0.84rem Arial, sans-serif; }
        .symptom-field textarea { min-height: 82px; resize: vertical; }
        .symptom-field textarea:focus, .symptom-field select:focus { outline: 3px solid #c4e0e8; border-color: #397e91; }
        .symptom-submit { min-height: 44px; padding: 0 16px; border: 1px solid #28758a; border-radius: 5px; color: #fff; background: #28758a; font: 700 0.8rem Arial, sans-serif; cursor: pointer; }
        .symptom-submit:hover { filter: brightness(0.94); }
        .urgency-indicator { display: flex; align-items: center; gap: 8px; min-height: 30px; margin-top: 12px; color: var(--muted); font: 0.78rem Arial, sans-serif; }
        .urgency-dot { width: 10px; height: 10px; border-radius: 50%; background: #e0a13c; box-shadow: 0 0 0 4px #ffefd0; }
        .urgency-dot.now { background: #c9574d; box-shadow: 0 0 0 4px #f9dfda; }
        .urgency-dot.routine { background: #2b9583; box-shadow: 0 0 0 4px #dff1eb; }
        .symptom-status { margin: 12px 0 0; color: #28758a; font: 0.78rem Arial, sans-serif; }
        .doctor-list { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 26px; }
        .doctor-card { padding: 16px; border: 1px solid #d4e3e7; border-radius: 6px; background: #fff; }
        .doctor-card h3 { margin: 0 0 5px; font: 700 0.88rem Arial, sans-serif; }
        .doctor-specialty { margin: 0; color: #28758a; font: 700 0.75rem Arial, sans-serif; }
        .doctor-availability { margin: 12px 0; color: var(--muted); font: 0.75rem Arial, sans-serif; }
        .doctor-book { width: 100%; min-height: 36px; border: 1px solid #28758a; border-radius: 5px; color: #28758a; background: #fff; font: 700 0.74rem Arial, sans-serif; cursor: pointer; }
        .doctor-book:hover { color: #fff; background: #28758a; }
        @media (max-width: 760px) { .medicine-content { grid-template-columns: 1fr; } .drop-zone, .scan-preview, .camera-view { min-height: 300px; } .scan-toolbar { align-items: flex-start; flex-direction: column; } .status { text-align: left; } .comparison-heading, .xai-heading, .symptom-heading { align-items: flex-start; flex-direction: column; } .comparison-heading p, .xai-heading p, .symptom-heading p { text-align: left; } .comparison-table { min-width: 620px; } .comparison-panel { overflow-x: auto; } .xai-grid { grid-template-columns: 1fr; gap: 22px; } .xai-column + .xai-column { padding-top: 22px; padding-left: 0; border-top: 1px solid #eadbd1; border-left: 0; } .symptom-form { grid-template-columns: 1fr; } .symptom-submit { width: 100%; } .doctor-list { grid-template-columns: 1fr; } }
      `}</style>

      <header className="medicine-header">
        <p className="medicine-kicker">Medicine verification</p>
        <h1 className="medicine-title">Read it before you take it.</h1>
        <p className="medicine-subtitle">Scan a medicine strip, pill bottle, or handwritten prescription to check its details before adding it to your care plan.</p>
      </header>

      <section className="medicine-content" aria-label="Medicine image scanner">
        <div className="scan-panel">
          <div className="scan-toolbar">
            <p className="panel-label">Add an image</p>
            <span className="status" aria-live="polite">{scanStatus}</span>
          </div>
          <div className={`drop-zone${isDragging ? " dragging" : ""}${previewUrl || cameraActive ? " has-preview" : ""}`} onDragOver={(event) => { event.preventDefault(); setIsDragging(true); }} onDragLeave={() => setIsDragging(false)} onDrop={handleDrop}>
            {cameraActive ? <><video ref={videoRef} className="camera-view" autoPlay muted playsInline /><div className="scan-guide" /></> : previewUrl ? <img className="scan-preview" src={previewUrl} alt={`Selected ${selectedType} preview`} /> : <div className="drop-prompt"><div className="drop-icon" aria-hidden="true">+</div><h2>Drop an image here</h2><p>Use a well-lit photo with the medicine name and strength in focus.</p><div className="actions"><button className="action-button" type="button" onClick={() => fileInputRef.current?.click()}>Upload image</button><button className="action-button secondary" type="button" onClick={toggleCamera}>Open camera</button></div></div>}
            {cameraActive && <div className="actions" style={{ position: "absolute", bottom: 18 }}><button className="action-button" type="button" onClick={capturePhoto}>Capture photo</button><button className="action-button secondary" type="button" onClick={toggleCamera}>Close camera</button></div>}
          </div>
          {fileName && <p className="file-name">{fileName}</p>}
          <input ref={fileInputRef} type="file" accept="image/*" capture="environment" onChange={handleFileChange} hidden />
        </div>

        <aside className="type-panel">
          <h2>What are you scanning?</h2>
          <p>Select the closest match to help verification focus on the right details.</p>
          <div className="type-list" role="group" aria-label="Medicine type">
            {scanTypes.map((type) => <button key={type.id} className={`type-option${selectedType === type.id ? " selected" : ""}`} type="button" aria-pressed={selectedType === type.id} onClick={() => setSelectedType(type.id)}><strong>{type.label}</strong><span>{type.hint}</span></button>)}
          </div>
          <p className="privacy-note">Images stay on this device until you choose to submit them for verification.</p>
        </aside>
      </section>

      <section className="comparison-panel" aria-labelledby="comparison-title">
        <div className="comparison-heading">
          <h2 id="comparison-title">Verification comparison</h2>
          <p>Review the prescribed details beside what was detected in the provided medicine.</p>
        </div>
        <table className="comparison-table">
          <thead>
            <tr>
              <th scope="col">Detail</th>
              <th scope="col">Prescribed Medicine</th>
              <th scope="col">Scanned/Provided Medicine</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {comparisonRows.map((row) => (
              <tr key={row.field}>
                <td>{row.field}</td>
                <td>{row.prescribed}</td>
                <td>{row.scanned}</td>
                <td><span className={`comparison-badge ${row.status.toLowerCase().replaceAll(" ", "-")}`}>{row.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="xai-panel" aria-labelledby="xai-title">
        <div className="xai-heading">
          <h2 id="xai-title">Why this warning was flagged</h2>
          <p>These signals explain the verification result and should be reviewed by a pharmacist before use.</p>
        </div>
        <div className="xai-grid">
          <div className="xai-column">
            <h3>Detection signals</h3>
            <ul className="reason-list">
              {xaiSignals.map((signal) => (
                <li className="reason-item" key={signal.label}>
                  <span className={`reason-dot ${signal.tone}`} aria-hidden="true" />
                  <div><strong>{signal.label}</strong><span>{signal.detail}</span></div>
                </li>
              ))}
            </ul>
          </div>
          <div className="xai-column">
            <h3>Brand authenticity</h3>
            <div className="authenticity-options" aria-label="Brand authenticity indicators">
              <div className="authenticity-option"><span>Original packaging</span><span className="xai-badge original">Original</span></div>
              <div className="authenticity-option selected"><span>Suspicious packaging</span><span className="xai-badge suspicious">Suspicious</span></div>
            </div>
          </div>
          <div className="xai-column">
            <h3>Drug interaction risk</h3>
            <ul className="interaction-list">
              {interactionRisks.map((interaction) => (
                <li className="interaction-item" key={interaction.medicine}><span>{interaction.medicine}</span><span className={`xai-badge ${interaction.tone}`}>{interaction.risk}</span></li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="symptom-panel" aria-labelledby="symptom-title">
        <div className="symptom-heading">
          <h2 id="symptom-title">Symptom checker</h2>
          <p>Share what you are feeling so the care team can prepare for a focused telemedicine visit.</p>
        </div>
        <form className="symptom-form" onSubmit={(event) => { event.preventDefault(); setSymptomStatus(symptoms.trim() ? "Symptoms saved for your care team." : "Add at least one symptom to continue."); }}>
          <div className="symptom-field">
            <label htmlFor="current-symptoms">Current symptoms</label>
            <textarea id="current-symptoms" value={symptoms} onChange={(event) => setSymptoms(event.target.value)} placeholder="For example: dizziness, headache, or swelling" />
          </div>
          <div className="symptom-field">
            <label htmlFor="urgency-level">Urgency level</label>
            <select id="urgency-level" value={urgency} onChange={(event) => setUrgency(event.target.value)}>
              <option value="Routine">Routine</option>
              <option value="Soon">Soon</option>
              <option value="Now">Now</option>
            </select>
          </div>
          <button className="symptom-submit" type="submit">Check symptoms</button>
        </form>
        <div className="urgency-indicator" aria-live="polite"><span className={`urgency-dot ${urgency.toLowerCase()}`} aria-hidden="true" /><strong>{urgency} attention</strong><span>{urgency === "Now" ? "Seek urgent medical guidance." : urgency === "Soon" ? "Consider a same-day consultation." : "Monitor and discuss at your next visit."}</span></div>
        {symptomStatus && <p className="symptom-status" aria-live="polite">{symptomStatus}</p>}
        <div className="doctor-list" aria-label="Recommended specialist doctors">
          {specialistDoctors.map((doctor) => <article className="doctor-card" key={doctor.name}><h3>{doctor.name}</h3><p className="doctor-specialty">{doctor.specialty}</p><p className="doctor-availability">Next opening: {doctor.availability}</p><button className="doctor-book" type="button">Book telemedicine visit</button></article>)}
        </div>
      </section>
    </main>
  );
}

export default MedicineVerification;
