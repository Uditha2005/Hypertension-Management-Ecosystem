import React, { useState } from "react";
import axios from "axios";

const API_BASE_URL = (
  process.env.REACT_APP_API_URL || "http://127.0.0.1:5000"
).replace(/\/+$/, "");

const initialForm = {
  age: "68",
  sex: "female",
  systolic_bp: "142",
  diastolic_bp: "84",
  pulse_rate: "68",
  height_cm: "158",
  weight_kg: "82",
  diabetes_history: "false",
  has_existing_hypertension: "false",
};

const getSourceUrl = (source) =>
  source?.match(/https?:\/\/\S+/)?.[0] || "";

function PhysiologicalRecommendations() {
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const updateField = (event) => {
    const { name, value } = event.target;

    setForm((current) => ({
      ...current,
      [name]: value,
    }));
  };

  const submitAssessment = async (event) => {
    event.preventDefault();

    setLoading(true);
    setError("");
    setResult(null);

    const payload = {
      age: Number(form.age),
      sex: form.sex,
      systolic_bp: Number(form.systolic_bp),
      diastolic_bp: Number(form.diastolic_bp),
      pulse_rate: Number(form.pulse_rate),
      height_cm: Number(form.height_cm),
      weight_kg: Number(form.weight_kg),
      diabetes_history: form.diabetes_history === "true",
      has_existing_hypertension:
        form.has_existing_hypertension === "true",
    };

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/component1/predict`,
        payload,
        { timeout: 25000 }
      );

      setResult(response.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const serverMessage = err.response?.data?.message;

      setError(
        Array.isArray(detail)
          ? detail.map((item) => item.msg || "Invalid input").join("; ")
          : detail || serverMessage || err.message ||
              "Unable to obtain an assessment. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  const features = result?.shap_explanation?.features || [];
  const recommendations = result?.recommendations || [];
  const warnings = result?.domain_warnings || [];
  const hasScore = typeof result?.model_score_percent === "number";

  return (
    <main className="physiological-ai">
      <style>{`
        .physiological-ai {
          --ink: #192d31;
          --muted: #6e7f80;
          --line: #d8e5df;
          --teal: #167d72;
          --teal-dark: #10594f;
          min-height: 100vh;
          padding: clamp(20px, 4vw, 52px);
          color: var(--ink);
          background: linear-gradient(
            135deg, #eaf3ef 0%, #f8f8f2 55%, #f4ede3 100%
          );
          font-family: Arial, sans-serif;
        }

        .physiological-ai * { box-sizing: border-box; }

        .phys-shell {
          max-width: 1180px;
          margin: 0 auto;
        }

        .phys-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 20px;
          margin-bottom: 26px;
        }

        .phys-kicker {
          margin: 0 0 12px;
          color: var(--teal);
          font-size: .72rem;
          font-weight: 700;
          letter-spacing: .13em;
          text-transform: uppercase;
        }

        .phys-title {
          max-width: 760px;
          margin: 0;
          font-family: Georgia, "Times New Roman", serif;
          font-size: clamp(2rem, 4vw, 3.5rem);
          font-weight: 400;
          line-height: 1.08;
        }

        .phys-intro {
          max-width: 690px;
          margin: 14px 0 0;
          color: var(--muted);
          font-size: .95rem;
          line-height: 1.7;
        }

        .phys-badge {
          flex-shrink: 0;
          padding: 9px 12px;
          border: 1px solid #b7d8cc;
          border-radius: 999px;
          color: #176c5d;
          background: #e1f1e9;
          font-size: .69rem;
          font-weight: 700;
          letter-spacing: .04em;
        }

        .phys-notice {
          margin-bottom: 22px;
          padding: 15px 17px;
          border: 1px solid #e5d5b2;
          border-radius: 12px;
          color: #715a30;
          background: #fff9eb;
          font-size: .83rem;
          line-height: 1.6;
        }

        .phys-layout {
          display: grid;
          grid-template-columns: minmax(280px, .9fr) minmax(0, 1.1fr);
          align-items: start;
          gap: 20px;
        }

        .phys-card {
          min-width: 0;
          padding: clamp(17px, 2.5vw, 27px);
          border: 1px solid var(--line);
          border-radius: 16px;
          background: rgba(255,255,255,.94);
          box-shadow: 0 12px 32px rgba(35, 70, 59, .06);
        }

        .phys-card h2 {
          margin: 0;
          font-family: Georgia, "Times New Roman", serif;
          font-size: 1.55rem;
          font-weight: 400;
        }

        .phys-card-intro {
          margin: 8px 0 23px;
          color: var(--muted);
          font-size: .8rem;
          line-height: 1.6;
        }

        .phys-fields {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 16px 13px;
        }

        .phys-field {
          display: flex;
          min-width: 0;
          flex-direction: column;
          gap: 7px;
        }

        .phys-field.full { grid-column: 1 / -1; }

        .phys-field label {
          font-size: .78rem;
          font-weight: 700;
        }

        .phys-field input,
        .phys-field select {
          width: 100%;
          min-width: 0;
          min-height: 44px;
          padding: 10px 11px;
          border: 1px solid #cbdad3;
          border-radius: 8px;
          outline-offset: 2px;
          color: var(--ink);
          background: #fff;
          font: inherit;
          font-size: .88rem;
        }

        .phys-field input:focus,
        .phys-field select:focus {
          border-color: var(--teal);
          outline-color: #8fc5b5;
        }

        .phys-help {
          color: var(--muted);
          font-size: .7rem;
          line-height: 1.5;
        }

        .phys-submit {
          width: 100%;
          min-height: 48px;
          margin-top: 23px;
          padding: 12px 16px;
          border: 0;
          border-radius: 9px;
          color: white;
          background: linear-gradient(135deg, #197f73, #105a52);
          font-size: .84rem;
          font-weight: 700;
          cursor: pointer;
          transition: opacity .15s ease;
        }

        .phys-submit:hover { opacity: .92; }
        .phys-submit:disabled { opacity: .6; cursor: wait; }

        .phys-error {
          margin-top: 15px;
          padding: 12px;
          border: 1px solid #e7b9b2;
          border-radius: 8px;
          color: #963d35;
          background: #fff0ed;
          font-size: .82rem;
          line-height: 1.6;
          overflow-wrap: anywhere;
        }

        .phys-empty {
          display: grid;
          min-height: 290px;
          align-content: center;
          justify-items: center;
          padding: 30px;
          text-align: center;
          color: var(--muted);
        }

        .phys-empty-symbol {
          display: grid;
          width: 58px;
          height: 58px;
          margin-bottom: 16px;
          place-items: center;
          border-radius: 18px;
          color: var(--teal);
          background: #e4f2eb;
          font-size: 1.3rem;
          font-weight: 700;
        }

        .phys-empty h3 {
          margin: 0 0 9px;
          color: var(--ink);
          font-family: Georgia, "Times New Roman", serif;
          font-size: 1.3rem;
          font-weight: 400;
        }

        .phys-empty p {
          max-width: 330px;
          margin: 0;
          font-size: .82rem;
          line-height: 1.65;
        }

        .phys-result-head {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 19px;
        }

        .phys-result-head h2 { margin: 0; }

        .phys-status {
          display: inline-block;
          max-width: 100%;
          margin-top: 7px;
          padding: 5px 8px;
          border-radius: 5px;
          color: #176c5d;
          background: #e1f1e9;
          font-size: .68rem;
          font-weight: 700;
          overflow-wrap: anywhere;
        }

        .phys-score-box {
          margin-bottom: 23px;
          padding: 20px;
          border: 1px solid #cce3d8;
          border-radius: 12px;
          background: linear-gradient(135deg, #eff8f2, #f9fbf6);
        }

        .phys-score-label {
          color: var(--muted);
          font-size: .7rem;
          font-weight: 700;
          letter-spacing: .07em;
          text-transform: uppercase;
        }

        .phys-score {
          margin: 7px 0 11px;
          color: var(--teal-dark);
          font-family: Georgia, "Times New Roman", serif;
          font-size: 3.2rem;
          line-height: 1.05;
          overflow-wrap: anywhere;
        }

        .phys-score-note {
          margin: 0;
          color: #576c66;
          font-size: .78rem;
          line-height: 1.65;
        }

        .phys-result-section {
          margin-top: 24px;
          padding-top: 21px;
          border-top: 1px solid var(--line);
        }

        .phys-result-section h3 {
          margin: 0 0 9px;
          font-family: Georgia, "Times New Roman", serif;
          font-size: 1.25rem;
          font-weight: 400;
        }

        .phys-section-note {
          margin: 0 0 15px;
          color: var(--muted);
          font-size: .77rem;
          line-height: 1.6;
        }

        .phys-feature {
          padding: 13px 0;
          border-bottom: 1px solid #edf1ed;
        }

        .phys-feature:last-child { border-bottom: 0; }

        .phys-feature-top {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 12px;
        }

        .phys-feature-name {
          font-size: .82rem;
          font-weight: 700;
        }

        .phys-feature-value {
          margin-top: 5px;
          color: var(--muted);
          font-size: .73rem;
        }

        .phys-contribution {
          flex-shrink: 0;
          text-align: right;
          font-size: .76rem;
          font-weight: 700;
        }

        .phys-up { color: #ad5b35; }
        .phys-down { color: #267a63; }

        .phys-rec {
          margin-top: 12px;
          padding: 15px;
          border: 1px solid #e0e9e3;
          border-radius: 10px;
          background: #fbfcf9;
        }

        .phys-rec h4 {
          margin: 0 0 8px;
          font-size: .88rem;
          line-height: 1.5;
        }

        .phys-rec p {
          margin: 7px 0 0;
          color: #536964;
          font-size: .78rem;
          line-height: 1.65;
          overflow-wrap: anywhere;
        }

        .phys-rec strong { color: var(--ink); }

        .phys-rec a {
          color: #146b60;
          overflow-wrap: anywhere;
        }

        .phys-warning {
          margin-top: 11px;
          padding: 12px;
          border-left: 3px solid #c98b36;
          border-radius: 5px;
          color: #76572c;
          background: #fff7e8;
          font-size: .78rem;
          line-height: 1.6;
          overflow-wrap: anywhere;
        }

        .phys-warning ul {
          margin: 8px 0 0;
          padding-left: 20px;
        }

        @media (max-width: 860px) {
          .phys-layout { grid-template-columns: 1fr; }
          .phys-header { flex-direction: column; }
        }

        @media (max-width: 470px) {
          .phys-fields { grid-template-columns: 1fr; }
          .phys-field.full { grid-column: auto; }
          .phys-feature-top { flex-direction: column; }
          .phys-contribution { text-align: left; }
        }
      `}</style>

      <div className="phys-shell">
        <header className="phys-header">
          <div>
            <p className="phys-kicker">
              Component 1 / Explainable physiological intelligence
            </p>
            <h1 className="phys-title">
              Personalized physiological recommendations
            </h1>
            <p className="phys-intro">
              Enter a resident&apos;s physiological measurements to request a
              research-model assessment, review the SHAP explanation, and
              explore personalized wellness guidance.
            </p>
          </div>

          <span className="phys-badge">RESEARCH PROTOTYPE</span>
        </header>

        <div className="phys-notice">
          <strong>Important limitation:</strong> This prototype uses a
          historical research dataset. Its model score is not a clinically
          validated individual risk probability or a diagnosis. The current
          model has a restricted training eligibility range; unsupported
          inputs may not receive a score.
        </div>

        <div className="phys-layout">
          <section className="phys-card">
            <h2>Resident measurements</h2>
            <p className="phys-card-intro">
              Enter the available measurements and submit them to the AI
              service. Use verified measurements and recorded history.
            </p>

            <form onSubmit={submitAssessment}>
              <div className="phys-fields">
                <div className="phys-field">
                  <label htmlFor="phys-age">Age (years)</label>
                  <input
                    id="phys-age"
                    name="age"
                    type="number"
                    min="60"
                    max="120"
                    step="1"
                    value={form.age}
                    onChange={updateField}
                    required
                  />
                  <span className="phys-help">
                    The resident form supports ages 60–120. The current research
                    model is eligible only for ages 60–74.
                  </span>
                </div>

                <div className="phys-field">
                  <label htmlFor="phys-sex">Sex</label>
                  <select
                    id="phys-sex"
                    name="sex"
                    value={form.sex}
                    onChange={updateField}
                    required
                  >
                    <option value="female">Female</option>
                    <option value="male">Male</option>
                  </select>
                </div>

                <div className="phys-field">
                  <label htmlFor="phys-sbp">Systolic blood pressure (mmHg)</label>
                  <input
                    id="phys-sbp"
                    name="systolic_bp"
                    type="number"
                    min="50"
                    max="300"
                    step="1"
                    value={form.systolic_bp}
                    onChange={updateField}
                    required
                  />
                </div>

                <div className="phys-field">
                  <label htmlFor="phys-dbp">Diastolic blood pressure (mmHg)</label>
                  <input
                    id="phys-dbp"
                    name="diastolic_bp"
                    type="number"
                    min="30"
                    max="200"
                    step="1"
                    value={form.diastolic_bp}
                    onChange={updateField}
                    required
                  />
                </div>

                <div className="phys-field">
                  <label htmlFor="phys-pulse">Pulse rate (BPM)</label>
                  <input
                    id="phys-pulse"
                    name="pulse_rate"
                    type="number"
                    min="20"
                    max="250"
                    step="1"
                    value={form.pulse_rate}
                    onChange={updateField}
                    required
                  />
                </div>

                <div className="phys-field">
                  <label htmlFor="phys-height">Height (cm)</label>
                  <input
                    id="phys-height"
                    name="height_cm"
                    type="number"
                    min="80"
                    max="250"
                    step="0.1"
                    value={form.height_cm}
                    onChange={updateField}
                    required
                  />
                </div>

                <div className="phys-field">
                  <label htmlFor="phys-weight">Weight (kg)</label>
                  <input
                    id="phys-weight"
                    name="weight_kg"
                    type="number"
                    min="20"
                    max="350"
                    step="0.1"
                    value={form.weight_kg}
                    onChange={updateField}
                    required
                  />
                </div>

                <div className="phys-field">
                  <label htmlFor="phys-diabetes">Diabetes history</label>
                  <select
                    id="phys-diabetes"
                    name="diabetes_history"
                    value={form.diabetes_history}
                    onChange={updateField}
                    required
                  >
                    <option value="false">No recorded history</option>
                    <option value="true">History reported</option>
                  </select>
                </div>

                <div className="phys-field full">
                  <label htmlFor="phys-existing">
                    Existing hypertension diagnosis
                  </label>
                  <select
                    id="phys-existing"
                    name="has_existing_hypertension"
                    value={form.has_existing_hypertension}
                    onChange={updateField}
                    required
                  >
                    <option value="false">No known diagnosis</option>
                    <option value="true">Already diagnosed</option>
                  </select>
                  <span className="phys-help">
                    Residents with an existing diagnosis follow a separate
                    pathway from the model&apos;s research prediction.
                  </span>
                </div>
              </div>

              <button className="phys-submit" type="submit" disabled={loading}>
                {loading ? "Assessing measurements..." : "Generate AI assessment"}
              </button>
            </form>

            {error && (
              <div className="phys-error" role="alert">
                <strong>Assessment failed.</strong> {error}
                <p>
                  Check that the Express backend and Python AI service are
                  running, then try again.
                </p>
              </div>
            )}
          </section>

          <section className="phys-card" aria-live="polite">
            {!result && (
              <div className="phys-empty">
                <div className="phys-empty-symbol">XAI</div>
                <h3>Your assessment will appear here</h3>
                <p>
                  Submit the resident&apos;s measurements to view the model
                  output, feature contributions, and returned recommendations.
                </p>
              </div>
            )}

            {result && (
              <>
                <div className="phys-result-head">
                  <div>
                    <h2>AI assessment</h2>
                    <span className="phys-status">
                      {String(result.status || "Response received").replace(
                        /_/g,
                        " "
                      )}
                    </span>
                  </div>
                </div>

                {hasScore ? (
                  <div className="phys-score-box">
                    <div className="phys-score-label">
                      {result.model_name || "Model"} output
                    </div>
                    <div className="phys-score">
                      {result.model_score_percent.toFixed(2)}%
                    </div>
                    <p className="phys-score-note">
                      {result.score_interpretation ||
                        "This is a research-model output, not a diagnosis."}
                    </p>
                  </div>
                ) : (
                  <div className="phys-warning">
                    <strong>No model score was returned.</strong>
                    <p>
                      The service may have routed this input outside the
                      model&apos;s research eligibility criteria. Review the
                      status and warnings below rather than interpreting this
                      as a low-risk result.
                    </p>
                  </div>
                )}

                {warnings.length > 0 && (
                  <div className="phys-warning">
                    <strong>Domain warnings</strong>
                    <ul>
                      {warnings.map((warning, index) => (
                        <li key={index}>
                          {typeof warning === "string"
                            ? warning
                            : warning.message ||
                              warning.detail ||
                              JSON.stringify(warning)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <section className="phys-result-section">
                  <h3>What influenced the model output?</h3>
                  <p className="phys-section-note">
                    SHAP contributions explain how the features influenced
                    this model&apos;s output. They do not establish medical
                    causation or show that changing a feature will produce
                    the same change in a person&apos;s health.
                  </p>

                  {features.length === 0 ? (
                    <p className="phys-section-note">
                      No SHAP feature contributions were returned for this
                      assessment.
                    </p>
                  ) : (
                    features.map((feature) => {
                      const contribution = Number(
                        feature.contribution_percentage_points
                      );
                      const isPositive = contribution >= 0;

                      return (
                        <article className="phys-feature" key={feature.feature}>
                          <div className="phys-feature-top">
                            <div>
                              <div className="phys-feature-name">
                                {feature.label || feature.feature}
                              </div>
                              <div className="phys-feature-value">
                                Entered/model value:{" "}
                                {typeof feature.value === "number"
                                  ? feature.value.toLocaleString(undefined, {
                                      maximumFractionDigits: 2,
                                    })
                                  : String(feature.value)}
                              </div>
                            </div>

                            {Number.isFinite(contribution) && (
                              <div
                                className={`phys-contribution ${
                                  isPositive ? "phys-up" : "phys-down"
                                }`}
                              >
                                {isPositive ? "+" : ""}
                                {contribution.toFixed(2)} points
                              </div>
                            )}
                          </div>

                          <p className="phys-section-note" style={{ margin: "8px 0 0" }}>
                            {feature.direction === "increases_model_output"
                              ? "Pushes the model output upward."
                              : feature.direction === "decreases_model_output"
                              ? "Pushes the model output downward."
                              : "Contribution direction not specified."}
                          </p>
                        </article>
                      );
                    })
                  )}
                </section>

                <section className="phys-result-section">
                  <h3>Personalized wellness recommendations</h3>
                  <p className="phys-section-note">
                    These are general guidance items returned by the
                    prototype. Individual care decisions should follow the
                    resident&apos;s clinical plan and healthcare professional&apos;s
                    advice.
                  </p>

                  {recommendations.length === 0 ? (
                    <p className="phys-section-note">
                      No recommendations were returned for this assessment.
                    </p>
                  ) : (
                    recommendations.map((item, index) => {
                      const sourceUrl = getSourceUrl(item.source);
                      const sourceLabel = sourceUrl
                        ? item.source.replace(sourceUrl, "").replace(/:\s*$/, "").trim()
                        : item.source;

                      return (
                        <article className="phys-rec" key={`${item.title}-${index}`}>
                          <h4>{item.title}</h4>
                          {item.reason && (
                            <p>
                              <strong>Why:</strong> {item.reason}
                            </p>
                          )}
                          {item.action && (
                            <p>
                              <strong>Suggested action:</strong> {item.action}
                            </p>
                          )}
                          {item.source && (
                            <p>
                              <strong>Source: </strong>
                              {sourceUrl ? (
                                <a
                                  href={sourceUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  {sourceLabel || sourceUrl}
                                </a>
                              ) : (
                                item.source
                              )}
                            </p>
                          )}
                        </article>
                      );
                    })
                  )}
                </section>

                {result.shap_explanation?.reconstruction_verified && (
                  <p className="phys-section-note" style={{ marginTop: 20 }}>
                    <strong>Explanation check:</strong> the SHAP contribution
                    reconstruction was verified by the prediction service.
                  </p>
                )}
              </>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}

export default PhysiologicalRecommendations;