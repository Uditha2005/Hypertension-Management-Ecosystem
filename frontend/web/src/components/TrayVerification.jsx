import React, { useEffect, useRef, useState } from "react";
import "./TrayVerification.css";
import "./TrayReview.css";

const API = (
  process.env.REACT_APP_API_URL || "http://localhost:8000"
).replace(/\/$/, "");

function resultTone(status) {
  if (status === "Counts match — review required") return "match";
  if (status === "Count differences — review required") return "difference";
  return "uncertain";
}

async function request(path, options = {}) {
  const response = await fetch(`${API}/api/medicine${path}`, options);
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(`The medicine service returned an unreadable response (HTTP ${response.status}).`);
  }

  if (!response.ok) {
    throw new Error(
      typeof data?.error === "string"
        ? data.error
        : typeof data?.detail === "string"
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
  const prescriptionReader = useRef(null);
  const ocrController = useRef(null);
  const [page, setPage] = useState("verify");
  const [products, setProducts] = useState([]);
  const [prescription, setPrescription] = useState(null);
  const [modelReady, setModelReady] = useState(false);
  const [comparisonReady, setComparisonReady] = useState(false);
  const [connected, setConnected] = useState(false);

  const [photo, setPhoto] = useState("");
  const [fileName, setFileName] = useState("");
  const [recognition, setRecognition] = useState(null);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [prescriptionPhoto, setPrescriptionPhoto] = useState("");
  const [prescriptionFileName, setPrescriptionFileName] = useState("");
  const [ocrResult, setOcrResult] = useState(null);
  const [prescriptionText, setPrescriptionText] = useState("");
  const [ocrError, setOcrError] = useState("");

  const [loading, setLoading] = useState(true);
  const [operation, setOperation] = useState("");
  const [error, setError] = useState("");

  const nextRowId = useRef(2);
  const [draftRows, setDraftRows] = useState([
    { rowId: 1, medicineName: "", strength: "", quantity: "", productId: "" },
  ]);
  const [reviewed, setReviewed] = useState(false);
  const [reference, setReference] = useState("");
  const [doseLabel, setDoseLabel] = useState("Prepared tray");
  const busy = operation !== "";

  function invalidateReview() {
    setPrescription(null);
    setReviewed(false);
    setResult(null);
  }

  function emptyRow() {
    return { rowId: nextRowId.current++, medicineName: "", strength: "", quantity: "", productId: "" };
  }

  function updateRow(rowId, field, value) {
    invalidateReview();
    setDraftRows((rows) => rows.map((row) => row.rowId === rowId
      ? { ...row, [field]: value,
          ...(["medicineName", "strength"].includes(field) ? { productId: "", suggestions: [], matchType: "unresolved" } : {}) }
      : row));
  }

  async function rowsFromText(text, withinOcr = false) {
    const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    if (lines.length > 50) {
      setOcrError("Use at most 50 medicine rows. Review the extracted text first.");
      return;
    }
    invalidateReview();
    if (!withinOcr) setOperation("autofill");
    setOcrError("");
    try {
      const data = await request("/prescription/draft", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!mounted.current) return;
      if (!Array.isArray(data?.rows) || data.rows.length > 50 || data.rows.some((row) =>
          typeof row.medicineName !== "string" || typeof row.strength !== "string" ||
          typeof row.productId !== "string" || !Array.isArray(row.suggestions) ||
          (row.quantity !== null && (!Number.isInteger(row.quantity) || row.quantity < 1 || row.quantity > 100)))) {
        throw new Error("Invalid automatic draft response.");
      }
      setDraftRows(data.rows.length ? data.rows.map((row) => ({ ...emptyRow(), ...row,
        quantity: row.quantity ?? "" })) : [emptyRow()]);
    } catch (err) {
      if (mounted.current) {
        setDraftRows(lines.length ? lines.map((line) => ({ ...emptyRow(), medicineName: line })) : [emptyRow()]);
        setOcrError("Auto-fill unavailable. OCR text was copied into editable rows. " + err.message);
      }
    } finally {
      if (!withinOcr && mounted.current) setOperation("");
    }
  }

  const draftValid = draftRows.length > 0 && draftRows.length <= 50 && doseLabel.trim() &&
    draftRows.every((row) => row.medicineName.trim() && Number.isInteger(Number(row.quantity)) &&
      Number(row.quantity) >= 1 && Number(row.quantity) <= 100);
  const mappedIds = draftRows.map((row) => row.productId).filter(Boolean);
  const duplicateProducts = new Set(mappedIds).size !== mappedIds.length;

  async function confirmPrescription() {
    if (!connected || !comparisonReady || !draftValid || duplicateProducts || !reviewed || busy) return;
    setOperation("saving-prescription");
    setError("");
    setPrescription(null);
    setResult(null);
    try {
      const data = await request("/prescription/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reference: reference.trim(), doseLabel: doseLabel.trim(), reviewed: true,
          items: draftRows.map((row) => ({ medicineName: row.medicineName.trim(), strength: row.strength.trim(),
            quantity: Number(row.quantity), productId: row.productId })) }),
      });
      if (!mounted.current) return;
      if (!data || typeof data.id !== "string" || !Array.isArray(data.items) || data.reviewed !== true) {
        throw new Error("The service returned an invalid reviewed prescription.");
      }
      setPrescription(data);
    } catch (err) {
      if (mounted.current) setError(err instanceof TypeError ? "Cannot reach the medicine API." : err.message);
    } finally {
      if (mounted.current) setOperation("");
    }
  }

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
        setComparisonReady(data.reviewedComparisonReady === true);
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
      prescriptionReader.current?.abort();
      ocrController.current?.abort();
    };
  }, []);

  function productName(id) {
    const product = products.find((item) => item.id === id);
    return product
      ? [product.name, product.strength].filter(Boolean).join(" · ")
      : id || "Unidentified medicine";
  }

  function loadPrescriptionPhoto(event) {
    const file = event.target.files?.[0];
    if (!file || busy) return;
    event.target.value = "";
    invalidateReview();
    setDraftRows([emptyRow()]);
    setPrescriptionPhoto("");
    setPrescriptionFileName("");
    setOcrResult(null);
    setPrescriptionText("");
    setOcrError("");

    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) ||
        file.size === 0 || file.size > 5 * 1024 * 1024) {
      setOcrError("Choose a non-empty JPG, PNG or WebP prescription image up to 5 MB.");
      return;
    }

    setOperation("reading-prescription");
    const reader = new FileReader();
    prescriptionReader.current = reader;
    reader.onload = () => {
      if (!mounted.current) return;
      setPrescriptionPhoto(String(reader.result));
      setPrescriptionFileName(file.name);
      setOperation("");
      prescriptionReader.current = null;
    };
    reader.onerror = () => {
      if (!mounted.current) return;
      setOcrError("Could not read the prescription image. Select it again.");
      setOperation("");
      prescriptionReader.current = null;
    };
    reader.readAsDataURL(file);
  }

  async function readPrescription() {
    if (!prescriptionPhoto || busy) return;
    invalidateReview();
    setOperation("ocr");
    setOcrError("");
    const controller = new AbortController();
    ocrController.current = controller;
    const timeout = setTimeout(() => controller.abort(), 120000);

    try {
      const data = await request("/prescription/ocr", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ imageData: prescriptionPhoto }),
        signal: controller.signal,
      });
      if (!mounted.current) return;
      if (!data || typeof data.text !== "string" || !Array.isArray(data.blocks)) {
        throw new Error("The service returned an invalid prescription OCR result.");
      }
      setOcrResult(data);
      setPrescriptionText(data.text);
      await rowsFromText(data.text, true);
      if (!data.text.trim()) {
        setOcrError("No text was extracted. Try a clearer image or type the text below.");
      }
    } catch (err) {
      if (mounted.current) {
        setOcrError(err.name === "AbortError"
          ? "Reading the prescription timed out. Try again."
          : err instanceof TypeError
          ? "Cannot reach the prescription OCR service. Check the Python API on port 8000."
          : err.message);
      }
    } finally {
      clearTimeout(timeout);
      if (ocrController.current === controller) ocrController.current = null;
      if (mounted.current) setOperation("");
    }
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
    if (!connected || !modelReady || !comparisonReady || !prescription?.comparisonReady || !photo || busy) return;
    const prescriptionId = prescription.id;
    setOperation("verifying");
    setError("");
    setResult(null);
    try {
      const data = await request("/verify-reviewed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prescriptionId, imageData: photo }),
      });
      if (!mounted.current) return;
      if (!data || data.mode !== "live" || data.prescription?.id !== prescriptionId ||
          !Array.isArray(data.rows) || !Array.isArray(data.uncertain) ||
          !Array.isArray(data.recognition?.detections) ||
          !data.recognition.detections.every(validDetection) ||
          typeof data.recognition.annotatedImage !== "string" ||
          !data.recognition.annotatedImage.startsWith("data:image/jpeg;base64,")) {
        throw new Error("The service returned an invalid comparison result.");
      }
      setRecognition(data.recognition);
      setResult(data);
      const record = { ...data };
      delete record.recognition;
      setHistory((previous) => [record, ...previous].slice(0, 200));
    } catch (err) {
      if (mounted.current) setError(err instanceof TypeError ? "Cannot reach the medicine API." : err.message);
    } finally {
      if (mounted.current) setOperation("");
    }
  }

  const canDetect = connected && modelReady && photo && !busy;
  const canVerify =
    canDetect && comparisonReady && prescription?.comparisonReady === true;

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
                      <th>Tray reference</th>
                      <th>Date and time</th>
                      <th>Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((record) => (
                      <tr key={record.id}>
                        <td>{record.reference || record.prescription?.doseLabel || "Prepared tray"}</td>
                        <td>{new Date(record.createdAt).toLocaleString()}</td>
                        <td><span className={`tray-status ${resultTone(record.status)}`}>{record.status}</span></td>
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
                <div className="step">01 · REVIEW PRESCRIPTION</div>
                <h2>Review the tray medicine list</h2>

                <label className={`upload ${prescriptionPhoto ? "has-photo" : ""}`}>
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    aria-label="Upload prescription photo"
                    onChange={loadPrescriptionPhoto}
                    disabled={busy}
                  />
                  {prescriptionPhoto ? (
                    <img src={prescriptionPhoto} alt="Uploaded prescription" />
                  ) : (
                    <>
                      <span className="upload-icon">＋</span>
                      <strong>Choose a prescription photo</strong>
                      <span>JPG, PNG or WebP · up to 5 MB</span>
                    </>
                  )}
                </label>
                {prescriptionFileName && (
                  <p className="muted filename">{prescriptionFileName} · Click the image to replace it</p>
                )}
                <button
                  type="button"
                  className="primary"
                  onClick={readPrescription}
                  disabled={!prescriptionPhoto || busy}
                >
                  {operation === "ocr" ? "Reading prescription…" : "Read prescription"}
                </button>
                {operation === "reading-prescription" && <p role="status">Loading prescription photo…</p>}
                {operation === "ocr" && <p className="muted" role="status">Extracting prescription text…</p>}
                {ocrError && <p className="error" role="alert">{ocrError}</p>}
                {ocrResult && (
                  <div style={{ marginTop: 18 }}>
                    <label htmlFor="prescription-ocr-text">Review and edit prescription text</label>
                    <textarea
                      id="prescription-ocr-text"
                      value={prescriptionText}
                      onChange={(event) => { setPrescriptionText(event.target.value); invalidateReview(); }}
                      disabled={busy}
                      rows={8}
                      spellCheck={false}
                      aria-describedby="prescription-draft-note"
                      style={{ width: "100%", boxSizing: "border-box", padding: 12,
                        border: "1px solid #cbd5e1", borderRadius: 10, font: "inherit",
                        lineHeight: 1.6, resize: "vertical" }}
                    />
                    <p className="muted">Check each medicine name, strength and instruction against the photo. Reading again replaces your edits.</p>
                    <button type="button" className="primary" disabled={busy}
                      onClick={() => rowsFromText(prescriptionText)}>
                      {operation === "autofill" ? "Preparing draft…" : "Auto-fill from edited text"}
                    </button>
                    <p className="muted">Refresh the rows after editing OCR text. Existing row edits will be replaced.</p>
                    <details>
                      <summary>OCR candidate lines ({ocrResult.blocks.length})</summary>
                      <div className="table-wrap">
                        <table>
                          <thead><tr><th>Extracted text</th><th>Confidence</th></tr></thead>
                          <tbody>
                            {ocrResult.blocks.map((block, index) => (
                              <tr key={index}>
                                <td>{typeof block?.text === "string" ? block.text : ""}</td>
                                <td>{Number.isFinite(block?.confidence) && block.confidence >= 0 && block.confidence <= 1
                                  ? `${(block.confidence * 100).toFixed(1)}%` : "Unavailable"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </details>
                  </div>
                )}
                <p className="muted" id="prescription-draft-note">
                  OCR text is a draft. Check the original prescription and fill in each row below before saving.
                </p>
                <div className="review-form">
                  <div className="review-heading"><div><span className="review-kicker">REVIEW BEFORE COMPARING</span>
                    <h3>Your tray medicine list</h3></div><span className="review-count">{draftRows.length} rows</span></div>
                  <div className="review-overview">
                    <span><b>{draftRows.filter((row) => row.productId).length}</b> products selected</span>
                    <span><b>{draftRows.filter((row) => !row.quantity).length}</b> quantities to review</span>
                  </div>
                  <p className="muted">Names and clear strengths are filled from OCR. Review the original prescription. Quantity means pills for this tray; daily schedules and supply totals are not used.</p>
                  <label htmlFor="review-reference">Tray label / patient reference (optional)</label>
                  <input id="review-reference" value={reference} maxLength={200} disabled={busy}
                    onChange={(event) => { setReference(event.target.value); invalidateReview(); }} />
                  <label htmlFor="review-dose">Dose or tray label</label>
                  <input id="review-dose" value={doseLabel} maxLength={200} disabled={busy}
                    onChange={(event) => { setDoseLabel(event.target.value); invalidateReview(); }} />
                  {draftRows.map((row, index) => (
                    <div key={row.rowId} className="review-medicine">
                      <div className="review-row-heading"><strong><span className="review-number">{index + 1}</span>Medicine {index + 1}</strong>
                        <span className={`review-badge ${row.productId ? "mapped" : "pending"}`}>{row.productId ? "Product selected" : "Needs review"}</span></div>
                      {row.sourceText && <details className="review-source"><summary>Original OCR line</summary><p>{row.sourceText}</p></details>}
                      <label htmlFor={`name-${row.rowId}`}>Reviewed medicine name</label>
                      <input id={`name-${row.rowId}`} value={row.medicineName} maxLength={200} disabled={busy}
                        onChange={(event) => updateRow(row.rowId, "medicineName", event.target.value)} />
                      <div className="review-pair"><div><label htmlFor={`strength-${row.rowId}`}>Strength from prescription (optional)</label>
                      <input id={`strength-${row.rowId}`} value={row.strength} maxLength={80} disabled={busy}
                        onChange={(event) => updateRow(row.rowId, "strength", event.target.value)} /></div>
                      <div><label htmlFor={`quantity-${row.rowId}`}>Pill quantity for this tray</label>
                      <input id={`quantity-${row.rowId}`} type="number" min="1" max="100" step="1" value={row.quantity} disabled={busy}
                        onChange={(event) => updateRow(row.rowId, "quantity", event.target.value)} /></div></div>
                      <label htmlFor={`product-${row.rowId}`}>Exact product supported by pill model</label>
                      <select id={`product-${row.rowId}`} value={row.productId} disabled={busy || !connected}
                        onChange={(event) => updateRow(row.rowId, "productId", event.target.value)}>
                        <option value="">Unsupported / exact product not known</option>
                        {products.map((product) => <option key={product.id} value={product.id}>{product.name} · {product.id}</option>)}
                      </select>
                      {!row.productId && row.suggestions?.length > 0 && <div className="review-suggestions">
                        <span>Similar names to review · suggestions are not confirmed matches</span>
                        {row.suggestions.map((suggestion) => <button type="button" className="review-suggestion" key={suggestion.productId} disabled={busy}
                          onClick={() => updateRow(row.rowId, "productId", suggestion.productId)}>{suggestion.name} · {suggestion.productId}</button>)}
                      </div>}
                      {row.matchType === "exact-text" && row.productId && <p className="review-hint">Exact text match suggested automatically. Confirm the actual product against its packaging.</p>}
                      {!row.quantity && <p className="review-hint">Tray quantity was not explicit in the text. Enter it from the reviewed dose.</p>}
                      {!row.productId && <p className="muted">This row cannot be compared until its exact product is supported. Do not select a similar-looking pill or a different brand.</p>}
                      <button type="button" className="review-danger" disabled={busy}
                        onClick={() => { invalidateReview(); setDraftRows((rows) => rows.filter((item) => item.rowId !== row.rowId)); }}>
                        Remove row
                      </button>
                    </div>
                  ))}
                  <button type="button" className="review-secondary" disabled={busy || draftRows.length >= 50}
                    onClick={() => { invalidateReview(); setDraftRows((rows) => [...rows, emptyRow()]); }}>
                    Add medicine row
                  </button>
                  {duplicateProducts && <p className="error" role="alert">Combine duplicate products into one row with the total quantity for this tray.</p>}
                  <label className="review-confirm">
                    <input type="checkbox" checked={reviewed} disabled={busy}
                        onChange={(event) => { setReviewed(event.target.checked); setPrescription(null); setResult(null); }} />
                    <span>I checked every row against the original prescription. Any selected model class is the exact product, and quantities apply to this tray.</span>
                  </label>
                  <button type="button" className="primary" onClick={confirmPrescription}
                    disabled={busy || !connected || !comparisonReady || !draftValid || duplicateProducts || !reviewed}>
                    {operation === "saving-prescription" ? "Saving reviewed list…" : "Confirm and save reviewed list"}
                  </button>
                  {!comparisonReady && <p className="muted">Restart the API with the updated comparison files to save the reviewed list.</p>}
                  {prescription && <p role="status" className={`review-saved ${prescription.comparisonReady ? "ready" : "blocked"}`}>
                    Reviewed list saved: {prescription.id}. {prescription.comparisonReady
                      ? "Ready for model label and quantity comparison."
                      : "Comparison blocked: one or more medicines are unsupported."}
                  </p>}
                  <p className="review-footnote">Saving records your review; it does not create a doctor-approved prescription. Strength, timing and clinical suitability are not checked by the pill model.</p>
                </div>
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
                  {!prescription
                    ? "Review and save the medicine list before comparing."
                    : !prescription.comparisonReady
                    ? "Comparison blocked because the reviewed list contains unsupported medicines."
                    : "Compares trained product labels and tray quantities. Manual review is still required."}
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
                    {result ? "Comparison results appear below." : "No prescription comparison has been performed."}
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
              <section className={`card result comparison-result ${resultTone(result.status)}`} aria-live="polite">
                <div className="step">04 · PRESCRIPTION COMPARISON</div>
                <h2 className="comparison-title"><span className={`tray-status ${resultTone(result.status)}`}>{result.status}</span></h2>
                <p className="comparison-note">{result.notes}</p>
                <div className="comparison-summary">
                  <span><strong>{result.rows.reduce((total, row) => total + row.expected, 0)}</strong>Expected pills</span>
                  <span><strong>{result.rows.reduce((total, row) => total + row.found, 0)}</strong>Counted model detections</span>
                  <span><strong>{result.rows.filter((row) => row.expected !== row.found).length}</strong>Rows with differences</span>
                </div>

                {result.uncertain.length > 0 && (
                  <p className="caution">
                    Counts exclude uncertain detections. Differences are inconclusive; review the whole tray.
                  </p>
                )}

                {result.uncertain.length > 0 && (
                  <ul>{result.uncertain.map((item, index) => (
                    <li key={index}>{productName(item.label)} · {(item.confidence * 100).toFixed(1)}% · {item.reason}</li>
                  ))}</ul>
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
                        <tr key={row.productId} className={`comparison-row ${row.expected !== row.found ? "difference" : result.uncertain.length > 0 ? "uncertain" : "match"}`}>
                          <td>{row.medicineName || productName(row.productId)}<p className="muted">{productName(row.productId)}{row.strength ? ` · Recorded strength: ${row.strength} (not verified)` : ""}</p></td>
                          <td>{row.expected}</td>
                          <td>{row.found}</td>
                          <td>
                            <span className={`tray-status ${row.expected !== row.found ? "difference" : result.uncertain.length > 0 ? "uncertain" : "match"}`}>
                            {row.found === row.expected
                              ? (result.uncertain.length > 0 ? "Counts equal · review" : "Counts match")
                              : row.found < row.expected
                              ? `${row.expected - row.found} missing`
                              : `${row.found - row.expected} extra`}
                            </span>
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
