import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  analyzeMealPlan,
  checkNutritionApiHealth,
  getApiErrorMessage,
  searchFoods,
} from "../services/nutritionApi";
import "./NutritionalIntelligence.css";

const dateString = (date) => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
};
const today = dateString(new Date());
const newRow = (day = today) => ({
  rowId: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
  day,
  fdc_id: "",
  description: "",
  quantity: "100",
  unit: "g",
});

const nutrients = [
  ["sodium_mg", "Sodium", "mg"],
  ["potassium_mg", "Potassium", "mg"],
  ["energy_kcal", "Energy", "kcal"],
  ["sat_fat_g", "Saturated fat", "g"],
  ["na_k_ratio", "Sodium : potassium ratio", ""],
];

function displayValue(value, key) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "N/A";
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
          {unit && <small>{unit}</small>}
        </div>
      ))}
    </div>
  );
}

export default function NutritionalIntelligence() {
  const [apiState, setApiState] = useState("checking");
  const [apiMessage, setApiMessage] = useState("Checking API connection…");
  const [age, setAge] = useState("58");
  const [sexFemale, setSexFemale] = useState("1");
  const [bmi, setBmi] = useState("26.4");
  const [selectedDays, setSelectedDays] = useState([today]);
  const [newDay, setNewDay] = useState(today);
  const [entries, setEntries] = useState([newRow(today)]);
  const [query, setQuery] = useState("");
  const [foodResults, setFoodResults] = useState([]);
  const [chosenFoodId, setChosenFoodId] = useState("");
  const [searchError, setSearchError] = useState("");
  const [searchMessage, setSearchMessage] = useState("");
  const [analysis, setAnalysis] = useState(null);
  const [analysisError, setAnalysisError] = useState("");
  const [searching, setSearching] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);

  const chosenFood = useMemo(
    () => foodResults.find((food) => String(food.fdc_id) === String(chosenFoodId)),
    [foodResults, chosenFoodId]
  );

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

  const addDay = () => {
    if (!newDay || selectedDays.includes(newDay)) return;
    setSelectedDays((current) => [...current, newDay].sort());
    setAnalysis(null);
  };

  const removeDay = (day) => {
    if (selectedDays.length === 1) return;
    setSelectedDays((current) => current.filter((item) => item !== day));
    setEntries((current) => current.filter((entry) => entry.day !== day));
    setAnalysis(null);
  };

  const changeEntry = (rowId, field, value) => {
    setEntries((current) => current.map((entry) =>
      entry.rowId === rowId ? { ...entry, [field]: value } : entry
    ));
    setAnalysis(null);
  };

  const addFoodRow = () => {
    setEntries((current) => [...current, newRow(selectedDays[0] || today)]);
    setAnalysis(null);
  };

  const removeFoodRow = (rowId) => {
    setEntries((current) => current.filter((entry) => entry.rowId !== rowId));
    setAnalysis(null);
  };

  const runFoodSearch = async (event) => {
    event.preventDefault();
    setSearchError("");
    setSearchMessage("");
    setFoodResults([]);
    setChosenFoodId("");
    if (!query.trim()) {
      setSearchError("Enter a food name to search.");
      return;
    }
    setSearching(true);
    try {
      const result = await searchFoods(query.trim(), 10);
      setFoodResults(result.foods || []);
      setSearchMessage(result.foods?.length
        ? `Found ${result.foods.length} records. Choose the exact food record you intend to use.`
        : "No matching records found.");
    } catch (error) {
      setSearchError(getApiErrorMessage(error));
    } finally {
      setSearching(false);
    }
  };

  const addChosenFood = () => {
    if (!chosenFood) {
      setSearchError("Choose a food record first.");
      return;
    }
    const hasServing = Number(chosenFood.serving_size) > 0 && chosenFood.serving_size_unit;
    setEntries((current) => [...current, {
      ...newRow(selectedDays[0] || today),
      fdc_id: String(chosenFood.fdc_id),
      description: chosenFood.description,
      quantity: hasServing ? String(chosenFood.serving_size) : "100",
      unit: hasServing ? "serving" : "g",
    }]);
    setSearchError("");
    setAnalysis(null);
  };

  const validateForm = () => {
    if (!Number.isFinite(Number(age)) || Number(age) < 18 || Number(age) > 80) {
      return "Age must be between 18 and 80 for this research model.";
    }
    if (!Number.isFinite(Number(bmi)) || Number(bmi) <= 0) return "Enter a valid BMI greater than zero.";
    if (!selectedDays.length) return "Select at least one date.";
    if (!entries.length) return "Add at least one food to the meal plan.";
    for (const [index, entry] of entries.entries()) {
      if (!selectedDays.includes(entry.day)) return `Food row ${index + 1}: choose a selected date.`;
      if (!String(entry.fdc_id).trim()) return `Food row ${index + 1}: select a USDA food record using food search, or enter its FoodData Central ID.`;
      if (!Number.isFinite(Number(entry.quantity)) || Number(entry.quantity) < 0) {
        return `Food row ${index + 1}: quantity must be zero or greater.`;
      }
      if (!["g", "kg", "serving"].includes(entry.unit)) {
        return `Food row ${index + 1}: choose g, kg, or serving.`;
      }
    }
    return "";
  };

  const submitAnalysis = async (event) => {
    event.preventDefault();
    setAnalysis(null);
    setAnalysisError("");
    const validationError = validateForm();
    if (validationError) {
      setAnalysisError(validationError);
      return;
    }
    const payload = {
      entries: entries.map(({ day, fdc_id, quantity, unit }) => ({
        day,
        fdc_id: /^\d+$/.test(String(fdc_id)) ? Number(fdc_id) : fdc_id,
        quantity: Number(quantity),
        unit,
      })),
      selected_days: selectedDays,
      age: Number(age),
      sex_female: Number(sexFemale),
      bmi: Number(bmi),
    };
    setAnalyzing(true);
    try {
      setAnalysis(await analyzeMealPlan(payload));
    } catch (error) {
      setAnalysisError(getApiErrorMessage(error));
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <main className="ci3-page">
      <header className="ci3-hero">
        <div>
          <p className="ci3-eyebrow">COMPONENT 3 · CAREGIVER WORKSPACE</p>
          <h1>Hypertension Dietary Risk Assessment</h1>
          <p className="ci3-subtitle">
            Build a planned meal schedule and review its estimated nutrient totals.
            This prototype supports research and demonstration, not clinical decisions.
          </p>
        </div>
        <div className={`ci3-api-status ci3-api-${apiState}`} role="status">
          <span className="ci3-status-dot" />
          <span>{apiState === "online" ? "API connected" : apiState === "checking" ? "Checking API" : "API unavailable"}</span>
          <button type="button" className="ci3-text-button" onClick={checkHealth}>Retry</button>
          <small>{apiMessage}</small>
        </div>
      </header>

      <section className="ci3-panel">
        <div className="ci3-section-heading">
          <span className="ci3-step">01</span>
          <div><h2>Resident profile</h2><p>Used as model input; not a substitute for clinical assessment.</p></div>
        </div>
        <div className="ci3-profile-grid">
          <label>Age (years)
            <input type="number" min="18" max="80" value={age} onChange={(e) => setAge(e.target.value)} />
            <small>Supported range: 18–80</small>
          </label>
          <label>Sex used by research model
            <select value={sexFemale} onChange={(e) => setSexFemale(e.target.value)}>
              <option value="1">Female</option>
              <option value="0">Male</option>
            </select>
            <small>Encoded as female = 1, male = 0</small>
          </label>
          <label>BMI (kg/m²)
            <input type="number" min="0.1" step="0.1" value={bmi} onChange={(e) => setBmi(e.target.value)} />
            <small>Enter a positive value</small>
          </label>
        </div>
      </section>

      <section className="ci3-panel">
        <div className="ci3-section-heading">
          <span className="ci3-step">02</span>
          <div><h2>Plan dates</h2><p>Add each date that should appear in the nutrient summary.</p></div>
        </div>
        <div className="ci3-add-day">
          <label htmlFor="ci3-new-day">Add a date</label>
          <input id="ci3-new-day" type="date" value={newDay} onChange={(e) => setNewDay(e.target.value)} />
          <button type="button" className="ci3-button ci3-button-secondary" onClick={addDay} disabled={!newDay || selectedDays.includes(newDay)}>Add date</button>
        </div>
        <div className="ci3-day-chips">
          {selectedDays.map((day) => (
            <span className="ci3-day-chip" key={day}>
              {day}
              <button type="button" aria-label={`Remove ${day}`} onClick={() => removeDay(day)} disabled={selectedDays.length === 1}>×</button>
            </span>
          ))}
        </div>
      </section>

      <section className="ci3-panel">
        <div className="ci3-section-heading">
          <span className="ci3-step">03</span>
          <div><h2>Find foods</h2><p>Search USDA FoodData Central. Review descriptions carefully before choosing a record.</p></div>
        </div>
        <form className="ci3-search-form" onSubmit={runFoodSearch}>
          <label htmlFor="ci3-food-query">Food name</label>
          <div className="ci3-search-row">
            <input id="ci3-food-query" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. cooked white rice" maxLength={200} />
            <button className="ci3-button" type="submit" disabled={searching}>{searching ? "Searching…" : "Search foods"}</button>
          </div>
        </form>
        {searchError && <p className="ci3-alert ci3-alert-error" role="alert">{searchError}</p>}
        {searchMessage && <p className="ci3-inline-message" role="status">{searchMessage}</p>}
        {foodResults.length > 0 && (
          <div className="ci3-food-results">
            {foodResults.map((food) => (
              <label className={`ci3-food-result ${String(food.fdc_id) === String(chosenFoodId) ? "ci3-food-result-selected" : ""}`} key={food.fdc_id}>
                <input type="radio" name="ci3-food-result" value={food.fdc_id}
                  checked={String(chosenFoodId) === String(food.fdc_id)}
                  onChange={() => setChosenFoodId(String(food.fdc_id))} />
                <span><strong>{food.description}</strong><small>ID {food.fdc_id} · {food.data_type}{food.serving_size ? ` · Serving ${food.serving_size} ${food.serving_size_unit || ""}` : ""}</small></span>
              </label>
            ))}
            <button type="button" className="ci3-button ci3-button-secondary" onClick={addChosenFood} disabled={!chosenFood}>Add selected food to plan</button>
          </div>
        )}
      </section>

      <section className="ci3-panel">
        <div className="ci3-section-heading">
          <span className="ci3-step">04</span>
          <div><h2>Meal-plan entries</h2><p>Use only supported units: grams (g), kilograms (kg), or serving.</p></div>
        </div>
        <div className="ci3-entry-list">
          {entries.map((entry, index) => (
            <div className="ci3-entry" key={entry.rowId}>
              <div className="ci3-entry-top"><strong>Food {index + 1}</strong><button type="button" className="ci3-remove-button" onClick={() => removeFoodRow(entry.rowId)} disabled={entries.length === 1}>Remove</button></div>
              <div className="ci3-entry-grid">
                <label>Date
                  <select value={entry.day} onChange={(e) => changeEntry(entry.rowId, "day", e.target.value)}>
                    {selectedDays.map((day) => <option key={day} value={day}>{day}</option>)}
                  </select>
                </label>
                <label>USDA Food ID
                  <input value={entry.fdc_id} onChange={(e) => changeEntry(entry.rowId, "fdc_id", e.target.value)} placeholder="Select from search or enter ID" />
                </label>
                <label>Food description (for your reference)
                  <input value={entry.description} onChange={(e) => changeEntry(entry.rowId, "description", e.target.value)} placeholder="e.g. cooked rice" />
                </label>
                <label>Quantity
                  <input type="number" min="0" step="any" value={entry.quantity} onChange={(e) => changeEntry(entry.rowId, "quantity", e.target.value)} />
                </label>
                <label>Unit
                  <select value={entry.unit} onChange={(e) => changeEntry(entry.rowId, "unit", e.target.value)}>
                    <option value="g">g</option><option value="kg">kg</option><option value="serving">serving</option>
                  </select>
                </label>
              </div>
            </div>
          ))}
        </div>
        <button type="button" className="ci3-button ci3-button-secondary" onClick={addFoodRow}>+ Add manual food entry</button>
        <p className="ci3-hint">For reliable results, choose foods using search so you can verify the USDA description and ID. A manually entered ID is not automatically checked until analysis runs.</p>
      </section>

      <section className="ci3-panel ci3-submit-panel">
        <div><h2>Calculate nutrition and research estimate</h2><p>Submit the plan to the Component 3 API.</p></div>
        <button type="button" className="ci3-button ci3-button-large" onClick={submitAnalysis} disabled={analyzing}>{analyzing ? "Analyzing meal plan…" : "Analyze meal plan"}</button>
      </section>

      {analysisError && <div className="ci3-alert ci3-alert-error" role="alert"><strong>Could not analyze plan</strong><p>{analysisError}</p></div>}

      {analysis && (
        <section className="ci3-results" aria-live="polite">
          <div className="ci3-results-heading"><div><p className="ci3-eyebrow">ANALYSIS RESULTS</p><h2>Nutrition summary</h2></div><span className="ci3-results-tag">API response received</span></div>
          <h3>Complete selected-plan total</h3>
          <NutrientGrid summary={analysis.complete_plan_total} />
          <h3>Daily summaries</h3>
          {Object.entries(analysis.daily_nutrients || {}).map(([day, summary]) => (
            <div className="ci3-daily-result" key={day}><h4>{day}</h4><NutrientGrid summary={summary} /></div>
          ))}
          <div className="ci3-prediction">
            <p className="ci3-eyebrow">EXPERIMENTAL MODEL OUTPUT</p>
            <h3>{analysis.prediction?.predicted_category || "No category returned"}</h3>
            <p>{analysis.prediction?.experimental_result}</p>
            <h4>Model probabilities</h4>
            <div className="ci3-probabilities">
              {Object.entries(analysis.prediction?.probabilities || {}).map(([category, probability]) => (
                <div className="ci3-probability" key={category}>
                  <div><span>{category}</span><strong>{(Number(probability) * 100).toFixed(1)}%</strong></div>
                  <div className="ci3-progress"><span style={{ width: `${Math.max(0, Math.min(100, Number(probability) * 100))}%` }} /></div>
                </div>
              ))}
            </div>
          </div>
          <div className="ci3-alert ci3-alert-warning"><strong>Research limitation — not a medical assessment</strong><p>{analysis.limitation || "This is an experimental research result, not a diagnosis or a validated prediction of future blood pressure. Planned meals have not been clinically validated as equivalent to observed NHANES dietary recalls."}</p></div>
          <details className="ci3-technical-details"><summary>Technical classifier features</summary><pre>{JSON.stringify(analysis.classifier_features, null, 2)}</pre></details>
        </section>
      )}
      <footer className="ci3-footer">Component 3 · Hypertension Dietary Risk Assessment System · Research prototype</footer>
    </main>
  );
}
