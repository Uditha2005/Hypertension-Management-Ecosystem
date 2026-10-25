import React, { useCallback, useEffect, useState } from "react";
import { getApiErrorMessage, getNutritionContext } from "../services/nutritionApi";
import "./Component3MealHistory.css";

const prettyDate = (value) => {
  if (!value) return "Date not recorded";
  const parsed = new Date(`${value}T12:00:00`);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
};
const nutrient = (value, unit) => value == null ? "Not available" : `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 })} ${unit}`;

export default function Component3MealHistory() {
  const [days, setDays] = useState(7);
  const [context, setContext] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(false);
  const refresh = useCallback(async () => {
    setBusy(true); setError("");
    try { setContext(await getNutritionContext(days)); }
    catch (err) { setError(getApiErrorMessage(err)); }
    finally { setBusy(false); }
  }, [days]);
  useEffect(() => { refresh(); }, [refresh]);
  const feedback = context?.feedback_counts || {};
  const records = context?.records || [];
  return (
    <section className="ci3-history" aria-labelledby="ci3-history-heading">
      <div className="ci3-history-heading-row">
        <div><p className="ci3-eyebrow">FOLLOW-UP</p><h2 id="ci3-history-heading">Meal history & feedback</h2><p className="ci3-muted">Review saved analyses and see whether recommendations were useful.</p></div>
        <button type="button" className="ci3-button ci3-button-secondary" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}>{expanded ? "Hide history" : "View history"}</button>
      </div>
      <div className="ci3-history-controls">
        <label>Period <select value={days} onChange={(event) => setDays(Number(event.target.value))}><option value={7}>Last 7 days</option><option value={14}>Last 14 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option></select></label>
        <button type="button" className="ci3-text-button" onClick={refresh} disabled={busy}>{busy ? "Refreshing…" : "Refresh"}</button>
      </div>
      {error && <p className="ci3-history-error" role="alert">{error}</p>}
      {context && <>
        <div className="ci3-history-stats">
          <div><strong>{context.record_count}</strong><span>Saved analyses</span></div>
          <div><strong>{context.feedback_count}</strong><span>Feedback responses</span></div>
          <div><strong>{feedback.helpful || 0}</strong><span>Helpful</span></div>
          <div><strong>{feedback.tried || 0}</strong><span>Recommendations tried</span></div>
        </div>
        {Object.keys(context.daily_recorded_nutrients || {}).length > 0 && <div className="ci3-history-daily"><h3>Recorded nutrient totals</h3><p className="ci3-muted">Only values present in saved analyses are shown; these may not represent complete daily intake.</p><div className="ci3-history-table-wrap"><table><thead><tr><th>Date</th><th>Sodium</th><th>Potassium</th><th>Energy</th><th>Saturated fat</th></tr></thead><tbody>{Object.entries(context.daily_recorded_nutrients).sort(([a],[b]) => b.localeCompare(a)).map(([date, values]) => <tr key={date}><td>{prettyDate(date)}</td><td>{nutrient(values.sodium_mg, "mg")}</td><td>{nutrient(values.potassium_mg, "mg")}</td><td>{nutrient(values.energy_kcal, "kcal")}</td><td>{nutrient(values.sat_fat_g, "g")}</td></tr>)}</tbody></table></div></div>}
        {expanded && <div className="ci3-history-records"><h3>Saved meal analyses</h3>{records.length === 0 ? <p>No saved analyses were found for this period.</p> : records.map((record) => {
          const foods = Array.isArray(record.meals) ? record.meals : [];
          const analysis = record.analysis || {};
          return <details className="ci3-history-record" key={record.record_id}><summary><span>{prettyDate(record.meal_date)}</span><span>{foods.length} food entries</span><span>{record.record_id ? record.record_id.slice(0, 8) : "Record"}</span></summary><div className="ci3-history-record-body"><p><strong>Foods recorded:</strong> {foods.length ? foods.map((food) => `${food.description || "Food"}${food.quantity != null ? ` (${food.quantity} ${food.unit || ""})` : ""}`).join(", ") : "No food details saved"}</p><p><strong>Nutrition goal:</strong> {record.profile_context?.nutrition_goal || "Not recorded"}</p>{Object.entries(analysis.meal_assessments || {}).map(([meal, assessment]) => <div key={meal}><strong>{meal}</strong><ul>{(assessment.suggestions || []).map((item, index) => <li key={index}>{typeof item === "string" ? item : `${item.title}: ${item.text}`}</li>)}</ul></div>)}</div></details>;
        })}</div>}
      </>}
      <p className="ci3-history-note">{context?.limitation || "History is limited to records available to the current prototype profile."}</p>
    </section>
  );
}
