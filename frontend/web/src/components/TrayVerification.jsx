import React, { useEffect, useRef, useState } from "react";
import "./TrayVerification.css";
import MedicineSafety, { prepareMedicineAudio } from "./MedicineSafety";

const API = (
  process.env.REACT_APP_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

const TRAY_SCOPE = "single-dose";
const TRAY_LABEL = "One-dose tray";
const DEFAULT_REVIEW_THRESHOLD = 0.60;

const STATUS_STYLES = {
  match: {
    color: "#216337",
    backgroundColor: "#e6f4e9",
    border: "1px solid #bfdcc7",
  },
  warning: {
    color: "#815914",
    backgroundColor: "#fff3d9",
    border: "1px solid #ead29e",
  },
  difference: {
    color: "#a23c30",
    backgroundColor: "#fde8e4",
    border: "1px solid #eac0b8",
  },
};

function Icon({ name, size = 18 }) {
  const paths = {
    upload:
      "M12 16V4m0 0l-4 4m4-4l4 4M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3",
    check: "M5 12.5l4.5 4.5L19 7.5",
    alert:
      "M12 8v5m0 3.5h.01M10.3 4.2L2.6 17.5A2 2 0 004.3 20.5h15.4a2 2 0 001.7-3L13.7 4.2a2 2 0 00-3.4 0z",
    pill:
      "M10.5 20.5a5 5 0 01-7-7l10-10a5 5 0 017 7l-10 10zM8.5 8.5l7 7",
    info: "M12 11v5m0-8.5h.01M12 21a9 9 0 100-18 9 9 0 000 18z",
  };

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name] || paths.info} />
    </svg>
  );
}

function StatusChip({ tone = "match", children }) {
  return (
    <span
      className={`av-chip ${tone}`}
      style={{
        ...STATUS_STYLES[tone],
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
      }}
    >
      {children}
    </span>
  );
}

function quantityValid(value) {
  return (
    String(value ?? "").trim() !== "" &&
    Number.isInteger(Number(value)) &&
    Number(value) >= 1 &&
    Number(value) <= 100
  );
}

function identity(name = "", strength = "") {
  const text = `${name} ${strength}`
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[µμ]g/g, "mcg")
    .replace(/_/g, " ");

  const pattern =
    /(?<![\w./-])(\d+(?:\.\d+)?)\s*(mcg|ug|mg|g|ml|iu|%)(?![a-z])/g;

  const strengths = [
    ...new Set(
      Array.from(text.matchAll(pattern), (match) =>
        `${Number(match[1])}${match[2] === "ug" ? "mcg" : match[2]}`
      )
    ),
  ].sort();

  return {
    name: text
      .replace(pattern, " ")
      .replace(/\b(?:tablets?|tabs?|capsules?|caps?)\b/g, " ")
      .replace(/[^a-z0-9]+/g, " ")
      .trim(),
    strength: strengths.join("|"),
    complex: /[+/]/.test(text),
  };
}

function exactProduct(row, products) {
  const wanted = identity(row.medicineName, row.strength);

  if (!wanted.name || !wanted.strength || wanted.complex) return "";

  const matches = products.filter((product) => {
    const candidate = identity(product.name, product.strength || "");

    return (
      !candidate.complex &&
      candidate.name === wanted.name &&
      candidate.strength === wanted.strength
    );
  });

  return matches.length === 1 ? matches[0].id : "";
}

function validRecognition(data) {
  return (
    data &&
    typeof data.annotatedImage === "string" &&
    data.annotatedImage.startsWith("data:image/jpeg;base64,") &&
    Array.isArray(data.detections) &&
    data.detections.every(
      (item) =>
        typeof item?.label === "string" &&
        Number.isFinite(item.confidence) &&
        item.confidence >= 0 &&
        item.confidence <= 1 &&
        Array.isArray(item.bbox) &&
        item.bbox.length === 4 &&
        item.bbox.every(Number.isFinite) &&
        item.bbox[2] > item.bbox[0] &&
        item.bbox[3] > item.bbox[1]
    )
  );
}

function comparisonTone(record) {
  if (record?.comparisonType === "total-count") {
    if (record.lowConfidenceCount > 0) return "warning";
    return record.difference === 0 ? "match" : "difference";
  }

  if (record?.uncertain?.length) return "warning";

  if (record?.rows?.some((row) => row.expected !== row.found)) {
    return "difference";
  }

  return "match";
}

function rowReview(row, result) {
  const relevant = (result.uncertain || []).filter(
    (item) =>
      item.label === row.productId ||
      item.productId === row.productId ||
      item.alternatives?.some(
        (alternative) => alternative.label === row.productId
      )
  );

  const difference = row.found - row.expected;

  // A definite surplus remains a count difference.
  // Otherwise, uncertainty affects only its related product row.
  const tone =
    difference > 0
      ? "difference"
      : relevant.length
      ? "warning"
      : difference < 0
      ? "difference"
      : "match";

  return { tone, relevant, difference };
}

function predictionTone(item, threshold) {
  if (item.referenceMode) return item.referenceAssigned ? "match" : "warning";
  return (
    item.unmapped ||
    item.identityUncertain ||
    item.confidence < threshold
  )
    ? "warning"
    : "match";
}

function PhotoInput({ title, image, filename, onChange, disabled }) {
  return (
    <label
      className={`av-drop ${image ? "has-image" : ""} ${
        disabled ? "disabled" : ""
      }`}
    >
      <input
        className="av-sr"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        aria-label={title}
        disabled={disabled}
        onChange={onChange}
      />
      {image ? (
        <img src={image} alt={title} />
      ) : (
        <span className="av-drop-icon">
          <Icon name="upload" size={26} />
        </span>
      )}
      <strong>{image ? "Click to replace photo" : title}</strong>
      <small>{filename || "JPG, PNG or WebP · maximum 5 MB"}</small>
    </label>
  );
}

