import React, { useEffect, useRef, useState } from "react";
import "./TrayVerification.css";

const API = (
  process.env.REACT_APP_API_URL || "http://localhost:8000"
).replace(/\/$/, "");

async function request(path, options = {}) {
  const response = await fetch(`${API}/api/medicine${path}`, options);
  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof data.error === "string"
        ? data.error
        : typeof data.detail === "string"
        ? data.detail
        : "The request failed."
    );
  }

  return data;
}

function validDetection(item) {
  return (
    typeof item.label === "string" &&
    Number.isFinite(item.confidence) &&
    item.confidence >= 0 &&
    item.confidence <= 1 &&
    Array.isArray(item.bbox) &&
    item.bbox.length === 4 &&
    item.bbox.every(Number.isFinite)
  );
}

export default function TrayVerification() {
  const mounted = useRef(false);
  const [page, setPage] = useState("verify");
  const [patients, setPatients] = useState([]);
  const [products, setProducts] = useState([]);
  const [patientId, setPatientId] = useState("");
  const [prescription, setPrescription] = useState(null);
  const [modelReady, setModelReady] = useState(false);
  const [prescriptionReady, setPrescriptionReady] = useState(false);
  const [connected, setConnected] = useState(false);

  const [photo, setPhoto] = useState("");
  const [fileName, setFileName] = useState("");
  const [recognition, setRecognition] = useState(null);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);

  const [loading, setLoading] = useState(true);
  const [loadingPrescription, setLoadingPrescription] = useState(false);
  const [operation, setOperation] = useState("");
  const [error, setError] = useState("");

  const busy = operation !== "";

  useEffect(() => {
    mounted.current = true;
    let cancelled = false;

    async function loadData() {
      try {
        const data = await request("/bootstrap");
        if (cancelled) return;

        if (data.mode !== "live") {
          throw new Error("The real recognition service is unavailable.");
        }

        setConnected(true);
        setModelReady(data.modelReady === true);
        setPrescriptionReady(data.prescriptionReady === true);
        setPatients(Array.isArray(data.patients) ? data.patients : []);
        setProducts(Array.isArray(data.products) ? data.products : []);

        const records = await request("/history");
        if (!cancelled && Array.isArray(records)) {
          setHistory(records.filter((record) => record.mode === "live"));
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof TypeError
              ? "Cannot reach the medicine service. Start the Python API on port 8000."
              : err.message
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadData();

    return () => {
      cancelled = true;
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    setPrescription(null);
    setResult(null);

    if (!patientId || !prescriptionReady) {
      setLoadingPrescription(false);
      return;
    }

    let cancelled = false;
    setLoadingPrescription(true);

    request(`/patients/${encodeURIComponent(patientId)}/prescription`)
      .then((data) => {
        if (cancelled) return;

        if (
          data.patientId !== patientId ||
          data.status !== "active" ||
          !Array.isArray(data.items) ||
          data.items.length === 0
        ) {
          throw new Error("No valid active prescription is available.");
        }

        setPrescription(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoadingPrescription(false);
      });

    return () => {
      cancelled = true;
    };
  }, [patientId, prescriptionReady]);

  function productName(id) {
    const product = products.find((item) => item.id === id);
    return product
      ? [product.name, product.strength].filter(Boolean).join(" · ")
      : id || "Unidentified medicine";
  }

  function changePatient(event) {
    setPatientId(event.target.value);
    setPrescription(null);
    setResult(null);
    setError("");
  }

  function loadPhoto(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    setPhoto("");
    setFileName("");
    setRecognition(null);
    setResult(null);
    setError("");

    if (
      !["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
      file.size > 5 * 1024 * 1024
    ) {
      setError("Choose a JPG, PNG or WebP image smaller than 5 MB.");
      event.target.value = "";
      return;
    }

    setOperation("reading");
    const reader = new FileReader();

    reader.onload = () => {
      if (!mounted.current) return;
      setPhoto(String(reader.result));
      setFileName(file.name);
      setOperation("");
    };

    reader.onerror = () => {
      if (!mounted.current) return;
      setError("Could not read the photo. Please select it again.");
      setOperation("");
    };

    reader.readAsDataURL(file);
  }

  async function detectPhoto() {
    if (!connected || !modelReady || !photo || busy) return;

    setOperation("detecting");
    setError("");
    setRecognition(null);
    setResult(null);

    try {
      const data = await request("/detect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ imageData: photo }),
      });

      if (!mounted.current) return;

      if (
        data.mode !== "live" ||
        !Array.isArray(data.detections) ||
        !data.detections.every(validDetection) ||
        typeof data.annotatedImage !== "string" ||
        !data.annotatedImage.startsWith("data:image/jpeg;base64,")
      ) {
        throw new Error("The service returned an invalid detection result.");
      }

      setRecognition(data);
    } catch (err) {
      if (mounted.current) {
        setError(
          err instanceof TypeError
            ? "Cannot reach the recognition service. Check the Python API."
            : err.message
        );
      }
    } finally {
      if (mounted.current) setOperation("");
    }
  }

  async function verifyTray() {
    if (
      !connected ||
      !modelReady ||
      !prescriptionReady ||
      !prescription ||
      !photo ||
      busy
    ) {
      return;
    }

    setOperation("verifying");
    setError("");
    setResult(null);

    try {
      const data = await request("/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patientId,
          prescriptionId: prescription.id,
          imageData: photo,
        }),
      });

      if (!mounted.current) return;

      if (
        data.mode !== "live" ||
        data.patientId !== patientId ||
        data.prescription?.id !== prescription.id ||
        !Array.isArray(data.rows) ||
        !Array.isArray(data.uncertain)
      ) {
        throw new Error("The service returned an invalid verification result.");
      }

      setResult(data);
      setHistory((previous) => [data, ...previous].slice(0, 200));
    } catch (err) {
      if (mounted.current) setError(err.message);
    } finally {
      if (mounted.current) setOperation("");
    }
  }

  const canDetect = connected && modelReady && photo && !busy;
  const canVerify =
    canDetect && prescriptionReady && prescription && !loadingPrescription;

  return (
    <div className="tray-app">
      <aside className="tray-sidebar">
        <div className="tray-logo">H<span>+</span></div>
        <h2>Hypertension Care</h2>
        <p>Medicine verification</p>

        <nav aria-label="Medicine verification">
          <button
            type="button"
            className={page === "verify" ? "active" : ""}
            onClick={() => setPage("verify")}
          >
            Review tray
          </button>
          <button
            type="button"
            className={page === "history" ? "active" : ""}
            onClick={() => setPage("history")}
          >
            Verification history
          </button>
        </nav>

        <div className="sidebar-footer">
          <strong>Medicine verification</strong>
          <br />
          Prepared tray review
        </div>
      </aside>

      <main>
        <header>
          <div>
            <div className="eyebrow">CAREGIVER WORKSPACE</div>
            <h1>
              {page === "verify"
                ? "Check the prepared tray"
                : "Verification history"}
            </h1>
            <p>
              Identify pills in a tray photo and review the recognition results.
            </p>
          </div>
        </header>

        {error && <div className="error" role="alert">{error}</div>}

        {loading ? (
          <p role="status">Connecting to the medicine service…</p>
        ) : page === "history" ? (
          <section className="card">
            <h2>Previous verifications</h2>
            {history.length === 0 ? (
              <div className="empty-state">
                No prescription verification records available.
                Pill detection alone does not create a verification record.
              </div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Patient</th>
                      <th>Date and time</th>
                      <th>Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((record) => (
                      <tr key={record.id}>
                        <td>{record.patientName || record.patientId}</td>
                        <td>{new Date(record.createdAt).toLocaleString()}</td>
                        <td>{record.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        ) : (
          <>
            <div className="workflow-grid">
              <section className="card">
                <div className="step">01 · PATIENT & PRESCRIPTION</div>
                <h2>Who is this tray for?</h2>

                <label htmlFor="tray-patient">Select patient</label>
                <select
                  id="tray-patient"
                  value={patientId}
                  onChange={changePatient}
                  disabled={
                    busy ||
                    !connected ||
                    !prescriptionReady ||
                    patients.length === 0
                  }
                >
                  <option value="">Choose a patient</option>
                  {patients.map((patient) => (
                    <option key={patient.id} value={patient.id}>
                      {patient.name} · {patient.id}
                    </option>
                  ))}
                </select>

                {loadingPrescription ? (
                  <p className="muted" role="status">Loading prescription…</p>
                ) : prescription ? (
                  <div className="prescription">
                    <div className="rx-title">
                      <strong>{prescription.doseLabel || "Selected dose"}</strong>
                      <span>Active prescription</span>
                    </div>
                    <p className="muted">{prescription.id}</p>
                    {prescription.items.map((item, index) => (
                      <div
                        className="rx-row"
                        key={`${item.productId}-${index}`}
                      >
                        <strong>{productName(item.productId)}</strong>
                        <b>× {item.quantity}</b>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state">
                    {!connected
                      ? "The medicine service is unavailable."
                      : !prescriptionReady
                      ? "Patient and prescription records are not connected yet. You can still detect pills from a photo."
                      : patients.length === 0
                      ? "No patients are available."
                      : "Select a patient to view their active prescription."}
                  </div>
                )}
              </section>

              <section className="card">
                <div className="step">02 · TRAY PHOTO</div>
                <h2>Add the prepared tray</h2>

                <label className={`upload ${photo ? "has-photo" : ""}`}>
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    aria-label="Upload medicine tray photo"
                    onChange={loadPhoto}
                    disabled={busy}
                  />
                  {photo ? (
                    <img src={photo} alt="Prepared medicine tray" />
                  ) : (
                    <>
                      <span className="upload-icon">＋</span>
                      <strong>Choose a tray photo</strong>
                      <span>JPG, PNG or WebP · up to 5 MB</span>
                    </>
                  )}
                </label>

                {fileName && (
                  <p className="muted filename">
                    {fileName} · Click the image to replace it
                  </p>
                )}

                <p className="muted">
                  Keep every pill visible, separated and in focus.
                </p>

                <button
                  type="button"
                  className="primary"
                  onClick={detectPhoto}
                  disabled={!canDetect}
                >
                  {operation === "detecting" ? "Detecting pills…" : "Detect pills"}
                </button>

                <p className="muted">
                  {!connected
                    ? "Start the Python service and refresh this page."
                    : !modelReady
                    ? "The recognition model is unavailable."
                    : operation === "reading"
                    ? "Reading the selected photo…"
                    : !photo
                    ? "Add a photo to detect pills."
                    : "Recognition currently supports MEDISEG Hong Kong products. All predictions require manual review."}
                </p>

                <button
                  type="button"
                  className="primary"
                  onClick={verifyTray}
                  disabled={!canVerify}
                >
                  {operation === "verifying"
                    ? "Verifying tray…"
                    : "Verify against prescription"}
                </button>

                <p className="muted">
                  {!prescriptionReady
                    ? "Prescription comparison will be available when patient records are connected."
                    : !prescription
                    ? "Select a patient with an active prescription."
                    : "Compares the detected products and quantities with the selected prescription."}
                </p>
              </section>
            </div>

            <section className="card result" aria-live="polite" aria-busy={busy}>
              <div className="step">03 · PILL RECOGNITION</div>

              {!recognition ? (
                <>
                  <h2>
                    {operation === "detecting"
                      ? "Analysing the photo…"
                      : "No photo analysed yet"}
                  </h2>
                  <p className="muted">
                    Upload a tray photo and choose Detect pills.
                  </p>
                </>
              ) : (
                <>
                  <h2>
                    {recognition.detections.length} model detections
                  </h2>
                  <p className="caution">
                    Review every prediction against the actual medicines.
                    Detection count is not a verified pill count.
                    No prescription comparison has been performed.
                  </p>

                  <img
                    src={recognition.annotatedImage}
                    alt="Model predictions with pill boxes and labels"
                    style={{
                      display: "block",
                      width: "100%",
                      maxHeight: "520px",
                      objectFit: "contain",
                      borderRadius: "10px",
                      background: "#f4f7f8",
                    }}
                  />

                  {recognition.detections.length === 0 ? (
                    <p className="muted">
                      No detections were returned. This does not confirm that
                      the tray is empty.
                    </p>
                  ) : (
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Detection</th>
                            <th>Predicted product</th>
                            <th>Model confidence</th>
                            <th>Review</th>
                          </tr>
                        </thead>
                        <tbody>
                          {recognition.detections.map((item, index) => (
                            <tr key={`${item.label}-${index}`}>
                              <td>{index + 1}</td>
                              <td>
                                {productName(item.label)}
                                {item.unmapped && (
                                  <p className="muted">
                                    No specific product identified
                                  </p>
                                )}
                              </td>
                              <td>
                                {(item.confidence * 100).toFixed(1)}%
                              </td>
                              <td>Manual review required</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  <p className="muted">
                    Confidence is the model score, not a guarantee that the
                    medicine or strength is correct.
                  </p>
                </>
              )}
            </section>

            {result && (
              <section className="card result" aria-live="polite">
                <div className="step">04 · PRESCRIPTION COMPARISON</div>
                <h2>{result.status}</h2>
                <p>{result.notes}</p>

                {result.uncertain.length > 0 && (
                  <p className="caution">
                    Counts exclude uncertain detections. Review the whole tray.
                  </p>
                )}

                {result.status === "Potential swap" && (
                  <p className="caution">
                    Missing and extra medicines were found together.
                    This does not establish which medicine replaced another.
                  </p>
                )}

                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Medicine</th>
                        <th>Expected</th>
                        <th>Identified</th>
                        <th>Difference</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.rows.map((row) => (
                        <tr key={row.productId}>
                          <td>{productName(row.productId)}</td>
                          <td>{row.expected}</td>
                          <td>{row.found}</td>
                          <td>
                            {row.found === row.expected
                              ? "Matches"
                              : row.found < row.expected
                              ? `${row.expected - row.found} missing`
                              : `${row.found - row.expected} extra`}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </>
        )}

        <footer>
          Review medicine predictions manually before administration.
        </footer>
      </main>
    </div>
  );
}