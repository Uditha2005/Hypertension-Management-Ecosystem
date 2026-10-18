import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  analyzeMealPlan,
  checkNutritionApiHealth,
  getApiErrorMessage,
  searchFoods,
} from "../services/nutritionApi";
import "./NutritionalIntelligence.css";

const MEALS = ["Breakfast", "Lunch", "Dinner", "Snacks"];
const UNITS = [
  { value: "g", label: "grams (g)" },
  { value: "kg", label: "kilograms (kg)" },
  { value: "serving", label: "serving(s) as defined by USDA" },
];

const dateString = (date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};
const today = dateString(new Date());
const newEntry = (day, meal = "Breakfast") => ({
  rowId: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
  day,
  meal,
  fdc_id: "",
  description: "",
  quantity: "",
  unit: "g",
  servingNote: "",
});

const nutrients = [
  ["sodium_mg", "Sodium", "mg"],
  ["potassium_mg", "Potassium", "mg"],
  ["energy_kcal", "Energy", "kcal"],
  ["sat_fat_g", "Saturated fat", "g"],
  ["na_k_ratio", "Sodium : potassium", "ratio"],
];

function displayValue(value, key) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "Unknown";
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: key === "na_k_ratio" ? 3 : 1,
  });
}

function NutrientGrid({ summary }) {
  return (
    <div className="ci3-metric-grid">
      {nutrients.map(([key, label, unit]) => (
        <div className="ci3-metric" key={key}>
          <span>{label}</span>
          <strong>{displayValue(summary?.[key], key)}</strong>
          <small>{unit}</small>
        </div>
      ))}
    </div>
  );
}

function Stepper({ step }) {
  return (
    <nav className="ci3-stepper" aria-label="Nutrition plan progress">
      {["Setup", "Build meals", "Review nutrition"].map((label, index) => {
        const number = index + 1;
        return (
          <React.Fragment key={label}>
            <span className={`ci3-step-item ${step === number ? "active" : ""} ${step > number ? "complete" : ""}`}>
              <b>{step > number ? "✓" : number}</b><span>{label}</span>
            </span>
            {number < 3 && <span className={`ci3-step-line ${step > number ? "complete" : ""}`} aria-hidden="true" />}
          </React.Fragment>
        );
      })}
    </nav>
  );
}