function ComparisonResult({ result, productName }) {
  if (!result) return null;

  const totalOnly = result.comparisonType === "total-count";
  const tone = comparisonTone(result);
  const threshold = Number.isFinite(result.confidenceThreshold)
    ? result.confidenceThreshold
    : DEFAULT_REVIEW_THRESHOLD;

  return (
    <section className="av-card">
      <div className="av-card-head">
        <h2>
          {totalOnly ? "Total count comparison" : "Medicine count comparison"}
        </h2>
      </div>

      <div
        className={`av-banner ${tone === "match" ? "" : tone}`}
        style={STATUS_STYLES[tone]}
      >
        <Icon name={tone === "match" ? "check" : "alert"} size={22} />
        <div>
          <strong>{result.status}</strong>
          <small>{result.notes}</small>
        </div>
      </div>

      {totalOnly ? (
        <div className="av-metrics">
          <div>
            <strong>{result.expectedTotal}</strong>
            <small>Expected</small>
          </div>
          <div>
            <strong>{result.detectedTotal}</strong>
            <small>Detected objects</small>
          </div>
          <div className={result.lowConfidenceCount ? "warn" : ""}>
            <strong>{result.lowConfidenceCount}</strong>
            <small>Low-score detections included</small>
          </div>
        </div>
      ) : (
        <>
          <p className="av-muted">
            {result.usesReferenceLabels
              ? "Appearance-assisted labels use declared sample colours and relative sizes. Matching counts do not verify medicine identities."
              : `Counted predictions use a model-score threshold of ${(threshold * 100).toFixed(0)}%. Excluded predictions remain available for review.`}
          </p>

          <div className="av-table">
            <table>
              <thead>
                <tr>
                  <th>Medicine</th>
                  <th>Expected</th>
                  <th>Counted predictions</th>
                  <th>Difference</th>
                  <th>Review status</th>
                </tr>
              </thead>
              <tbody>
                {(result.rows || []).map((row, index) => {
                  const state = rowReview(row, result);

                  return (
                    <tr key={`${row.productId}-${index}`}>
                      <td>
                        <strong>
                          {row.medicineName || productName(row.productId)}
                        </strong>
                        {row.strength && (
                          <small style={{ display: "block" }}>
                            Recorded: {row.strength}
                          </small>
                        )}
                      </td>
                      <td>{row.expected}</td>
                      <td>
                        {row.found}
                        {!!state.relevant.length && (
                          <small
                            style={{
                              display: "block",
                              color: "#815914",
                              marginTop: 5,
                            }}
                          >
                            {state.relevant.length} uncertain prediction(s)
                            associated with this medicine; excluded.
                          </small>
                        )}
                      </td>
                      <td>
                        <StatusChip tone={state.tone}>
                          {state.difference > 0 ? "+" : ""}
                          {state.difference}
                        </StatusChip>
                      </td>
                      <td>
                        <StatusChip tone={state.tone}>
                          {state.tone === "match"
                            ? "Counts match"
                            : state.tone === "warning"
                            ? "Needs review"
                            : "Count difference"}
                        </StatusChip>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {!!result.uncertain?.length && (
            <div
              className="av-alert av-warning"
              style={{ marginTop: 16 }}
            >
              <Icon name="alert" />
              <div>
                <strong>Uncertain predictions excluded from counts</strong>
                <ul>
                  {result.uncertain.map((item, index) => {
                    const alternatives = [
                      ...new Set(
                        (item.alternatives || [])
                          .map((alternative) => alternative.label)
                          .filter(Boolean)
                      ),
                    ];

                    return (
                      <li key={index}>
                        {item.identityUncertain ||
                        item.label === "__uncertain__"
                          ? `Conflicting / ambiguous prediction${
                              alternatives.length
                                ? ": " +
                                  alternatives.map(productName).join(" / ")
                                : ""
                            }`
                          : productName(item.label)}
                        {Number.isFinite(item.confidence) &&
                          ` · model score ${(item.confidence * 100).toFixed(1)}%`}
                        {" · "}
                        {item.reason || "Review required"}
                      </li>
                    );
                  })}
                </ul>
              </div>
            </div>
          )}

          <p className="av-muted">
            Green: this product's counts match. Yellow: related predictions
            need review. Red: counted predictions differ from the expected
            quantity.
          </p>
        </>
      )}

      <p className="av-muted" style={{ marginTop: 14, marginBottom: 0 }}>
        Matching counts do not confirm medicine identity or clinical suitability.
      </p>
    </section>
  );
}

export default function TrayVerification() {
  const mounted = useRef(false);
  const controllers = useRef(new Set());
  const readers = useRef(new Set());
  const lock = useRef(false);
  const nextId = useRef(1);

  const [service, setService] = useState(null);
  const [loading, setLoading] = useState(true);
  const [operation, setOperation] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [page, setPage] = useState("workspace");
  const [step, setStep] = useState(0);
  const [history, setHistory] = useState([]);

  const [prescriptionPhoto, setPrescriptionPhoto] = useState("");
  const [prescriptionFilename, setPrescriptionFilename] = useState("");
  const [ocrResult, setOcrResult] = useState(null);
  const [text, setText] = useState("");
  const useLLM = true;
  const [rows, setRows] = useState([]);
  const [reference, setReference] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [saved, setSaved] = useState(null);
  const [extraction, setExtraction] = useState(null);

  const [photo, setPhoto] = useState("");
  const [filename, setFilename] = useState("");
  const [recognition, setRecognition] = useState(null);
  const [result, setResult] = useState(null);
  const [checkNumber, setCheckNumber] = useState(0);

  const busy = Boolean(operation);
  const products = Array.isArray(service?.products) ? service.products : [];
  const connected = service?.mode === "live";

  function productName(id) {
    if (id === "__uncertain__") return "Unidentified — conflicting predictions";
    return products.find((product) => product.id === id)?.name || id || "Unselected";
  }

  async function api(path, body) {
    const controller = new AbortController();
    controllers.current.add(controller);
    const timeout = setTimeout(() => controller.abort(), 120000);

    try {
      const response = await fetch(`${API}/api/medicine${path}`, {
        method: body === undefined ? "GET" : "POST",
        headers:
          body === undefined ? undefined : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });

      let data;
      try {
        data = await response.json();
      } catch {
        throw new Error(`Unreadable API response: HTTP ${response.status}.`);
      }

      if (!response.ok) {
        throw new Error(
          typeof data?.error === "string"
            ? data.error
            : typeof data?.detail === "string"
            ? data.detail
            : `Request failed: HTTP ${response.status}.`
        );
      }

      return data;
    } catch (err) {
      if (err.name === "AbortError") {
        throw new Error("The request timed out or was cancelled.");
      }
      if (err instanceof TypeError) {
        throw new Error(`Cannot reach the medicine API at ${API}.`);
      }
      throw err;
    } finally {
      clearTimeout(timeout);
      controllers.current.delete(controller);
    }
  }

  useEffect(() => {
    mounted.current = true;
    let cancelled = false;

    async function start() {
      try {
        const data = await api("/bootstrap");
        if (cancelled) return;

        if (data?.mode !== "live" || !Array.isArray(data.products)) {
          throw new Error("Invalid medicine service response.");
        }
        if (
          !data.products.every(
            (product) =>
              typeof product?.id === "string" &&
              typeof product.name === "string"
          )
        ) {
          throw new Error("Invalid medicine catalog.");
        }

        setService(data);

        try {
          const records = await api("/history");
          if (!cancelled && Array.isArray(records)) {
            setHistory(
              records.filter((record) => record?.mode === "live").slice(0, 200)
            );
          }
        } catch {
          if (!cancelled) {
            setNotice("Connected. Previous history could not be loaded.");
          }
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    start();

    return () => {
      cancelled = true;
      mounted.current = false;
      controllers.current.forEach((controller) => controller.abort());
      readers.current.forEach((reader) => {
        if (reader.readyState === 1) reader.abort();
      });
    };
  }, []);

  async function run(label, action) {
    if (lock.current || loading) return;

    lock.current = true;
    setOperation(label);
    setError("");
    setNotice("");

    try {
      await action();
    } catch (err) {
      if (mounted.current) {
        setError(err.message || "The operation failed.");
      }
    } finally {
      lock.current = false;
      if (mounted.current) setOperation("");
    }
  }

  function invalidate() {
    setReviewed(false);
    setSaved(null);
    setResult(null);
  }

  function normalizeRows(data) {
    if (
      !Array.isArray(data?.rows) ||
      !data.rows.length ||
      data.rows.length > 50
    ) {
      throw new Error("No valid medicine rows returned. Existing rows were kept.");
    }

    return data.rows.map((row) => {
      if (
        typeof row?.medicineName !== "string" ||
        typeof row.strength !== "string" ||
        typeof row.productId !== "string" ||
        !Array.isArray(row.suggestions) ||
        !(
          row.quantity === null ||
          (Number.isInteger(row.quantity) && quantityValid(row.quantity))
        )
      ) {
        throw new Error("Invalid medicine draft response. Existing rows were kept.");
      }

      const matched = exactProduct(row, products);
      const productId =
        matched ||
        (products.some((product) => product.id === row.productId)
          ? row.productId
          : "");

      return {
        ...row,
        rowId: nextId.current++,
        productId,
        quantity: row.quantity ?? "",
        sourceText: row.sourceText || "",
        doseText: row.doseText || "",
        scheduleText: row.scheduleText || "",
        durationText: row.durationText || "",
        quantityExplanation: row.quantityExplanation || "",
        reviewNotes: Array.isArray(row.reviewNotes)
          ? row.reviewNotes.filter((note) => typeof note === "string")
          : [],
        suggestions: row.suggestions.filter(
          (suggestion) =>
            typeof suggestion?.productId === "string" &&
            products.some((product) => product.id === suggestion.productId)
        ),
      };
    });
  }

  async function requestDraft(value) {
    if (!value.trim() || value.length > 12000) {
      throw new Error("Enter prescription text, up to 12,000 characters.");
    }

    return api("/prescription/draft", {
      text: value,
      useLLM,
      trayScope: TRAY_SCOPE,
    });
  }

  function applyDraft(data) {
    const prepared = normalizeRows(data);
    if (!mounted.current) return;

    invalidate();
    setRows(prepared);
    setExtraction({
      provider: data.provider || "local-parser",
      fallbackUsed: data.fallbackUsed === true,
      fallbackReason: data.fallbackReason || "",
    });
    setStep(1);
    setNotice(
      data.fallbackUsed
        ? "Draft created using the local fallback. Check the extraction warning."
        : "Draft created. Review the tablets per dose and matched products."
    );
  }

  function createDraft() {
    run("Creating medicine draft…", async () => {
      applyDraft(await requestDraft(text));
    });
  }

  function extractPhoto() {
    if (!prescriptionPhoto || !connected) return;

    run("Reading prescription and creating draft…", async () => {
      const data = await api("/prescription/ocr", {
        imageData: prescriptionPhoto,
      });

      if (typeof data?.text !== "string" || !Array.isArray(data.blocks)) {
        throw new Error("Invalid OCR response.");
      }
      if (!mounted.current) return;

      setOcrResult(data);
      setText(data.text);

      if (!data.text.trim()) {
        throw new Error("No medicine text was read. Check the image or enter the text.");
      }

      applyDraft(await requestDraft(data.text));
    });
  }

  function loadPhoto(event, prescriptionImage) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    run("Loading photo…", async () => {
      if (
        !["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
        file.size === 0 ||
        file.size > 5 * 1024 * 1024
      ) {
        throw new Error("Choose a non-empty JPG, PNG or WebP image under 5 MB.");
      }

      const value = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        readers.current.add(reader);

        reader.onload = () => {
          readers.current.delete(reader);
          resolve(String(reader.result));
        };
        reader.onerror = () => {
          readers.current.delete(reader);
          reject(new Error("Could not read the photo."));
        };
        reader.onabort = () => {
          readers.current.delete(reader);
          reject(new Error("Photo loading cancelled."));
        };

        reader.readAsDataURL(file);
      });

      if (!mounted.current) return;

      if (prescriptionImage) {
        invalidate();
        setPrescriptionPhoto(value);
        setPrescriptionFilename(file.name);
        setText("");
        setRows([]);
        setOcrResult(null);
        setExtraction(null);
      } else {
        setPhoto(value);
        setFilename(file.name);
        setRecognition(null);
        setResult(null);
      }
    });
  }

  function editRow(rowId, field, value) {
    invalidate();

    setRows((previous) =>
      previous.map((row) => {
        if (row.rowId !== rowId) return row;

        const updated = { ...row, [field]: value };

        if (field === "medicineName" || field === "strength") {
          updated.productId = exactProduct(updated, products);
          updated.suggestions = [];
        }

        if (field === "sourceText") {
          updated.quantity = "";
          updated.productId = "";
          updated.quantityExplanation =
            "Source edited. Click Re-read this instruction.";
        }

        if (field === "quantity") {
          updated.quantitySource = "manual";
          updated.quantityExplanation =
            "Manual override — review against the source.";
        }

        return updated;
      })
    );
  }

  function rereadRow(row) {
    run("Re-reading medicine instruction…", async () => {
      const data = await requestDraft(row.sourceText);
      const prepared = normalizeRows(data);

      if (prepared.length !== 1) {
        throw new Error("Keep one medicine instruction in this row.");
      }
      if (!mounted.current) return;

      invalidate();
      setRows((previous) =>
        previous.map((item) =>
          item.rowId === row.rowId
            ? { ...prepared[0], rowId: row.rowId }
            : item
        )
      );
      setNotice(
        data.fallbackUsed
          ? `Local fallback used: ${data.fallbackReason || "Review all fields."}`
          : "Instruction re-read. Review the updated count and product."
      );
    });
  }

  function chooseProduct(row, productId) {
    invalidate();
    setRows((previous) =>
      previous.map((item) =>
        item.rowId === row.rowId
          ? {
              ...item,
              productId,
              matchType: productId ? "manual" : "unresolved",
            }
          : item
      )
    );
  }

  function addMedicine() {
    if (rows.length >= 50) return;

    invalidate();
    setRows((previous) => [
      ...previous,
      {
        rowId: nextId.current++,
        medicineName: "",
        strength: "",
        productId: "",
        quantity: "",
        sourceText: "",
        doseText: "",
        scheduleText: "",
        durationText: "",
        reviewNotes: [],
        suggestions: [],
      },
    ]);
    setStep(1);
  }

  const incomplete = rows.filter(
    (row) => !row.medicineName.trim() || !quantityValid(row.quantity)
  ).length;
  const unmatched = rows.filter((row) => !row.productId).length;
  const ids = rows.map((row) => row.productId).filter(Boolean);
  const duplicates = new Set(ids).size !== ids.length;

  const saveReason = !connected
    ? "The medicine API is unavailable."
    : !service?.reviewedComparisonReady
    ? "Reviewed-list service is unavailable."
    : !rows.length
    ? "Create a medicine draft first."
    : incomplete
    ? `${incomplete} row(s) need a clear medicine name or quantity. Open Review / edit.`
    : duplicates
    ? "Combine duplicate product rows before saving."
    : !reviewed
    ? "Confirm that you reviewed the source, products and counts."
    : "";

  const canSave = !busy && !loading && !saveReason;
  const canDetect =
    connected && service?.modelReady && Boolean(photo) && !busy && !loading;
  const canCompare =
    canDetect &&
    service?.reviewedComparisonReady &&
    saved?.comparisonReady === true;
  const canTotal =
    canDetect &&
    service?.totalCountComparisonReady &&
    saved?.reviewed === true;

  function saveList() {
    if (!canSave) return;

    run("Saving reviewed list…", async () => {
      const data = await api("/prescription/review", {
        reference: reference.trim(),
        doseLabel: TRAY_LABEL,
        reviewed: true,
        items: rows.map((row) => ({
          medicineName: row.medicineName.trim(),
          strength: row.strength.trim(),
          productId: row.productId,
          quantity: Number(row.quantity),
        })),
      });

      if (
        typeof data?.id !== "string" ||
        data.reviewed !== true ||
        !Array.isArray(data.items)
      ) {
        throw new Error("Invalid saved-prescription response.");
      }
      if (!mounted.current) return;

      setSaved(data);
      setResult(null);
      setStep(2);
      setNotice("Reviewed list saved. Upload the prepared tray photo.");
    });
  }

  function detect() {
    if (!canDetect) return;
    prepareMedicineAudio().catch(() => {});

    run("Detecting pills…", async () => {
      setResult(null);
      setRecognition(null);

      const data = await api("/detect", { imageData: photo });
      if (!validRecognition(data)) {
        throw new Error("Invalid detection response.");
      }
      if (mounted.current) {
        setRecognition(data);
        setCheckNumber((number) => number + 1);
      }
    });
  }

  function compare(totalOnly) {
    if (totalOnly ? !canTotal : !canCompare) return;
    prepareMedicineAudio().catch(() => {});

    run("Comparing prepared tray…", async () => {
      setResult(null);
      setRecognition(null);

      const data = await api(
        totalOnly ? "/verify-total-count" : "/verify-reviewed",
        { prescriptionId: saved.id, imageData: photo }
      );

      const count = (value) => Number.isInteger(value) && value >= 0;

      if (
        data?.prescription?.id !== saved.id ||
        typeof data.status !== "string" ||
        !validRecognition(data.recognition)
      ) {
        throw new Error("Invalid comparison response.");
      }

      if (totalOnly) {
        if (
          data.comparisonType !== "total-count" ||
          data.identitiesChecked !== false ||
          !count(data.expectedTotal) ||
          !count(data.detectedTotal) ||
          !count(data.lowConfidenceCount) ||
          data.lowConfidenceCount > data.detectedTotal ||
          data.detectedTotal !== data.recognition.detections.length ||
          data.difference !== data.detectedTotal - data.expectedTotal
        ) {
          throw new Error("Invalid total-count result.");
        }
      } else if (
        data.comparisonType !== "product-count" ||
        !Array.isArray(data.rows) ||
        !data.rows.every(
          (row) =>
            typeof row?.productId === "string" &&
            count(row.expected) &&
            count(row.found)
        ) ||
        !Array.isArray(data.uncertain)
      ) {
        throw new Error("Invalid product-count result.");
      }

      if (!mounted.current) return;

      setResult(data);
      setRecognition(data.recognition);
      setCheckNumber((number) => number + 1);

      const record = { ...data };
      delete record.recognition;
      setHistory((previous) =>
        [record, ...previous.filter((item) => item.id !== record.id)].slice(0, 200)
      );
    });
  }

  const stepLabels = ["Prescription", "Review medicines", "Tray & results"];
  const threshold = Number.isFinite(result?.confidenceThreshold)
    ? result.confidenceThreshold
    : DEFAULT_REVIEW_THRESHOLD;

  return (
    <div className="av-medicine">
      <div className="av-inner">
        <header className="av-toolbar">
          <div className="av-title">
            <h1>
              {page === "history" ? "Review history" : "Medicine verification"}
            </h1>
            <p>
              {page === "history"
                ? "Previous tray comparisons."
                : "Read the prescription, review the tablets per dose, then check the prepared tray."}
            </p>
          </div>
          <div className="av-toolbar-right">
            <div className="av-seg" role="group" aria-label="Medicine navigation">
              <button
                className={page === "workspace" ? "active" : ""}
                disabled={busy}
                onClick={() => setPage("workspace")}
              >
                Workspace
              </button>
              <button
                className={page === "history" ? "active" : ""}
                disabled={busy}
                onClick={() => setPage("history")}
              >
                History
              </button>
            </div>
            <span className="av-status">
              <i className={`av-dot ${connected ? "online" : ""}`} />
              {loading
                ? "Connecting…"
                : connected
                ? "API connected"
                : "API offline"}
            </span>
          </div>
        </header>
        {page === "workspace" && (
          <MedicineSafety
            recognition={recognition}
            result={result}
            prescription={saved}
            checkNumber={checkNumber}
          />
        )}


        {error && (
          <div className="av-alert av-error" role="alert">
            <Icon name="alert" />
            <div>{error}</div>
          </div>
        )}
        {notice && (
          <div className="av-alert" role="status">
            <Icon name="info" />
            <div>{notice}</div>
          </div>
        )}
        {busy && (
          <div className="av-alert av-busy" role="status">
            <span className="av-spinner" />
            <div>{operation}</div>
          </div>
        )}

        {loading ? (
          <p className="av-muted">Connecting to the medicine service…</p>
        ) : page === "history" ? (
          <section>
            {!history.length && (
              <div className="av-empty">
                <span className="av-drop-icon">
                  <Icon name="pill" size={26} />
                </span>
                <strong>No saved comparisons yet</strong>
                <p>Completed tray comparisons will appear here.</p>
              </div>
            )}
            {history.map((record, index) => (
              <article className="av-card" key={record.id || index}>
                <div
                  className="av-row-head"
                  style={{ padding: 0, border: 0 }}
                >
                  <div className="av-row-title">
                    <h3>
                      {record.reference ||
                        record.prescription?.doseLabel ||
                        "Prepared tray"}
                    </h3>
                    <small>
                      {record.createdAt &&
                      !Number.isNaN(Date.parse(record.createdAt))
                        ? new Date(record.createdAt).toLocaleString()
                        : "Date unavailable"}
                    </small>
                  </div>
                  <StatusChip tone={comparisonTone(record)}>
                    {record.status}
                  </StatusChip>
                </div>
                <p className="av-muted" style={{ marginTop: 12 }}>
                  {record.comparisonType === "total-count"
                    ? `Total count only · expected ${record.expectedTotal}, detected ${record.detectedTotal}`
                    : "Predicted products and counts · manual review required"}
                </p>
                <details>
                  <summary>View comparison</summary>
                  <div style={{ marginTop: 14 }}>
                    <ComparisonResult
                      result={record}
                      productName={productName}
                    />
                  </div>
                </details>
              </article>
            ))}
          </section>
        ) : (
          <>
            <nav className="av-steps" aria-label="Review steps">
              {stepLabels.map((label, index) => (
                <button
                  key={label}
                  disabled={busy}
                  onClick={() => setStep(index)}
                  className={`${step === index ? "active" : ""} ${
                    index < step ? "done" : ""
                  }`}
                  aria-current={step === index ? "step" : undefined}
                >
                  <span className="av-step-num">
                    {index < step ? (
                      <Icon name="check" size={16} />
                    ) : (
                      index + 1
                    )}
                  </span>
                  {label}
                </button>
              ))}
            </nav>

            {step === 0 && (
              <fieldset disabled={busy}>
                <section className="av-card">
                  <div className="av-card-head">
                    <h2>Tray for one dose</h2>
                    <p>Counts are calculated from clear extracted instructions.</p>
                  </div>
                  <div className="av-alert" style={{ marginBottom: 0 }}>
                    <Icon name="info" />
                    <div>
                      Each tray is for <strong>one scheduled dose time</strong>.
                      Using the configured shorthand convention, 1x3 means one
                      tablet per dose and 2x3 means two tablets per dose.
                      Confirm that each medicine belongs at this time.
                    </div>
                  </div>
                  <div
  className={`ms-provider ${service?.llmConfigured ? "ready" : "unavailable"}`}
  role="status"
>
  <span className="ms-provider-dot" aria-hidden="true" />
  <div>
    <strong>
      {service?.llmConfigured
        ? "Powered by Groq"
        : "Groq extraction unavailable"}
    </strong>
    <small>
      {service?.llmConfigured
        ? "Automatic instruction extraction from OCR text. Review the draft before use."
        : "The API key is not configured in the medicine server."}
    </small>
  </div>
</div>
                  {useLLM && !service?.llmConfigured && (
                    <div
                      className="av-alert av-warning"
                      style={{ marginTop: 14, marginBottom: 0 }}
                    >
                      <Icon name="alert" />
                      <div>
                        The API has no Groq key. The backend may use a labelled
                        local fallback.
                      </div>
                    </div>
                  )}
                </section>

                <div className="av-grid">
                  <section className="av-card">
                    <div className="av-card-head">
                      <h2>Add the prescription</h2>
                      <p>Upload a clear, well-lit photo.</p>
                    </div>
                    <PhotoInput
                      title="Choose prescription photo"
                      image={prescriptionPhoto}
                      filename={prescriptionFilename}
                      disabled={busy}
                      onChange={(event) => loadPhoto(event, true)}
                    />
                    <div className="av-actions">
                      <button
                        className="av-button av-primary av-wide"
                        disabled={!prescriptionPhoto || !connected}
                        onClick={extractPhoto}
                      >
                        Read prescription & create draft
                      </button>
                    </div>
                  </section>

                  <section className="av-card">
                    <div className="av-card-head">
                      <h2>Check what was read</h2>
                      <p>
                        One medicine per line. Check decimal points and handwritten
                        numbers.
                      </p>
                    </div>
                    <label
                      className="av-label"
                      htmlFor="av-ocr"
                      style={{ marginTop: 0 }}
                    >
                      Prescription text
                    </label>
                    <textarea
                      id="av-ocr"
                      value={text}
                      maxLength={12000}
                      placeholder={
                        "Tab. Amlodipine 2.5 mg 1x1\nTab. Atenolol 50 mg 1x2"
                      }
                      onChange={(event) => {
                        setText(event.target.value);
                        invalidate();
                        setRows([]);
                        setExtraction(null);
                      }}
                    />
                    <div className="av-actions">
                      <button
                        className="av-button av-primary"
                        disabled={!text.trim() || !connected}
                        onClick={createDraft}
                      >
                        Create / replace draft
                      </button>
                      <button
                        className="av-button"
                        disabled={!connected}
                        onClick={addMedicine}
                      >
                        Enter manually
                      </button>
                    </div>
                    <p className="av-muted" style={{ marginBottom: 0 }}>
                      Creating a draft replaces the existing rows.
                    </p>
                    {ocrResult && (
                      <details>
                        <summary>OCR details</summary>
                        <pre>{JSON.stringify(ocrResult, null, 2)}</pre>
                      </details>
                    )}
                  </section>
                </div>
              </fieldset>
            )}

            {step === 1 && (
              <div className="av-grid av-review">
                <aside className="av-card">
                  <div className="av-card-head">
                    <h2>Original prescription</h2>
                    <p>{TRAY_LABEL}</p>
                  </div>
                  {prescriptionPhoto ? (
                    <a
                      href={prescriptionPhoto}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <img
                        className="av-photo"
                        src={prescriptionPhoto}
                        alt="Original prescription"
                      />
                    </a>
                  ) : (
                    <p className="av-muted">No prescription image uploaded.</p>
                  )}
                  <p className="av-muted" style={{ marginTop: 14 }}>
                    Counts are draft calculations. Review against the source before
                    saving.
                  </p>
                  <button
                    className="av-button av-wide"
                    disabled={busy}
                    onClick={() => setStep(0)}
                  >
                    Back to source & options
                  </button>
                  {extraction && (
                    <p
                      className="av-muted"
                      style={{ marginTop: 12, marginBottom: 0 }}
                    >
                      Extraction: <strong>{extraction.provider}</strong>
                    </p>
                  )}
                </aside>

                <section>
                  <div className="av-metrics">
                    <div>
                      <strong>{rows.length}</strong>
                      <small>Medicine rows</small>
                    </div>
                    <div>
                      <strong>{rows.length - unmatched}</strong>
                      <small>Products selected</small>
                    </div>
                    <div className={incomplete ? "warn" : ""}>
                      <strong>{incomplete}</strong>
                      <small>Need a count or name</small>
                    </div>
                  </div>

                  {extraction?.fallbackUsed && (
                    <div className="av-alert av-warning" role="status">
                      <Icon name="alert" />
                      <div>
                        <strong>Local fallback used.</strong>{" "}
                        {extraction.fallbackReason}
                      </div>
                    </div>
                  )}

                  <fieldset disabled={busy}>
                    <div className="av-card">
                      <label
                        className="av-label"
                        htmlFor="av-reference"
                        style={{ marginTop: 0 }}
                      >
                        Patient / tray reference · optional
                      </label>
                      <input
                        id="av-reference"
                        value={reference}
                        maxLength={200}
                        onChange={(event) => {
                          setReference(event.target.value);
                          invalidate();
                        }}
                      />
                      <p
                        className="av-muted"
                        style={{ marginTop: 10, marginBottom: 0 }}
                      >
                        {products.length} dataset products available · {TRAY_LABEL}
                      </p>
                    </div>

                    {!rows.length && (
                      <div className="av-empty">
                        <span className="av-drop-icon">
                          <Icon name="pill" size={26} />
                        </span>
                        <strong>No medicines yet</strong>
                        <p>Create a draft, or add a medicine manually.</p>
                      </div>
                    )}

                    {rows.map((row, index) => {
                      const productOk = Boolean(row.productId);
                      const countOk = quantityValid(row.quantity);
                      const needsReview = !productOk || !countOk;

                      return (
                        <article
                          className={`av-row ${needsReview ? "attention" : ""}`}
                          key={row.rowId}
                        >
                          <div className="av-row-head">
                            <span className="av-row-num">
                              {String(index + 1).padStart(2, "0")}
                            </span>
                            <div className="av-row-title">
                              <h3>{row.medicineName || "New medicine"}</h3>
                              <small>
                                {row.strength ? `Written strength: ${row.strength}` : "Prescription strength not read — confirm separately"}
                              </small>
                            </div>
                            <StatusChip tone={needsReview ? "warning" : "match"}>
                              {needsReview ? "Needs review" : "Ready for review"}
                            </StatusChip>
                          </div>

                          <div className="av-row-body">
                            <div className="av-summary">
                              <div className={`av-tile ${productOk ? "" : "warn"}`}>
                                <span className="av-tile-icon">
                                  <Icon
                                    name={productOk ? "check" : "alert"}
                                    size={15}
                                  />
                                </span>
                                <div>
                                  <small>Matched dataset product — review selection</small>
                                  <strong>
                                    {productOk
                                      ? productName(row.productId)
                                      : "No unique exact match"}
                                  </strong>
                                </div>
                              </div>
                              <div className={`av-tile ${countOk ? "" : "warn"}`}>
                                <span className="av-tile-icon">
                                  <Icon
                                    name={countOk ? "check" : "alert"}
                                    size={15}
                                  />
                                </span>
                                <div>
                                  <small>Tablets per dose</small>
                                  <strong>
                                    {countOk
                                      ? `${row.quantity} tablet${
                                          Number(row.quantity) > 1 ? "s" : ""
                                        }`
                                      : "Instruction needs review"}
                                  </strong>
                                </div>
                              </div>
                            </div>

                            <p className="av-instruction">
                              <span>Read instruction</span>
                              <code>
                                {[row.doseText, row.scheduleText]
                                  .filter(Boolean)
                                  .join(" · ") || "Not clearly extracted"}
                              </code>
                            </p>
                            {row.quantityExplanation && (
                              <p className="av-muted" style={{ marginBottom: 0 }}>
                                {row.quantityExplanation}
                              </p>
                            )}

                            {!row.productId && row.suggestions.length > 0 && (
                              <div className="av-suggest">
                                <p className="av-muted" style={{ margin: 0 }}>
                                  Possible matches. Select only after checking:
                                </p>
                                <div className="av-actions">
                                  {row.suggestions.map((suggestion) => (
                                    <button
                                      className="av-button"
                                      key={suggestion.productId}
                                      onClick={() =>
                                        chooseProduct(row, suggestion.productId)
                                      }
                                    >
                                      {productName(suggestion.productId)}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            )}

                            <details>
                              <summary>
                                Review / edit
                                {needsReview ? " — attention required" : ""}
                              </summary>

                              <label
                                className="av-label"
                                htmlFor={`source-${row.rowId}`}
                              >
                                Original OCR instruction · editable
                              </label>
                              <textarea
                                id={`source-${row.rowId}`}
                                value={row.sourceText}
                                maxLength={12000}
                                style={{ minHeight: 80 }}
                                onChange={(event) =>
                                  editRow(
                                    row.rowId,
                                    "sourceText",
                                    event.target.value
                                  )
                                }
                              />
                              <div className="av-actions">
                                <button
                                  className="av-button av-primary"
                                  disabled={!row.sourceText.trim() || !connected}
                                  onClick={() => rereadRow(row)}
                                >
                                  Re-read this instruction
                                </button>
                              </div>
                              <p className="av-muted">
                                Correct the text against the image, then re-read to
                                update the extracted fields and count.
                              </p>

                              <div className="av-grid" style={{ gap: 16 }}>
                                <div>
                                  <label
                                    className="av-label"
                                    htmlFor={`name-${row.rowId}`}
                                  >
                                    Reviewed medicine name
                                  </label>
                                  <input
                                    id={`name-${row.rowId}`}
                                    value={row.medicineName}
                                    maxLength={200}
                                    onChange={(event) =>
                                      editRow(
                                        row.rowId,
                                        "medicineName",
                                        event.target.value
                                      )
                                    }
                                  />
                                </div>
                                <div>
                                  <label
                                    className="av-label"
                                    htmlFor={`strength-${row.rowId}`}
                                  >
                                    Recorded strength
                                  </label>
                                  <input
                                    id={`strength-${row.rowId}`}
                                    value={row.strength}
                                    maxLength={80}
                                    onChange={(event) =>
                                      editRow(
                                        row.rowId,
                                        "strength",
                                        event.target.value
                                      )
                                    }
                                  />
                                </div>
                                <div>
                                  <label
                                    className="av-label"
                                    htmlFor={`product-${row.rowId}`}
                                  >
                                    Dataset product override
                                  </label>
                                  <select
                                    id={`product-${row.rowId}`}
                                    value={row.productId}
                                    onChange={(event) =>
                                      chooseProduct(row, event.target.value)
                                    }
                                  >
                                    <option value="">
                                      Needs review / no exact match
                                    </option>
                                    {products.map((product) => (
                                      <option key={product.id} value={product.id}>
                                        {product.name}
                                      </option>
                                    ))}
                                  </select>
                                </div>
                                <div>
                                  <label
                                    className="av-label"
                                    htmlFor={`quantity-${row.rowId}`}
                                  >
                                    Tablets per dose override · only if required
                                  </label>
                                  <input
                                    id={`quantity-${row.rowId}`}
                                    type="number"
                                    min="1"
                                    max="100"
                                    step="1"
                                    value={row.quantity}
                                    onChange={(event) =>
                                      editRow(
                                        row.rowId,
                                        "quantity",
                                        event.target.value
                                      )
                                    }
                                  />
                                </div>
                              </div>

                              {!!row.reviewNotes.length && (
                                <ul className="av-muted">
                                  {row.reviewNotes.map((note, noteIndex) => (
                                    <li key={noteIndex}>{note}</li>
                                  ))}
                                </ul>
                              )}
                              <div className="av-actions">
                                <button
                                  className="av-button av-danger"
                                  onClick={() => {
                                    invalidate();
                                    setRows((previous) =>
                                      previous.filter(
                                        (item) => item.rowId !== row.rowId
                                      )
                                    );
                                  }}
                                >
                                  Remove medicine
                                </button>
                              </div>
                            </details>
                          </div>
                        </article>
                      );
                    })}

                    <button
                      className="av-button av-add"
                      disabled={rows.length >= 50}
                      onClick={addMedicine}
                    >
                      + Add medicine
                    </button>

                    <section
                      className="av-card av-save"
                      style={{ marginTop: 22 }}
                    >
                      {!!unmatched && (
                        <p className="av-muted">
                          {unmatched} product(s) need review. A saved list without
                          product matches supports total-count comparison only.
                        </p>
                      )}
                      <label
                        className="av-check"
                        style={{ background: "#ffffff", marginTop: 0 }}
                      >
                        <input
                          type="checkbox"
                          checked={reviewed}
                          onChange={(event) => {
                            setReviewed(event.target.checked);
                            setSaved(null);
                            setResult(null);
                          }}
                        />
                        <span>
                          I checked the original instructions, names, strengths,
                          selected products and tablets per dose. I confirmed that
                          every medicine listed belongs to this dose time.
                        </span>
                      </label>
                      {saveReason && <p className="av-muted">{saveReason}</p>}
                      <button
                        className="av-button av-primary av-wide"
                        disabled={!canSave}
                        onClick={saveList}
                      >
                        Save reviewed list & continue
                      </button>
                    </section>
                  </fieldset>
                </section>
              </div>
            )}

            {step === 2 && (
              <>
                <div className="av-grid">
                  <section className="av-card">
                    <div className="av-card-head">
                      <h2>Prepared tray</h2>
                      <p>
                        Tablets separate, visible and in focus, on a plain
                        background.
                      </p>
                    </div>
                    <PhotoInput
                      title="Choose tray photo"
                      image={photo}
                      filename={filename}
                      disabled={busy}
                      onChange={(event) => loadPhoto(event, false)}
                    />
                    <div className="av-actions">
                      <button
                        className="av-button"
                        disabled={!canDetect}
                        onClick={detect}
                      >
                        Detect pills
                      </button>
                      <button
                        className="av-button"
                        disabled={!canTotal}
                        onClick={() => compare(true)}
                      >
                        Compare total count
                      </button>
                      <button
                        className="av-button av-primary"
                        disabled={!canCompare}
                        onClick={() => compare(false)}
                      >
                        Compare medicines & counts
                      </button>
                    </div>
                    {!saved && (
                      <p className="av-muted">
                        Save a reviewed list before comparing.
                      </p>
                    )}
                    {saved && !saved.comparisonReady && (
                      <p className="av-muted">
                        Some products remain unselected. Only total-count
                        comparison is available.
                      </p>
                    )}
                  </section>

                  <section className="av-card">
                    <div className="av-card-head">
                      <h2>{saved?.doseLabel || "Reviewed list"}</h2>
                    </div>
                    {!saved ? (
                      <p className="av-muted">No reviewed list saved.</p>
                    ) : (
                      saved.items.map((item, index) => (
                        <div className="av-detection" key={index}>
                          <span>
                            <strong>{item.medicineName}</strong>
                            <small>
                              {item.strength || "Strength not recorded"}
                            </small>
                            <small>
                              {item.productId
                                ? productName(item.productId)
                                : "No product selected"}
                            </small>
                          </span>
                          <strong>× {item.quantity}</strong>
                        </div>
                      ))
                    )}
                    <div className="av-actions">
                      <button
                        className="av-button"
                        disabled={busy}
                        onClick={() => setStep(1)}
                      >
                        Review medicine list
                      </button>
                    </div>
                  </section>
                </div>

                <ComparisonResult
                  result={result}
                  productName={productName}
                />

                <section className="av-card">
                  <div className="av-card-head">
                    <h2>Tablet recognition</h2>
                    <p>Model scores are not correctness guarantees.</p>
                  </div>

                  {!recognition ? (
                    <div className="av-empty" style={{ marginBottom: 0 }}>
                      <span className="av-drop-icon">
                        <Icon name="pill" size={26} />
                      </span>
                      <strong>No predictions yet</strong>
                      <p>Upload a tray photo and choose an action.</p>
                    </div>
                  ) : (
                    <>
                      {recognition.detections.some((item) => item.referenceMode) && (

<div style={{
  display: "flex",
  flexWrap: "wrap",
  alignItems: "center",
  gap: 12,
  marginBottom: 16,
  padding: "10px 14px",
  border: "1px solid #d7e3dc",
  borderRadius: 10,
  background: "#f3f7f4",
  color: "#365347"
}}>
  <strong style={{ fontSize: 12 }}>
    Appearance-assisted review
  </strong>
  <details style={{ fontSize: 12 }}>
    <summary style={{ cursor: "pointer" }}>
      Method details
    </summary>
    <p style={{ margin: "8px 0 0", lineHeight: 1.6 }}>
      Labels use colour and relative size for five declared samples.
      These appearance-assisted labels are not confirmed model identities.
      Review against original packaging.
    </p>
  </details>
</div>

                      )}
                      <img
                        className="av-photo"
                        src={recognition.annotatedImage}
                        alt="Predicted tablets with bounding boxes"
                      />
                      {!recognition.detections.length && (
                        <p>No detections returned.</p>
                      )}

                      <div style={{ marginTop: 14 }}>
                        {recognition.detections.map((item, index) => {
                          const uncertain =
                            item.identityUncertain ||
                            item.label === "__uncertain__";
                          const lowScore = item.confidence < threshold;
                          const itemTone = predictionTone(item, threshold);

                          return (
                            <div
                              className="av-detection"
                              key={`${item.label}-${index}`}
                            >
                              <span>
                                <strong>
                                  {index + 1}.{" "}
                                  {uncertain
                                    ? "Unidentified — conflicting / ambiguous prediction"
                                    : item.productName || productName(item.label)}
                                </strong>
                                <small>
                                  {item.referenceMode
                                    ? (item.referenceAssigned ? "Appearance-assisted label" : "Identity needs review")
                                    : uncertain
                                    ? "Identity needs review"
                                    : item.unmapped
                                    ? "Unsupported class"
                                    : lowScore
                                    ? "Low model score — excluded from product counts"
                                    : "Predicted identity — review required"}
                                </small>

                                {!item.referenceMode && uncertain && !!item.alternatives?.length && (
                                  <small>
                                    Candidates:{" "}
                                    {[
                                      ...new Set(
                                        item.alternatives.map(
                                          (alternative) => alternative.label
                                        )
                                      ),
                                    ]
                                      .map(productName)
                                      .join(" / ")}
                                  </small>
                                )}
                              </span>
                              <StatusChip tone={itemTone}>
                                {item.referenceMode ? (item.referenceAssigned ? "Assisted" : "Review") : `${(item.confidence * 100).toFixed(1)}%`}
                              </StatusChip>
                            </div>
                          );
                        })}
                      </div>
                    </>
                  )}
                </section>
              </>
            )}
          </>
        )}

        <footer>
          Review against the original prescription and medicine packaging.
          This research system does not confirm clinical suitability.
        </footer>
      </div>
    </div>
  );
}
