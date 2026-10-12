import React, { useEffect, useState } from "react";
import "./TrayVerification.css";

const API = process.env.REACT_APP_API_URL || "http://localhost:8000";

async function request(path, options) {
  const response = await fetch(`${API}/api/medicine${path}`, options);
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || data.detail || "Request failed");
  }

  return data;
}

export default function TrayVerification() {
  const [page, setPage] = useState("verify");
  const [patients, setPatients] = useState([]);
  const [products, setProducts] = useState([]);
  const [patientId, setPatientId] = useState("");
  const [prescription, setPrescription] = useState(null);
  const [modelReady, setModelReady] = useState(false);
  const [connected, setConnected] = useState(false);

  const [photo, setPhoto] = useState("");
  const [fileName, setFileName] = useState("");
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);

  const [loading, setLoading] = useState(true);
  const [loadingPrescription, setLoadingPrescription] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      try {
        const data = await request("/bootstrap");
        if (cancelled) return;

        // Never display synthetic patients as real patient records.
        if (data.mode !== "live") {
          setConnected(false);
          return;
        }

        setConnected(true);
        setPatients(data.patients || []);
        setProducts(data.products || []);
        setModelReady(data.modelReady === true);

        const records = await request("/history");

        if (!cancelled) {
          setHistory(records.filter((record) => record.mode === "live"));
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadData();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setPrescription(null);
    setResult(null);

    if (!patientId) {
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
  }, [patientId]);

  function getProduct(id) {
    return products.find((product) => product.id === id);
  }

  function productName(id) {
    const product = getProduct(id);

    if (!product) return id || "Unidentified medicine";

    return [product.name, product.strength].filter(Boolean).join(" · ");
  }

  function changePatient(event) {
    setPatientId(event.target.value);
    setPrescription(null);
    setResult(null);
    setPhoto("");
    setFileName("");
    setError("");
  }

  function loadPhoto(event) {
    const file = event.target.files?.[0];

    setPhoto("");
    setFileName("");
    setResult(null);
    setError("");

    if (!file) return;

    const allowed = ["image/jpeg", "image/png", "image/webp"];

    if (!allowed.includes(file.type) || file.size > 5 * 1024 * 1024) {
      setError("Choose a JPG, PNG or WebP image smaller than 5 MB.");
      event.target.value = "";
      return;
    }

    setBusy(true);

    const reader = new FileReader();

    reader.onload = () => {
      setPhoto(reader.result);
      setFileName(file.name);
      setBusy(false);
    };

    reader.onerror = () => {
      setError("Could not read the image. Please select it again.");
      setBusy(false);
    };

    reader.readAsDataURL(file);
  }

  async function verifyTray() {
    if (!connected || !modelReady || !prescription || !photo || busy) {
      return;
    }

    setBusy(true);
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

      // Accept only actual inference results for the selected prescription.
      if (
        data.mode !== "live" ||
        data.patientId !== patientId ||
        data.prescription?.id !== prescription.id ||
        !Array.isArray(data.rows) ||
        !Array.isArray(data.uncertain)
      ) {
        throw new Error("The service did not return a valid verification result.");
      }

      setResult(data);
      setHistory((previous) => [data, ...previous].slice(0, 200));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const canVerify =
    connected && modelReady && prescription && photo && !busy;

  return (
    <div className="tray-app">
      <aside className="tray-sidebar">
        <div className="tray-logo">
          H<span>+</span>
        </div>

        <h2>Hypertension Care</h2>
        <p>Medicine verification</p>

        <nav aria-label="Medicine verification">
          <button
            className={page === "verify" ? "active" : ""}
            onClick={() => setPage("verify")}
          >
            Verify tray
          </button>

          <button
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
              Review the prepared medicines against the patient's active
              prescription.
            </p>
          </div>
        </header>

        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}

        {loading ? (
          <p role="status">Loading medicine verification…</p>
        ) : page === "history" ? (
          <section className="card">
            <h2>Previous verifications</h2>

            {history.length === 0 ? (
              <div className="empty-state">
                No verification records available.
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
                        <td>
                          {new Date(record.createdAt).toLocaleString()}
                        </td>
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

                <label htmlFor="patient">Select patient</label>
                <select
                  id="patient"
                  value={patientId}
                  onChange={changePatient}
                  disabled={busy || !connected || patients.length === 0}
                >
                  <option value="">Choose a patient</option>

                  {patients.map((patient) => (
                    <option key={patient.id} value={patient.id}>
                      {patient.name} · {patient.id}
                    </option>
                  ))}
                </select>

                {loadingPrescription ? (
                  <p className="muted" role="status">
                    Loading prescription…
                  </p>
                ) : prescription ? (
                  <div className="prescription">
                    <div className="rx-title">
                      <strong>
                        {prescription.doseLabel || "Selected dose"}
                      </strong>
                      <span>Active prescription</span>
                    </div>

                    <p className="muted">{prescription.id}</p>

                    {prescription.items.map((item, index) => (
                      <div
                        className="rx-row"
                        key={`${item.productId}-${index}`}
                      >
                        <div>
                          <strong>{productName(item.productId)}</strong>
                          <p>
                            {[
                              getProduct(item.productId)?.brand,
                              getProduct(item.productId)?.formulation,
                            ]
                              .filter(Boolean)
                              .join(" · ")}
                          </p>
                        </div>
                        <b>× {item.quantity}</b>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state">
                    {!connected
                      ? "Patient records are not connected yet."
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
                    key={patientId}
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
                  className="primary"
                  onClick={verifyTray}
                  disabled={!canVerify}
                  aria-describedby="verification-help"
                >
                  {busy ? "Processing…" : "Verify tray"}
                </button>

                <p id="verification-help" className="muted">
                  {!connected
                    ? "Verification will be available when patient records and the recognition service are connected."
                    : !modelReady
                    ? "Medicine recognition is currently unavailable."
                    : !prescription
                    ? "Select a patient with an active prescription."
                    : !photo
                    ? "Add a tray photo to continue."
                    : "Ready to check the prepared tray."}
                </p>
              </section>
            </div>

            <section className="card result" aria-live="polite">
              <div className="step">03 · VERIFICATION RESULT</div>

              {!result ? (
                <>
                  <h2>No verification performed yet</h2>
                  <p className="muted">
                    The comparison will appear here after the tray is analysed.
                  </p>
                </>
              ) : (
                <>
                  <h2>{result.status}</h2>
                  <p>{result.notes}</p>

                  {result.uncertain.length > 0 && (
                    <p className="caution">
                      Some medicines could not be identified confidently.
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
                </>
              )}
            </section>
          </>
        )}

        <footer>
          Review uncertain medicines manually before administration.
        </footer>
      </main>
    </div>
  );
}