function formatDay(day) {
  return new Date(`${day}T12:00:00`).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

function EntryEditor({ entry, onChange, onRemove }) {
  return (
    <article className="ci3-entry">
      <div className="ci3-entry-top">
        <div><strong>{entry.description || "New food"}</strong>{entry.fdc_id && <small>USDA record {entry.fdc_id}</small>}</div>
        <button type="button" className="ci3-remove-button" onClick={() => onRemove(entry.rowId)}>Remove</button>
      </div>
      <div className="ci3-entry-grid">
        <label>Food name
          <input value={entry.description} onChange={(event) => onChange(entry.rowId, "description", event.target.value)} placeholder="Search or describe this food" />
        </label>
        <label>Quantity
          <input aria-label={`Quantity for ${entry.description || "food"}`} type="number" min="0.01" max="100000" step="any" value={entry.quantity} onChange={(event) => onChange(entry.rowId, "quantity", event.target.value)} placeholder="e.g. 100" />
        </label>
        <label>Unit
          <select value={entry.unit} onChange={(event) => onChange(entry.rowId, "unit", event.target.value)}>
            {UNITS.map((unit) => <option value={unit.value} key={unit.value}>{unit.label}</option>)}
          </select>
        </label>
        {entry.servingNote && <p className="ci3-serving-note">{entry.servingNote}</p>}
      </div>
    </article>
  );
}

export default function NutritionalIntelligence() {
  const [step, setStep] = useState(1);
  const [apiState, setApiState] = useState("checking");
  const [apiMessage, setApiMessage] = useState("Checking API connection...");
  const [age, setAge] = useState("");
  const [sexFemale, setSexFemale] = useState("1");
  const [bmi, setBmi] = useState("");
  const [selectedDays, setSelectedDays] = useState([today]);
  const [newDay, setNewDay] = useState(today);
  const [activeDay, setActiveDay] = useState(today);
  const [activeMeal, setActiveMeal] = useState("Breakfast");
  const [entries, setEntries] = useState([]);
  const [query, setQuery] = useState("");
  const [foodResults, setFoodResults] = useState([]);
  const [searchError, setSearchError] = useState("");
  const [searchMessage, setSearchMessage] = useState("");
  const [searching, setSearching] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [analysisError, setAnalysisError] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const searchSequence = useRef(0);

  const checkHealth = useCallback(async () => {
    setApiState("checking");
    try {
      const data = await checkNutritionApiHealth();
      setApiState("online");
      setApiMessage(`${data.service || "Nutrition API"} connected`);
    } catch (error) {
      setApiState("offline");
      setApiMessage(getApiErrorMessage(error));
    }
  }, []);
  useEffect(() => { checkHealth(); }, [checkHealth]);

  const activeEntries = useMemo(() => entries.filter((entry) => entry.day === activeDay && entry.meal === activeMeal), [entries, activeDay, activeMeal]);

  const changeEntry = (rowId, field, value) => {
    setEntries((current) => current.map((entry) => entry.rowId === rowId ? { ...entry, [field]: value } : entry));
    setAnalysis(null);
  };
  const addDay = () => {
    if (!newDay || selectedDays.includes(newDay)) return;
    setSelectedDays((current) => [...current, newDay].sort());
    setActiveDay(newDay);
    setAnalysis(null);
  };
  const removeDay = (day) => {
    if (selectedDays.length === 1) return;
    setSelectedDays((current) => current.filter((item) => item !== day));
    setEntries((current) => current.filter((entry) => entry.day !== day));
    if (activeDay === day) setActiveDay(selectedDays.find((item) => item !== day) || today);
    setAnalysis(null);
  };
  const removeEntry = (rowId) => {
    setEntries((current) => current.filter((entry) => entry.rowId !== rowId));
    setAnalysis(null);
  };

  const runFoodSearch = async (event) => {
    event.preventDefault();
    const trimmed = query.trim();
    setSearchError(""); setSearchMessage(""); setFoodResults([]);
    if (!trimmed) { setSearchError("Enter a food to search, such as oats, rice, eggs, vegetables, or lentils."); return; }
    const requestId = ++searchSequence.current;
    setSearching(true);
    try {
      const result = await searchFoods(trimmed, 10);
      if (requestId !== searchSequence.current) return;
      const foods = result.foods || [];
      setFoodResults(foods);
      setSearchMessage(foods.length ? `${foods.length} USDA records found. Choose the closest description.` : "No matching foods found. Try a broader search.");
    } catch (error) {
      if (requestId === searchSequence.current) setSearchError(getApiErrorMessage(error));
    } finally {
      if (requestId === searchSequence.current) setSearching(false);
    }
  };
  const addFood = (food) => {
    const servingUnit = (food.serving_size_unit || "").toLowerCase();
    const usesServing = servingUnit === "serving";
    const usesGrams = servingUnit === "g";
    setEntries((current) => [...current, {
      ...newEntry(activeDay, activeMeal), fdc_id: String(food.fdc_id), description: food.description,
      quantity: food.serving_size ? String(food.serving_size) : "", unit: usesServing ? "serving" : "g",
      servingNote: food.serving_size ? `USDA lists a reference serving of ${food.serving_size} ${food.serving_size_unit || "units"}. ${usesGrams ? "This entry starts in grams because the record is mass-based." : "Confirm the unit before submitting."}` : "No serving size was provided; enter a quantity in grams or kilograms.",
    }]);
    setAnalysis(null); setSearchError("");
  };

  const setupError = () => {
    if (!age.trim() || !Number.isFinite(Number(age)) || Number(age) < 18 || Number(age) > 80) return "Enter an age from 18 to 80 years.";
    if (!bmi.trim() || !Number.isFinite(Number(bmi)) || Number(bmi) <= 0) return "Enter a BMI greater than zero.";
    return "";
  };
  const validateMeals = () => {
    if (!entries.length) return "Add at least one food to the meal plan.";
    for (const [index, entry] of entries.entries()) {
      if (!entry.fdc_id) return `Food ${index + 1} needs a USDA search result before analysis.`;
      const quantity = Number(entry.quantity);
      if (!entry.quantity || !Number.isFinite(quantity) || quantity <= 0 || quantity > 100000) return `${entry.description || `Food ${index + 1}`} needs a quantity greater than 0 and no more than 100,000.`;
      if (!["g", "kg", "serving"].includes(entry.unit)) return `${entry.description || `Food ${index + 1}`} needs a supported unit.`;
    }
    return "";
  };
  const goToBuild = () => { const error = setupError(); if (error) { setAnalysisError(error); return; } setAnalysisError(""); setStep(2); };
  const submitAnalysis = async (event) => {
    event.preventDefault();
    const error = setupError() || validateMeals();
    if (error) { setAnalysisError(error); return; }
    setAnalysis(null); setAnalysisError(""); setAnalyzing(true); setStep(3);
    try {
      const payload = {
        entries: entries.map(({ day, fdc_id, quantity, unit }) => ({ day, fdc_id: Number(fdc_id), quantity: Number(quantity), unit })),
        selected_days: selectedDays, age: Number(age), sex_female: Number(sexFemale), bmi: Number(bmi),
      };
      setAnalysis(await analyzeMealPlan(payload));
    } catch (errorResponse) {
      setAnalysisError(getApiErrorMessage(errorResponse));
    } finally { setAnalyzing(false); }
  };

  return (
    <main className="ci3-page">
      <header className="ci3-hero">
        <div><p className="ci3-eyebrow">COMPONENT 3 · CAREGIVER WORKSPACE</p><h1>Plan meals with confidence</h1><p className="ci3-subtitle">Build a resident's planned meals from real USDA food records, then review the nutrition summary together. This research tool does not determine clinical risk.</p></div>
        <div className={`ci3-api-status ci3-api-${apiState}`} role="status"><span className="ci3-status-dot" /><span>{apiState === "online" ? "Nutrition service connected" : apiState === "checking" ? "Checking nutrition service" : "Nutrition service unavailable"}</span><button type="button" className="ci3-text-button" onClick={checkHealth}>Retry</button><small>{apiMessage}</small></div>
      </header>
      <Stepper step={step} />

      {step === 1 && <section className="ci3-panel ci3-step-panel" aria-labelledby="setup-title">
        <div className="ci3-section-heading"><span className="ci3-step">1</span><div><p className="ci3-eyebrow">RESIDENT AND PLAN SETUP</p><h2 id="setup-title">Tell us about this plan</h2><p>These details are inputs for the research model, not a diagnosis or a complete clinical profile.</p></div></div>
        <div className="ci3-profile-grid">
          <label htmlFor="ci3-age">Age in years<input id="ci3-age" type="number" min="18" max="80" value={age} onChange={(event) => setAge(event.target.value)} placeholder="18-80" /><small>Supported research range: 18-80</small></label>
          <label htmlFor="ci3-sex">Sex used by research model<select id="ci3-sex" value={sexFemale} onChange={(event) => setSexFemale(event.target.value)}><option value="1">Female</option><option value="0">Male</option></select><small>This is encoded for the existing API.</small></label>
          <label htmlFor="ci3-bmi">BMI (kg/m²)<input id="ci3-bmi" type="number" min="0.1" step="0.1" value={bmi} onChange={(event) => setBmi(event.target.value)} placeholder="e.g. 26.4" /><small>Use the resident's available measurement.</small></label>
        </div>
        <div className="ci3-plan-choice"><h3>How many days are you planning?</h3><p>Start with one day, or add dates for a multi-day plan. You can change this later.</p><div className="ci3-day-chips">{selectedDays.map((day) => <span className="ci3-day-chip" key={day}>{formatDay(day)}<button type="button" aria-label={`Remove ${formatDay(day)}`} onClick={() => removeDay(day)} disabled={selectedDays.length === 1}>×</button></span>)}</div><div className="ci3-add-day"><label htmlFor="ci3-new-day">Add another day<input id="ci3-new-day" type="date" value={newDay} onChange={(event) => setNewDay(event.target.value)} /></label><button type="button" className="ci3-button ci3-button-secondary" onClick={addDay} disabled={!newDay || selectedDays.includes(newDay)}>Add day</button></div></div>
        {analysisError && <p className="ci3-alert ci3-alert-error" role="alert">{analysisError}</p>}
        <div className="ci3-navigation"><span>Next: choose foods and portions for each meal.</span><button type="button" className="ci3-button" onClick={goToBuild}>Continue to build meals</button></div>
      </section>}

      {step === 2 && <section className="ci3-build-layout" aria-labelledby="build-title">
        <div className="ci3-panel ci3-build-main"><div className="ci3-section-heading"><span className="ci3-step">2</span><div><p className="ci3-eyebrow">BUILD MEALS AND PORTIONS</p><h2 id="build-title">What will the resident eat?</h2><p>Choose a day and meal, then add foods from USDA search or build the meal manually.</p></div></div>
          <div className="ci3-day-tabs" role="tablist" aria-label="Plan days">{selectedDays.map((day) => <button type="button" role="tab" aria-selected={activeDay === day} className={activeDay === day ? "active" : ""} key={day} onClick={() => setActiveDay(day)}>{formatDay(day)}</button>)}</div>
          <div className="ci3-meal-tabs" role="tablist" aria-label="Meals for selected day">{MEALS.map((meal) => <button type="button" role="tab" aria-selected={activeMeal === meal} className={activeMeal === meal ? "active" : ""} key={meal} onClick={() => setActiveMeal(meal)}>{meal}<span>{entries.filter((entry) => entry.day === activeDay && entry.meal === meal).length}</span></button>)}</div>
          <form className="ci3-search-form" onSubmit={runFoodSearch}><label htmlFor="ci3-food-query">Find a food for {activeMeal.toLowerCase()} <span>Try oats, rice, eggs, vegetables, or lentils</span></label><div className="ci3-search-row"><input id="ci3-food-query" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search USDA foods" maxLength={200} /><button className="ci3-button" type="submit" disabled={searching}>{searching ? "Searching..." : "Search"}</button></div></form>
          <div className="ci3-live-region" aria-live="polite">{searching ? "Searching USDA food records..." : searchMessage}</div>
          {searchError && <p className="ci3-alert ci3-alert-error" role="alert">{searchError}</p>}
          {foodResults.length > 0 && <div className="ci3-food-results"><h3>Choose a food record</h3>{foodResults.map((food) => <div className="ci3-food-result" key={food.fdc_id}><div><strong>{food.description}</strong><small>{food.data_type} · USDA record {food.fdc_id}{food.serving_size ? ` · ${food.serving_size} ${food.serving_size_unit || "per serving"}` : " · No serving size listed"}</small></div><button type="button" className="ci3-button ci3-button-small" onClick={() => addFood(food)}>Add to {activeMeal.toLowerCase()}</button></div>)}</div>}
          <div className="ci3-current-meal"><div className="ci3-current-meal-heading"><div><p className="ci3-eyebrow">{formatDay(activeDay)} · {activeMeal.toUpperCase()}</p><h3>{activeMeal} foods</h3></div></div>{activeEntries.length ? activeEntries.map((entry) => <EntryEditor key={entry.rowId} entry={entry} onChange={changeEntry} onRemove={removeEntry} />) : <div className="ci3-empty-state"><strong>No foods in this meal yet</strong><span>Search above and add a verified USDA food record to begin.</span></div>}</div>
          {analysisError && <p className="ci3-alert ci3-alert-error" role="alert">{analysisError}</p>}
          <div className="ci3-navigation"><button type="button" className="ci3-button ci3-button-secondary" onClick={() => setStep(1)}>Back to setup</button><button type="button" className="ci3-button" onClick={() => { const error = validateMeals(); if (error) setAnalysisError(error); else { setAnalysisError(""); setStep(3); } }}>Review nutrition</button></div>
        </div>
        <aside className="ci3-panel ci3-plan-summary" aria-label="Current plan summary"><p className="ci3-eyebrow">PLAN SUMMARY</p><h2>{selectedDays.length} {selectedDays.length === 1 ? "day" : "days"}</h2><p className="ci3-muted">{entries.length} food {entries.length === 1 ? "entry" : "entries"} across the plan</p>{selectedDays.map((day) => <div className="ci3-summary-day" key={day}><strong>{formatDay(day)}</strong>{MEALS.map((meal) => { const count = entries.filter((entry) => entry.day === day && entry.meal === meal).length; return <span key={meal}>{meal}<b>{count}</b></span>; })}</div>)}</aside>
      </section>}

      {step === 3 && <section className="ci3-results" aria-labelledby="results-title"><div className="ci3-results-heading"><div><p className="ci3-eyebrow">3 · REVIEW NUTRITION</p><h2 id="results-title">Your plan summary</h2><p className="ci3-muted">{selectedDays.length} {selectedDays.length === 1 ? "day" : "days"} · {entries.length} food entries submitted</p></div><span className="ci3-results-tag">{analyzing ? "Analysis in progress" : analysis ? "Analysis complete" : "Ready to analyze"}</span></div>{analyzing && <div className="ci3-loading" role="status"><span className="ci3-spinner" /> Reviewing the plan with the nutrition service...</div>}{analysisError && <div className="ci3-alert ci3-alert-error" role="alert"><strong>We could not complete this analysis.</strong><p>{analysisError}</p></div>}{analysis && <><div className="ci3-result-block"><h3>Full selected-plan total</h3><p className="ci3-muted">This is the total across all selected days, not a daily average.</p><NutrientGrid summary={analysis.complete_plan_total} /></div><div className="ci3-result-block"><h3>Daily summaries</h3><p className="ci3-muted">Each row is the total for that day. Meal-level nutrient totals are not returned by the current API.</p>{Object.entries(analysis.daily_nutrients || {}).map(([day, summary]) => <div className="ci3-daily-result" key={day}><h4>{formatDay(day)}</h4><NutrientGrid summary={summary} /></div>)}</div><div className="ci3-prediction"><p className="ci3-eyebrow">EXPERIMENTAL CLASSIFIER OUTPUT</p><h3>{analysis.prediction?.predicted_category || "No category returned"}</h3><p>{analysis.prediction?.experimental_result || "The API did not return a classifier explanation."}</p>{Object.keys(analysis.prediction?.probabilities || {}).length > 0 && <><h4>Returned model probabilities</h4><div className="ci3-probabilities">{Object.entries(analysis.prediction.probabilities).map(([category, probability]) => <div className="ci3-probability" key={category}><div><span>{category}</span><strong>{(Number(probability) * 100).toFixed(1)}%</strong></div><div className="ci3-progress"><span style={{ width: `${Math.max(0, Math.min(100, Number(probability) * 100))}%` }} /></div></div>)}</div></>}<p className="ci3-classifier-note">This output is experimental, is not a diagnosis, and has not been clinically validated as a prediction of future blood pressure.</p></div><div className="ci3-alert ci3-alert-warning"><strong>Review with a qualified clinician</strong><p>{analysis.limitation}</p></div><details className="ci3-technical-details"><summary>Technical classifier details</summary><pre>{JSON.stringify(analysis.classifier_features, null, 2)}</pre></details></>}</section>}
+      {step === 3 && <div className="ci3-result-actions"><button type="button" className="ci3-button ci3-button-secondary" onClick={() => { setAnalysisError(""); setStep(2); }}>Back to edit meals</button>{!analysis && !analyzing && <button type="button" className="ci3-button" onClick={submitAnalysis}>Analyze plan</button>}{analysis && <button type="button" className="ci3-button" onClick={submitAnalysis} disabled={analyzing}>Recalculate nutrition</button>}</div>}
      <footer className="ci3-footer">Component 3 · Hypertension Dietary Risk Assessment System · Research prototype</footer>
    </main>
  );
}
