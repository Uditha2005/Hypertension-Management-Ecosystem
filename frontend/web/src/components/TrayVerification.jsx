import React, { useEffect, useRef, useState } from "react";
import "./TrayVerification.css";

const API = (
  process.env.REACT_APP_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

const STEPS = ["Prescription", "Review medicines", "Tray & results"];

const REVIEW_STYLES = `
.med-workspace {
  --mv-ink: #292929;
  --mv-muted: #666666;
  --mv-line: #d7ded8;
  --mv-teal: #287a43;
  --mv-teal-dark: #1d6033;
  --mv-canvas: #f2f4f2;
  color-scheme: light;
  accent-color: #287a43;
}
.med-workspace .mv-top { background:#193f27; border-color:#315b3a; }
.med-workspace .mv-brand-icon {
  background:#315b3a; color:white; border-color:#628769;
}
.med-workspace .mv-top nav { background:#12321d; border-color:#41694b; }
.med-workspace .mv-top nav button { color:#d8e7da; }
.med-workspace .mv-top nav button.active { background:white; color:#245c34; }
.med-workspace .mv-reference { background:#eaf0eb; border-color:#cbd8ce; }
.med-workspace .mv-review-layout { align-items:start; }
.med-workspace .mv-reference-note {
  padding:16px; border:1px solid #bfd4c3; border-radius:12px;
  background:#dcebdd; color:#34533b;
}
.med-workspace .mv-medicine {
  margin-bottom:20px; padding:24px; overflow:hidden;
  border:1px solid #bfd5c3; border-left:5px solid #35834a;
  border-radius:16px; background:#f1f7f2;
  box-shadow:0 5px 18px rgba(0,0,0,.04);
}
.med-workspace .mv-medicine-heading {
  display:flex; align-items:center; gap:14px;
  margin:-24px -24px 22px; padding:20px 24px;
  border-bottom:1px solid #bfd5c3; background:#dcebdd; color:#204e2c;
}
.med-workspace .mv-medicine-heading > div { min-width:0; flex:1; }
.med-workspace .mv-medicine-heading h3 {
  margin:0; color:#204e2c; font-size:18px; font-weight:750;
  overflow-wrap:anywhere;
}
.med-workspace .mv-medicine-heading p {
  margin:5px 0 0; color:#48634e; font-size:12px;
}
.med-workspace .mv-medicine-number {
  display:grid; place-items:center; flex:0 0 44px;
  width:44px; height:44px; border-radius:12px;
  background:#286639; color:white; font-weight:750;
}
.med-workspace .mv-medicine label { color:#344a39; font-weight:650; }
.med-workspace .mv-medicine input,
.med-workspace .mv-medicine select {
  width:100%; border:1px solid #b8cabb; border-radius:10px;
  background:white; color:#292929; box-shadow:none;
}
.med-workspace input:focus-visible,
.med-workspace select:focus-visible,
.med-workspace textarea:focus-visible,
.med-workspace button:focus-visible {
  outline:2px solid #35834a; outline-offset:3px;
}
.med-workspace .mv-medicine .mv-field-note { color:#57635a; }
.med-workspace .mv-source-line {
  margin-bottom:18px; padding:12px 14px; border:1px solid #d4ddd5;
  border-radius:9px; background:#e8eee9; color:#4b554d;
  overflow-wrap:anywhere;
}
.med-workspace .mv-source-line summary { cursor:pointer; font-size:12px; }
.med-workspace .mv-remove {
  margin-left:auto; padding:7px 12px; border:1px solid #b1c5b5;
  border-radius:8px; background:white; color:#505050;
}
.med-workspace .mv-autofill-note {
  display:inline-flex; margin-top:10px; padding:5px 10px;
  border:1px solid #bdd8c4; border-radius:7px;
  background:#deeee2; color:#245c34; font-size:12px;
}
.med-workspace .mv-save-panel { border-color:#bfd5c3; background:#e7f1e8; }
.med-workspace .mv-primary { background:#287a43; color:white; }
.med-workspace .mv-primary:hover:not(:disabled) { background:#1d6033; }
.med-workspace .mv-primary:disabled { background:#ddd; color:#666; }
.med-workspace .mv-secondary {
  background:white; border-color:#bacbbd; color:#34533b;
}
.med-workspace .mv-suggestions button {
  border:1px solid #b8cfbd; background:white; color:#285c36;
}
.med-workspace .mv-fields { min-width:0; }
.med-workspace .mv-details pre {
  white-space:pre-wrap; overflow-wrap:anywhere;
}
.med-workspace .mv-actions {
  display:flex; flex-wrap:wrap; gap:12px;
}
.med-workspace .mv-actions > button {
  flex:1 1 180px; width:auto; margin-top:0;
}
.med-workspace .mv-count-only {
  border:1px solid #b9cbbb; border-top:5px solid #487b52;
  background:#f1f6f2;
}
.med-workspace .mv-count-only .mv-alert {
  background:#e4ebe5; color:#344438; border-color:#bfcdc2;
}
@media (max-width:550px) {
  .med-workspace .mv-medicine { padding:18px; }
  .med-workspace .mv-medicine-heading {
    margin:-18px -18px 18px; padding:16px 18px;
    gap:10px; flex-wrap:wrap;
  }
}
`;

function tone(status) {
  if (status === "Counts match — review required") return "match";
  if (status === "Count differences — review required") return "difference";
  return "uncertain";
}

function quantityValid(value) {
  return (
    String(value ?? "").trim() !== "" &&
    Number.isInteger(Number(value)) &&
    Number(value) >= 1 &&
    Number(value) <= 100
  );
}

function validCount(value) {
  return Number.isInteger(value) && value >= 0;
}

function validRecognition(data) {
  return (
    data &&
    Array.isArray(data.detections) &&
    data.detections.every(
      (item) =>
        item &&
        typeof item.label === "string" &&
        Number.isFinite(item.confidence) &&
        item.confidence >= 0 &&
        item.confidence <= 1 &&
        Array.isArray(item.bbox) &&
        item.bbox.length === 4 &&
        item.bbox.every(Number.isFinite) &&
        item.bbox[2] > item.bbox[0] &&
        item.bbox[3] > item.bbox[1]
    ) &&
    typeof data.annotatedImage === "string" &&
    data.annotatedImage.startsWith("data:image/jpeg;base64,")
  );
}

function validDraft(row) {
  return (
    row &&
    typeof row.medicineName === "string" &&
    typeof row.strength === "string" &&
    typeof row.productId === "string" &&
    Array.isArray(row.suggestions) &&
    row.suggestions.every(
      (item) =>
        item &&
        typeof item.productId === "string" &&
        typeof item.name === "string"
    ) &&
    (row.quantity === null ||
      (Number.isInteger(row.quantity) &&
        row.quantity >= 1 &&
        row.quantity <= 100))
  );
}

function medicineIdentity(name = "", strength = "") {
  const text = `${name} ${strength}`
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[µμ]g/g, "mcg");

  const pattern = /(\d+(?:\.\d+)?)\s*(mcg|mg|g|ml|iu|%)(?![a-z])/g;
  const strengths = [
    ...new Set(
      Array.from(
        text.matchAll(pattern),
        (match) => `${Number(match[1])}${match[2]}`
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

function findExactSupportedProduct(row, products) {
  const target = medicineIdentity(row.medicineName, row.strength);

  // Combination/concentration expressions remain for manual selection.
  if (!target.name || !target.strength || target.complex) return "";

  const matches = products.filter((product) => {
    const candidate = medicineIdentity(product.name, product.strength || "");
    return (
      !candidate.complex &&
      candidate.name === target.name &&
      candidate.strength === target.strength
    );
  });

  return matches.length === 1 ? matches[0].id : "";
}

function explicitTrayQuantity(sourceText = "") {
  const pattern =
    /\b(?:tray\s+(?:qty|quantity)\s*[:=]\s*(\d+)|(\d+)\s+(?:tablets?|pills?|capsules?)\s+for\s+(?:this\s+)?tray)\b/gi;

  const matches = Array.from(
    String(sourceText).matchAll(pattern),
    (match) => Number(match[1] || match[2])
  );

  return matches.length &&
    matches.every(quantityValid) &&
    new Set(matches).size === 1
    ? matches[0]
    : "";
}

function Icon({ kind, size = 22 }) {
  const paths = {
    plus: <path d="M12 5v14M5 12h14" />,
    check: <path d="m5 12 4 4L19 6" />,
    arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
    document: (
      <>
        <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
        <path d="M14 3v6h6M8 13h8M8 17h5" />
      </>
    ),
    image: (
      <>
        <rect x="3" y="3" width="18" height="18" rx="3" />
        <circle cx="8" cy="8" r="1" />
        <path d="m21 15-5-5L5 21" />
      </>
    ),
    history: (
      <>
        <path d="M3 11a9 9 0 1 1 2.7 7M3 4v7h7" />
        <path d="M12 7v5l3 2" />
      </>
    ),
  };

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[kind] || paths.document}
    </svg>
  );
}

function Upload({ image, filename, title, onChange, disabled }) {
  return (
    <div>
      <label className={`mv-upload ${image ? "has-image" : ""}`}>
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          aria-label={title}
          onChange={onChange}
          disabled={disabled}
        />
        {image ? (
          <img src={image} alt={title} />
        ) : (
          <>
            <span className="mv-upload-symbol">
              <Icon kind="image" size={30} />
            </span>
            <strong>{title}</strong>
            <span>Choose a clear JPG, PNG or WebP image</span>
            <small>Maximum file size: 5 MB</small>
          </>
        )}
      </label>
      {filename && (
        <p className="mv-help mv-filename">
          {filename} · Click the image to replace
        </p>
      )}
    </div>
  );
}

export default function TrayVerification() {
  const mounted = useRef(false);
  const controllers = useRef(new Set());
  const readers = useRef(new Set());
  const nextId = useRef(2);
  const operationLock = useRef(false);

  const [page, setPage] = useState("workspace");
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);
  const [modelReady, setModelReady] = useState(false);
  const [comparisonReady, setComparisonReady] = useState(false);
  const [totalReady, setTotalReady] = useState(false);
  const [products, setProducts] = useState([]);
  const [history, setHistory] = useState([]);
  const [operation, setOperation] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [prescriptionPhoto, setPrescriptionPhoto] = useState("");
  const [prescriptionFilename, setPrescriptionFilename] = useState("");
  const [ocrResult, setOcrResult] = useState(null);
  const [text, setText] = useState("");
  const [reference, setReference] = useState("");
  const [doseLabel, setDoseLabel] = useState("Prepared tray");
  const [reviewed, setReviewed] = useState(false);
  const [prescription, setPrescription] = useState(null);
  const [photo, setPhoto] = useState("");
  const [filename, setFilename] = useState("");
  const [recognition, setRecognition] = useState(null);
  const [result, setResult] = useState(null);

  const [rows, setRows] = useState([
    {
      rowId: 1,
      medicineName: "",
      strength: "",
      quantity: "",
      quantitySource: "",
      productId: "",
      matchType: "unresolved",
      suggestions: [],
      sourceText: "",
    },
  ]);

  const busy = operation !== "";

  async function api(path, body) {
    const controller = new AbortController();
    controllers.current.add(controller);
    const timeout = setTimeout(() => controller.abort(), 120000);

    try {
      const response = await fetch(`${API}/api/medicine${path}`, {
        method: body === undefined ? "GET" : "POST",
        headers: body === undefined
          ? undefined
          : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });

      let data;
      try {
        data = await response.json();
      } catch {
        throw new Error(`Unreadable service response (HTTP ${response.status}).`);
      }

      if (!response.ok) {
        throw new Error(
          typeof data?.error === "string"
            ? data.error
            : typeof data?.detail === "string"
            ? data.detail
            : `Request failed (HTTP ${response.status}).`
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
        if (data?.mode !== "live") {
          throw new Error("The live medicine service is unavailable.");
        }

        setConnected(true);
        setModelReady(data.modelReady === true);
        setComparisonReady(data.reviewedComparisonReady === true);
        setTotalReady(data.totalCountComparisonReady === true);
        setProducts(
          Array.isArray(data.products)
            ? data.products.filter(
                (item) =>
                  item &&
                  typeof item.id === "string" &&
                  typeof item.name === "string"
              )
            : []
        );

        try {
          const records = await api("/history");
          if (!cancelled && Array.isArray(records)) {
            setHistory(
              records.filter((item) => item?.mode === "live").slice(0, 200)
            );
          }
        } catch {
          if (!cancelled) {
            setNotice("Connected, but previous history could not be loaded.");
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
    if (operationLock.current || loading) return;
    operationLock.current = true;
    setOperation(label);
    setError("");
    setNotice("");

    try {
      await action();
    } catch (err) {
      if (mounted.current) setError(err.message || "The operation failed.");
    } finally {
      operationLock.current = false;
      if (mounted.current) setOperation("");
    }
  }

  function freshRow() {
    return {
      rowId: nextId.current++,
      medicineName: "",
      strength: "",
      quantity: "",
      quantitySource: "",
      productId: "",
      matchType: "unresolved",
      suggestions: [],
      sourceText: "",
    };
  }

  function invalidate() {
    setReviewed(false);
    setPrescription(null);
    setResult(null);
  }

  function updateRow(rowId, field, value) {
    invalidate();

    setRows((previous) =>
      previous.map((row) => {
        if (row.rowId !== rowId) return row;
        const updated = { ...row, [field]: value };

        if (field === "medicineName" || field === "strength") {
          updated.productId = findExactSupportedProduct(updated, products);
          updated.matchType = updated.productId ? "exact-text" : "unresolved";
          updated.suggestions = [];
        }
        if (field === "productId") {
          updated.matchType = value ? "manual" : "unresolved";
        }
        if (field === "quantity") updated.quantitySource = "manual";

        return updated;
      })
    );
  }

  function autofillMissingFields() {
    invalidate();
    setRows((previous) =>
      previous.map((row) => {
        const updated = { ...row };
        if (!updated.productId) {
          updated.productId = findExactSupportedProduct(updated, products);
          updated.matchType = updated.productId ? "exact-text" : "unresolved";
        }
        if (String(updated.quantity ?? "").trim() === "") {
          const quantity = explicitTrayQuantity(updated.sourceText);
          if (quantityValid(quantity)) {
            updated.quantity = quantity;
            updated.quantitySource = "explicit";
          }
        }
        return updated;
      })
    );
    setNotice(
      "Checked blank fields for exact product matches and explicit tray quantities. Review all values."
    );
  }

  function productName(id) {
    return products.find((item) => item.id === id)?.name || id || "Unidentified";
  }

  function loadImage(event, isPrescription) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || busy || loading) return;

    if (
      !["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
      file.size === 0 ||
      file.size > 5 * 1024 * 1024
    ) {
      setError("Choose a non-empty JPG, PNG or WebP image up to 5 MB.");
      return;
    }

    run("Loading image…", () =>
      new Promise((resolve, reject) => {
        const reader = new FileReader();
        readers.current.add(reader);
        const finish = () => readers.current.delete(reader);

        reader.onload = () => {
          finish();
          if (mounted.current) {
            if (isPrescription) {
              invalidate();
              setPrescriptionPhoto(String(reader.result));
              setPrescriptionFilename(file.name);
              setOcrResult(null);
              setText("");
              setRows([freshRow()]);
            } else {
              setPhoto(String(reader.result));
              setFilename(file.name);
              setRecognition(null);
              setResult(null);
            }
          }
          resolve();
        };

        reader.onerror = () => {
          finish();
          reject(new Error("Could not read the selected image."));
        };
        reader.onabort = () => {
          finish();
          reject(new Error("Image loading was cancelled."));
        };
        reader.readAsDataURL(file);
      })
    );
  }

  async function createDraft(value) {
    if (!value.trim()) throw new Error("Add prescription text first.");
    if (
      value.length > 12000 ||
      value.split(/\r?\n/).filter((line) => line.trim()).length > 50
    ) {
      throw new Error("Use at most 12,000 characters and 50 medicine lines.");
    }

    const data = await api("/prescription/draft", { text: value });
    if (
      !Array.isArray(data?.rows) ||
      data.rows.length > 50 ||
      !data.rows.every(validDraft)
    ) {
      throw new Error("Invalid draft response. Existing rows were kept.");
    }
    if (!data.rows.length) {
      throw new Error("No medicine rows extracted. Correct the text or add rows manually.");
    }
    if (!mounted.current) return;

    invalidate();
    setRows(
      data.rows.map((row) => {
        const known = products.some((product) => product.id === row.productId);
        const productId = known
          ? row.productId
          : findExactSupportedProduct(row, products);
        const quantity = quantityValid(row.quantity)
          ? row.quantity
          : explicitTrayQuantity(row.sourceText);

        return {
          ...row,
          rowId: nextId.current++,
          productId,
          quantity,
          quantitySource: quantityValid(quantity) ? "explicit" : "",
          matchType: productId ? "exact-text" : "unresolved",
        };
      })
    );
    setStep(1);
    setNotice("Draft created. Auto-filled values remain editable.");
  }

  function extractPrescription() {
    if (!prescriptionPhoto || !connected) return;

    run("Reading prescription…", async () => {
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
        throw new Error("No medicine text selected. Check All OCR text or type the lines.");
      }
      await createDraft(data.text);
    });
  }

  const selectedIds = rows.map((row) => row.productId).filter(Boolean);
  const duplicateProducts = new Set(selectedIds).size !== selectedIds.length;
  const incompleteRows = rows.filter(
    (row) => !row.medicineName.trim() || !quantityValid(row.quantity)
  ).length;
  const unmappedRows = rows.filter((row) => !row.productId).length;
  const missingStrengths = rows.filter((row) => !row.strength.trim()).length;

  const saveReason = !connected
    ? "The medicine service is offline."
    : !comparisonReady
    ? "The reviewed-prescription service is unavailable."
    : !rows.length
    ? "Add at least one medicine."
    : !doseLabel.trim()
    ? "Enter a tray label."
    : incompleteRows
    ? `${incompleteRows} row(s) need a name and a whole-number tray quantity from 1 to 100.`
    : duplicateProducts
    ? "Combine duplicate products into one row with their total tray quantity."
    : !reviewed
    ? "Confirm that you reviewed the medicine list."
    : "";

  const canSave = !saveReason && rows.length <= 50 && !busy && !loading;
  const canDetect = connected && modelReady && Boolean(photo) && !busy && !loading;
  const canVerify =
    canDetect && comparisonReady && prescription?.comparisonReady === true;
  const canCompareTotal =
    canDetect && totalReady && prescription?.reviewed === true &&
    Boolean(prescription?.id);

  function savePrescription() {
    if (!canSave) return;

    run("Saving reviewed list…", async () => {
      const data = await api("/prescription/review", {
        reference: reference.trim(),
        doseLabel: doseLabel.trim(),
        reviewed: true,
        items: rows.map((row) => ({
          medicineName: row.medicineName.trim(),
          strength: row.strength.trim(),
          quantity: Number(row.quantity),
          productId: row.productId,
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

      setPrescription(data);
      setResult(null);
      setStep(2);
      setNotice(
        data.comparisonReady
          ? "List saved. Upload a tray photo and choose a comparison."
          : "List saved. Total-count comparison is available; product comparison requires supported medicines."
      );
    });
  }

  function detectPills() {
    if (!canDetect) return;

    run("Detecting pills…", async () => {
      setRecognition(null);
      setResult(null);
      const data = await api("/detect", { imageData: photo });

      if (data?.mode !== "live" || !validRecognition(data)) {
        throw new Error("Invalid pill-detection response.");
      }
      if (mounted.current) setRecognition(data);
    });
  }

  function compareTray(totalOnly = false) {
    if (totalOnly ? !canCompareTotal : !canVerify) return;

    run(
      totalOnly ? "Comparing total pill count…" : "Comparing medicines & counts…",
      async () => {
        setResult(null);
        setRecognition(null);

        const data = await api(
          totalOnly ? "/verify-total-count" : "/verify-reviewed",
          { prescriptionId: prescription.id, imageData: photo }
        );

        if (
          data?.mode !== "live" ||
          data.prescription?.id !== prescription.id ||
          typeof data.status !== "string" ||
          !validRecognition(data.recognition)
        ) {
          throw new Error("Invalid comparison response.");
        }

        if (totalOnly) {
          if (
            data.comparisonType !== "total-count" ||
            data.identitiesChecked !== false ||
            !validCount(data.expectedTotal) ||
            !validCount(data.detectedTotal) ||
            !validCount(data.lowConfidenceCount) ||
            data.lowConfidenceCount > data.detectedTotal ||
            data.difference !== data.detectedTotal - data.expectedTotal ||
            data.detectedTotal !== data.recognition.detections.length
          ) {
            throw new Error("Invalid total-count response.");
          }
        } else if (
          data.comparisonType !== "product-count" ||
          !Array.isArray(data.rows) ||
          !data.rows.every(
            (row) =>
              row &&
              typeof row.productId === "string" &&
              validCount(row.expected) &&
              validCount(row.found)
          ) ||
          !Array.isArray(data.uncertain) ||
          !data.uncertain.every(
            (item) =>
              item &&
              typeof item.label === "string" &&
              Number.isFinite(item.confidence) &&
              item.confidence >= 0 &&
              item.confidence <= 1
          )
        ) {
          throw new Error("Invalid product comparison response.");
        }

        if (!mounted.current) return;
        setRecognition(data.recognition);
        setResult(data);
        const record = { ...data };
        delete record.recognition;
        setHistory((previous) => [record, ...previous].slice(0, 200));
      }
    );
  }

  const comparisonReason = !prescription
    ? "Save a reviewed list in step 2 before comparing."
    : !photo
    ? "Choose a tray photo."
    : !modelReady
    ? "The pill model is unavailable."
    : !prescription.comparisonReady
    ? "Some medicines are unsupported. Use total-count comparison; medicine identities will not be checked."
    : "Both comparison options are available. Review all predictions.";

  return (
    <div className="med-workspace">
      <style>{REVIEW_STYLES}</style>

      <header className="mv-top">
        <div className="mv-brand">
          <span className="mv-brand-icon"><Icon kind="plus" /></span>
          <div>
            <strong>Hypertension Care</strong>
            <small>Medicine review workspace</small>
          </div>
        </div>

        <nav aria-label="Medicine workspace navigation">
          <button
            type="button"
            className={page === "workspace" ? "active" : ""}
            disabled={busy}
            onClick={() => setPage("workspace")}
            aria-current={page === "workspace" ? "page" : undefined}
          >
            <Icon kind="document" size={17} /> Workspace
          </button>
          <button
            type="button"
            className={page === "history" ? "active" : ""}
            disabled={busy}
            onClick={() => setPage("history")}
            aria-current={page === "history" ? "page" : undefined}
          >
            <Icon kind="history" size={17} /> History
          </button>
        </nav>

        <span className={`mv-connection ${connected ? "online" : ""}`}>
          <i aria-hidden="true" />
          {loading ? "Connecting" : connected ? "API connected" : "API offline"}
        </span>
      </header>

      <main className="mv-main">
        <div className="mv-heading">
          <div>
            <span className="mv-eyebrow">CAREGIVER WORKSPACE</span>
            <h1>
              {page === "history" ? "Review history" : "Every medicine. Clearly reviewed."}
            </h1>
            <p>
              {page === "history"
                ? "Saved comparisons with their comparison type."
                : "Read the prescription, review the list, then inspect the prepared tray."}
            </p>
          </div>
          <span className="mv-tag">Manual review required</span>
        </div>

        {error && <div className="mv-alert error" role="alert">{error}</div>}
        {notice && <div className="mv-alert info" role="status">{notice}</div>}
        {busy && <div className="mv-progress" role="status">{operation}</div>}

        {loading ? (
          <div className="mv-empty">Connecting to the medicine service…</div>
        ) : page === "history" ? (
          <section className="mv-panel">
            <div className="mv-panel-heading">
              <h2>Previous comparisons</h2>
              <span className="mv-tag">{history.length} records</span>
            </div>
            {!history.length ? (
              <div className="mv-empty">No saved comparisons yet.</div>
            ) : (
              <div className="mv-history">
                {history.map((record, index) => (
                  <article key={record.id || index} className="mv-history-row">
                    <span className="mv-history-icon"><Icon kind="history" /></span>
                    <div>
                      <strong>
                        {record.reference || record.prescription?.doseLabel || "Prepared tray"}
                      </strong>
                      <p className="mv-help">
                        {record.comparisonType === "total-count"
                          ? "Total count only · identities not checked"
                          : "Predicted products and counts · review required"}
                      </p>
                      {record.comparisonType === "total-count" && (
                        <p className="mv-help">
                          Expected: {record.expectedTotal} · Detected: {record.detectedTotal}
                        </p>
                      )}
                      <p className="mv-help">
                        {record.createdAt && !Number.isNaN(Date.parse(record.createdAt))
                          ? new Date(record.createdAt).toLocaleString()
                          : "Date unavailable"}
                      </p>
                    </div>
                    <span className={`mv-badge ${tone(record.status)}`}>
                      {record.status || "Review required"}
                    </span>
                  </article>
                ))}
              </div>
            )}
          </section>
        ) : (
          <>
            <nav className="mv-steps" aria-label="Verification steps">
              {STEPS.map((label, index) => (
                <button
                  type="button"
                  key={label}
                  className={step === index ? "active" : ""}
                  onClick={() => setStep(index)}
                  disabled={busy}
                  aria-current={step === index ? "step" : undefined}
                >
                  <span className="mv-step-number">0{index + 1}</span>
                  <span>{label}</span>
                  <Icon kind={["document", "check", "image"][index]} size={18} />
                </button>
              ))}
            </nav>

            {step === 0 && (
              <div className="mv-source-grid">
                <section className="mv-panel">
                  <span className="mv-eyebrow">01 / SOURCE IMAGE</span>
                  <h2>Add the prescription</h2>
                  <p className="mv-help">
                    Use a sharp image with all medicine instructions visible.
                  </p>
                  <Upload
                    image={prescriptionPhoto}
                    filename={prescriptionFilename}
                    title="Choose prescription photo"
                    onChange={(event) => loadImage(event, true)}
                    disabled={busy}
                  />
                  <button
                    type="button"
                    className="mv-primary"
                    onClick={extractPrescription}
                    disabled={busy || !connected || !prescriptionPhoto}
                  >
                    <Icon kind="document" size={18} />
                    Read prescription & create draft
                  </button>
                </section>

                <section className="mv-panel">
                  <span className="mv-eyebrow">EXTRACTED TEXT</span>
                  <h2>Check what was read</h2>
                  <p className="mv-help">
                    Correct OCR spelling or enter one medicine per line.
                  </p>
                  <label htmlFor="mv-source-text">Prescription text</label>
                  <textarea
                    id="mv-source-text"
                    rows={10}
                    maxLength={12000}
                    value={text}
                    disabled={busy}
                    placeholder="Extracted medicine lines will appear here…"
                    onChange={(event) => {
                      setText(event.target.value);
                      invalidate();
                    }}
                  />
                  <button
                    type="button"
                    className="mv-primary"
                    disabled={busy || !connected || !text.trim()}
                    onClick={() => run("Creating medicine draft…", () => createDraft(text))}
                  >
                    Create / replace medicine draft <Icon kind="arrow" size={18} />
                  </button>
                  <p className="mv-help">
                    Creating a draft replaces edited rows. It does not save a prescription.
                  </p>
                  <button
                    type="button"
                    className="mv-text-button"
                    disabled={busy}
                    onClick={() => setStep(1)}
                  >
                    Enter medicines manually instead
                  </button>

                  {ocrResult && (
                    <details className="mv-details">
                      <summary>All OCR text & reading notes</summary>
                      <pre>{ocrResult.rawText || ocrResult.text || "No text returned."}</pre>
                      {Array.isArray(ocrResult.warnings) &&
                        ocrResult.warnings.map((warning, index) => (
                          <p className="mv-help" key={index}>{String(warning)}</p>
                        ))}
                    </details>
                  )}
                </section>
              </div>
            )}

            {step === 1 && (
              <div className="mv-review-layout">
                <aside className="mv-panel mv-reference">
                  <span className="mv-eyebrow">ORIGINAL PRESCRIPTION</span>
                  <h2>Keep the source in view</h2>
                  {prescriptionPhoto ? (
                    <a href={prescriptionPhoto} target="_blank" rel="noreferrer">
                      <img
                        className="mv-reference-image"
                        src={prescriptionPhoto}
                        alt="Original prescription"
                      />
                    </a>
                  ) : (
                    <div className="mv-empty">No prescription image selected.</div>
                  )}
                  <p className="mv-help">Click the image for a closer view.</p>
                  <button
                    type="button"
                    className="mv-secondary"
                    disabled={busy}
                    onClick={() => setStep(0)}
                  >
                    Back to source & OCR text
                  </button>
                  <div className="mv-reference-note">
                    <strong>Editable autofill</strong>
                    <p>Unique exact product matches are selected automatically.</p>
                    <p>
                      Quantities require explicit tray information. Dose schedules
                      are not converted into tray quantities.
                    </p>
                    <p>
                      Unsupported medicines can be saved for total-count comparison.
                    </p>
                  </div>
                </aside>

                <section>
                  <div className="mv-review-title">
                    <div>
                      <span className="mv-eyebrow">02 / REVIEW THE DRAFT</span>
                      <h2>Your medicine list</h2>
                    </div>
                    <span className="mv-tag">{rows.length} medicines</span>
                  </div>

                  <div className="mv-metrics">
                    <div><strong>{selectedIds.length}</strong><span>Products selected</span></div>
                    <div><strong>{incompleteRows}</strong><span>Incomplete rows</span></div>
                    <div><strong>{missingStrengths}</strong><span>Strengths to check</span></div>
                  </div>

                  <fieldset className="mv-fields" disabled={busy}>
                    <legend className="mv-sr-only">Reviewed prescription details</legend>

                    <div className="mv-panel mv-pair">
                      <div>
                        <label htmlFor="mv-reference">Patient / tray reference</label>
                        <input
                          id="mv-reference"
                          maxLength={200}
                          value={reference}
                          placeholder="Optional reference"
                          onChange={(event) => {
                            setReference(event.target.value);
                            invalidate();
                          }}
                        />
                      </div>
                      <div>
                        <label htmlFor="mv-dose">Tray label</label>
                        <input
                          id="mv-dose"
                          maxLength={200}
                          value={doseLabel}
                          onChange={(event) => {
                            setDoseLabel(event.target.value);
                            invalidate();
                          }}
                        />
                      </div>
                    </div>

                    <div className="mv-panel-heading">
                      <p className="mv-help">{products.length} supported products loaded</p>
                      <button
                        type="button"
                        className="mv-secondary"
                        disabled={!connected || !rows.length}
                        onClick={autofillMissingFields}
                      >
                        Auto-fill blank fields
                      </button>
                    </div>

                    {rows.map((row, index) => (
                      <article className="mv-medicine" key={row.rowId}>
                        <div className="mv-medicine-heading">
                          <span className="mv-medicine-number">
                            {String(index + 1).padStart(2, "0")}
                          </span>
                          <div>
                            <h3>{row.medicineName.trim() || `Medicine ${index + 1}`}</h3>
                            <p>
                              {row.productId
                                ? row.matchType === "exact-text"
                                  ? "Exact text match · confirm product"
                                  : "Product selected manually"
                                : "No supported product selected"}
                            </p>
                          </div>
                          <button
                            type="button"
                            className="mv-remove"
                            aria-label={`Remove medicine ${index + 1}`}
                            onClick={() => {
                              invalidate();
                              setRows((previous) =>
                                previous.filter((item) => item.rowId !== row.rowId)
                              );
                            }}
                          >
                            Remove
                          </button>
                        </div>

                        {row.sourceText && (
                          <details className="mv-source-line">
                            <summary>Original OCR line</summary>
                            <p>{row.sourceText}</p>
                          </details>
                        )}

                        <label htmlFor={`name-${row.rowId}`}>Reviewed medicine name</label>
                        <input
                          id={`name-${row.rowId}`}
                          value={row.medicineName}
                          maxLength={200}
                          placeholder="Enter medicine name"
                          onChange={(event) =>
                            updateRow(row.rowId, "medicineName", event.target.value)
                          }
                        />

                        <div className="mv-pair">
                          <div>
                            <label htmlFor={`strength-${row.rowId}`}>
                              Recorded strength · optional
                            </label>
                            <input
                              id={`strength-${row.rowId}`}
                              value={row.strength}
                              maxLength={80}
                              placeholder="Strength on prescription"
                              onChange={(event) =>
                                updateRow(row.rowId, "strength", event.target.value)
                              }
                            />
                            <p className="mv-field-note">
                              The pill model does not verify strength.
                            </p>
                          </div>
                          <div>
                            <label htmlFor={`qty-${row.rowId}`}>Pills for this tray</label>
                            <input
                              id={`qty-${row.rowId}`}
                              type="number"
                              min="1"
                              max="100"
                              step="1"
                              value={row.quantity}
                              placeholder="Enter tray quantity"
                              onChange={(event) =>
                                updateRow(row.rowId, "quantity", event.target.value)
                              }
                            />
                            {row.quantitySource === "explicit" &&
                              quantityValid(row.quantity) && (
                                <span className="mv-autofill-note">Auto-filled · editable</span>
                              )}
                            <p className="mv-field-note">
                              {quantityValid(row.quantity)
                                ? "Confirm this count applies to the prepared tray."
                                : "Enter the intended count for this tray."}
                            </p>
                          </div>
                        </div>

                        <label htmlFor={`product-${row.rowId}`}>Exact supported product</label>
                        <select
                          id={`product-${row.rowId}`}
                          value={row.productId}
                          disabled={!connected}
                          onChange={(event) =>
                            updateRow(row.rowId, "productId", event.target.value)
                          }
                        >
                          <option value="">Not selected / unsupported</option>
                          {products.map((product) => (
                            <option key={product.id} value={product.id}>
                              {product.name} · {product.id}
                            </option>
                          ))}
                        </select>

                        {row.productId && row.matchType === "exact-text" && (
                          <span className="mv-autofill-note">Exact text match · editable</span>
                        )}

                        <p className="mv-field-note">
                          {row.productId
                            ? "Confirm the exact product against its packaging."
                            : "Leave unsupported if no exact product exists. Total-count comparison remains available."}
                        </p>

                        {!row.productId && row.suggestions?.length > 0 && (
                          <div className="mv-suggestions">
                            <small>Possible matches — check before selecting</small>
                            {row.suggestions
                              .filter((suggestion) =>
                                products.some((product) => product.id === suggestion.productId)
                              )
                              .map((suggestion) => (
                                <button
                                  type="button"
                                  key={suggestion.productId}
                                  onClick={() =>
                                    updateRow(row.rowId, "productId", suggestion.productId)
                                  }
                                >
                                  {suggestion.name}
                                </button>
                              ))}
                          </div>
                        )}
                      </article>
                    ))}

                    <button
                      type="button"
                      className="mv-add"
                      disabled={rows.length >= 50}
                      onClick={() => {
                        invalidate();
                        const newRow = freshRow();
                        setRows((previous) => [...previous, newRow]);
                      }}
                    >
                      <Icon kind="plus" size={18} /> Add medicine
                    </button>

                    <div className="mv-panel mv-save-panel">
                      {unmappedRows > 0 && (
                        <p className="mv-inline-warning">
                          {unmappedRows} unsupported/unselected product(s).
                          You can save this list and compare total counts.
                          Product-by-product comparison requires supported products.
                        </p>
                      )}
                      <label className="mv-checkbox">
                        <input
                          type="checkbox"
                          checked={reviewed}
                          onChange={(event) => {
                            setReviewed(event.target.checked);
                            setPrescription(null);
                            setResult(null);
                          }}
                        />
                        <span>
                          I reviewed names, recorded strengths and tray quantities.
                          Any selected product matches the packaging; unsupported
                          products remain unselected.
                        </span>
                      </label>
                      {saveReason && <p className="mv-field-note">{saveReason}</p>}
                      <button
                        type="button"
                        className="mv-primary"
                        disabled={!canSave}
                        onClick={savePrescription}
                      >
                        Save reviewed list & continue <Icon kind="arrow" size={18} />
                      </button>
                    </div>
                  </fieldset>
                </section>
              </div>
            )}

            {step === 2 && (
              <>
                <div className="mv-tray-layout">
                  <section className="mv-panel">
                    <span className="mv-eyebrow">03 / PREPARED TRAY</span>
                    <h2>Add your tray photo</h2>
                    <Upload
                      image={photo}
                      filename={filename}
                      title="Choose tray photo"
                      onChange={(event) => loadImage(event, false)}
                      disabled={busy}
                    />
                    <p className="mv-help">Keep pills separate, visible and in focus.</p>

                    <div className="mv-actions">
                      <button
                        type="button"
                        className="mv-secondary"
                        disabled={!canDetect}
                        onClick={detectPills}
                      >
                        Detect pills
                      </button>
                      <button
                        type="button"
                        className="mv-secondary"
                        disabled={!canCompareTotal}
                        onClick={() => compareTray(true)}
                      >
                        Compare total pill count
                      </button>
                      <button
                        type="button"
                        className="mv-primary"
                        disabled={!canVerify}
                        onClick={() => compareTray(false)}
                      >
                        Compare medicines & counts
                      </button>
                    </div>

                    <p className="mv-field-note">{comparisonReason}</p>
                    {!totalReady && (
                      <p className="mv-field-note">
                        Total-count service unavailable. Restart the API with the updated main.py.
                      </p>
                    )}
                    <p className="mv-help">
                      Total counting does not check medicine identities.
                      Local medicine recognition requires compatible trained classes.
                    </p>
                  </section>

                  <section className="mv-panel">
                    <span className="mv-eyebrow">REVIEWED LIST</span>
                    <h2>{prescription?.doseLabel || doseLabel || "Prepared tray"}</h2>
                    {!prescription ? (
                      <div className="mv-empty">No reviewed list saved yet.</div>
                    ) : (
                      <div className="mv-mini-list">
                        {prescription.items.map((item, index) => (
                          <div key={index}>
                            <span>
                              <strong>{item.medicineName || productName(item.productId)}</strong>
                              <small>{item.strength || "Strength not recorded"}</small>
                              {!item.productId && <small>Unsupported · total count only</small>}
                            </span>
                            <b>× {item.quantity}</b>
                          </div>
                        ))}
                      </div>
                    )}
                    <button
                      type="button"
                      className="mv-text-button"
                      disabled={busy}
                      onClick={() => setStep(1)}
                    >
                      Edit reviewed medicine list
                    </button>
                  </section>
                </div>

                {result?.comparisonType === "total-count" && (
                  <section className="mv-panel mv-result mv-count-only" aria-live="polite">
                    <div className="mv-panel-heading">
                      <div>
                        <span className="mv-eyebrow">TOTAL COUNT ONLY</span>
                        <h2>Tray count comparison</h2>
                      </div>
                      <span className="mv-badge uncertain">Identities not checked</span>
                    </div>
                    <div className="mv-metrics">
                      <div><strong>{result.expectedTotal}</strong><span>Expected total</span></div>
                      <div><strong>{result.detectedTotal}</strong><span>Detected objects</span></div>
                      <div>
                        <strong>{result.difference > 0 ? "+" : ""}{result.difference}</strong>
                        <span>Detected minus expected</span>
                      </div>
                    </div>
                    <div className="mv-alert info">
                      <strong>{result.status}</strong>
                      <p>
                        {result.difference === 0
                          ? "The totals are equal. This does not confirm that the correct medicines are present."
                          : result.difference < 0
                          ? `${Math.abs(result.difference)} fewer objects were detected than expected. Inspect for missed pills.`
                          : `${result.difference} more objects were detected than expected. Inspect for extra pills or incorrect detections.`}
                      </p>
                    </div>
                    {result.lowConfidenceCount > 0 && (
                      <div className="mv-alert warning">
                        <strong>{result.lowConfidenceCount} low-confidence detection(s) included</strong>
                        <p>These remain in the displayed total. Review every bounding box.</p>
                      </div>
                    )}
                    <p className="mv-help">{result.notes}</p>
                  </section>
                )}

                {result?.comparisonType === "product-count" && (
                  <section className="mv-panel mv-result" aria-live="polite">
                    <div className="mv-panel-heading">
                      <div>
                        <span className="mv-eyebrow">PREDICTED PRODUCTS & COUNTS</span>
                        <h2>Tray review results</h2>
                      </div>
                      <span className={`mv-badge ${tone(result.status)}`}>{result.status}</span>
                    </div>
                    <p className="mv-help">{result.notes}</p>
                    <div className="mv-metrics">
                      <div>
                        <strong>{result.rows.reduce((sum, row) => sum + row.expected, 0)}</strong>
                        <span>Expected pills</span>
                      </div>
                      <div>
                        <strong>{result.rows.reduce((sum, row) => sum + row.found, 0)}</strong>
                        <span>Counted predictions</span>
                      </div>
                      <div>
                        <strong>{result.rows.filter((row) => row.expected !== row.found).length}</strong>
                        <span>Rows with differences</span>
                      </div>
                    </div>
                    {result.uncertain.length > 0 && (
                      <div className="mv-alert warning">
                        <strong>Uncertain detections are excluded from product counts.</strong>
                        <ul>
                          {result.uncertain.map((item, index) => (
                            <li key={index}>
                              {productName(item.label)} · {(item.confidence * 100).toFixed(1)}%
                              {item.reason ? ` · ${item.reason}` : ""}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    <div className="mv-result-grid">
                      {result.rows.map((row, index) => {
                        const difference = row.found - row.expected;
                        const rowTone = difference !== 0
                          ? "difference"
                          : result.uncertain.length ? "uncertain" : "match";
                        return (
                          <article className={`mv-result-card ${rowTone}`} key={`${row.productId}-${index}`}>
                            <span className={`mv-badge ${rowTone}`}>
                              {difference < 0
                                ? `${-difference} fewer predicted`
                                : difference > 0
                                ? `${difference} extra predicted`
                                : "Counts equal · review required"}
                            </span>
                            <h3>{row.medicineName || productName(row.productId)}</h3>
                            <p className="mv-help">{productName(row.productId)}</p>
                            {row.strength && (
                              <p className="mv-help">Recorded strength: {row.strength} · not verified</p>
                            )}
                            <div className="mv-counts">
                              <span><small>Expected</small><strong>{row.expected}</strong></span>
                              <span><small>Predicted</small><strong>{row.found}</strong></span>
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  </section>
                )}

                <section className="mv-panel" aria-live="polite" aria-busy={busy}>
                  <span className="mv-eyebrow">MODEL OUTPUT</span>
                  <h2>
                    {recognition
                      ? `${recognition.detections.length} detections to review`
                      : "Pill recognition"}
                  </h2>
                  {!recognition ? (
                    <div className="mv-empty">Upload a tray photo and choose an action.</div>
                  ) : (
                    <>
                      <p className="mv-inline-warning">
                        Predictions are not confirmed identities. Confidence is a model
                        score, not a correctness guarantee.
                        {!result && " No prescription comparison has been performed."}
                      </p>
                      <img
                        className="mv-detection-image"
                        src={recognition.annotatedImage}
                        alt="Model predictions with bounding boxes"
                      />
                      {!recognition.detections.length ? (
                        <p className="mv-help">
                          No detections returned. This does not confirm an empty tray.
                        </p>
                      ) : (
                        <div className="mv-detections">
                          {recognition.detections.map((item, index) => (
                            <div key={`${item.label}-${index}`}>
                              <span className="mv-detection-number">{index + 1}</span>
                              <span>
                                <strong>{item.productName || productName(item.label)}</strong>
                                <small>
                                  {item.label} · {item.unmapped ? "Unsupported class" : "Predicted identity"}
                                </small>
                              </span>
                              <b>{(item.confidence * 100).toFixed(1)}%</b>
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </section>
              </>
            )}
          </>
        )}

        <footer className="mv-footer">
          Review medicine identity, strength and instructions against the original
          prescription and packaging before administration.
        </footer>
      </main>
    </div>
  );
}