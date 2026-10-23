import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  analyzeMealPlan,
  checkNutritionApiHealth,
  getApiErrorMessage,
  searchFoods,
  identifyFoodsFromImage,
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
  if (value === null || value === undefined || !Number.isFinite(Number(value)))
    return "Unknown";
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
      {["Plan dates", "Build meals", "Review nutrition"].map((label, index) => {
        const number = index + 1;
        return (
          <React.Fragment key={label}>
            <span
              className={`ci3-step-item ${step === number ? "active" : ""} ${step > number ? "complete" : ""}`}
            >
              <b>{step > number ? "✓" : number}</b>
              <span>{label}</span>
            </span>
            {number < 3 && (
              <span
                className={`ci3-step-line ${step > number ? "complete" : ""}`}
                aria-hidden="true"
              />
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}

function formatDay(day) {
  return new Date(`${day}T12:00:00`).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

function EntryEditor({ entry, onChange, onRemove }) {
  return (
    <article className="ci3-entry">
      <div className="ci3-entry-top">
        <div>
          <strong>{entry.description || "New food"}</strong>
          {entry.fdc_id && <small>USDA record {entry.fdc_id}</small>}
        </div>
        <button
          type="button"
          className="ci3-remove-button"
          onClick={() => onRemove(entry.rowId)}
        >
          Remove
        </button>
      </div>
      <div className="ci3-entry-grid">
        <label>
          Food name
          <input
            value={entry.description}
            onChange={(event) =>
              onChange(entry.rowId, "description", event.target.value)
            }
            placeholder="Search or describe this food"
          />
        </label>
        <label>
          Quantity
          <input
            aria-label={`Quantity for ${entry.description || "food"}`}
            type="number"
            min="0.01"
            max="100000"
            step="any"
            value={entry.quantity}
            onChange={(event) =>
              onChange(entry.rowId, "quantity", event.target.value)
            }
            placeholder="e.g. 100"
          />
        </label>
        <label>
          Unit
          <select
            value={entry.unit}
            onChange={(event) =>
              onChange(entry.rowId, "unit", event.target.value)
            }
          >
            {UNITS.map((unit) => (
              <option value={unit.value} key={unit.value}>
                {unit.label}
              </option>
            ))}
          </select>
        </label>
        {entry.servingNote && (
          <p className="ci3-serving-note">{entry.servingNote}</p>
        )}
      </div>
    </article>
  );
}

export default function NutritionalIntelligence() {
  const [step, setStep] = useState(1);
  const [apiState, setApiState] = useState("checking");
  const [apiMessage, setApiMessage] = useState("Checking API connection...");
  const [selectedDays, setSelectedDays] = useState([today]);
  const [newDay, setNewDay] = useState(today);
  const [activeDay, setActiveDay] = useState(today);
  const [activeMeal, setActiveMeal] = useState("Breakfast");
  const [entries, setEntries] = useState([]);
  const [ageYears, setAgeYears] = useState("60");
  const [bmi, setBmi] = useState("");
  const [sexCode, setSexCode] = useState("");
  const [fullDayIntake, setFullDayIntake] = useState(false);
  const [dietaryRequirements, setDietaryRequirements] = useState("");
  const [query, setQuery] = useState("");
  const [foodResults, setFoodResults] = useState([]);
  const [searchError, setSearchError] = useState("");
  const [searchMessage, setSearchMessage] = useState("");
  const [searching, setSearching] = useState(false);
  const [photoFile, setPhotoFile] = useState(null);
  const [photoBusy, setPhotoBusy] = useState(false);
  const [photoError, setPhotoError] = useState("");
  const [photoMessage, setPhotoMessage] = useState("");
  const [photoSuggestions, setPhotoSuggestions] = useState([]);
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
  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  const activeEntries = useMemo(
    () =>
      entries.filter(
        (entry) => entry.day === activeDay && entry.meal === activeMeal,
      ),
    [entries, activeDay, activeMeal],
  );

  const changeEntry = (rowId, field, value) => {
    setEntries((current) =>
      current.map((entry) =>
        entry.rowId === rowId ? { ...entry, [field]: value } : entry,
      ),
    );
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
    if (activeDay === day)
      setActiveDay(selectedDays.find((item) => item !== day) || today);
    setAnalysis(null);
  };
  const removeEntry = (rowId) => {
    setEntries((current) => current.filter((entry) => entry.rowId !== rowId));
    setAnalysis(null);
  };

  const runFoodSearch = async (event) => {
    event.preventDefault();
    const trimmed = query.trim();
    setSearchError("");
    setSearchMessage("");
    setFoodResults([]);
    if (!trimmed) {
      setSearchError(
        "Enter a food to search, such as oats, rice, eggs, vegetables, or lentils.",
      );
      return;
    }
    const requestId = ++searchSequence.current;
    setSearching(true);
    try {
      const result = await searchFoods(trimmed, 10);
      if (requestId !== searchSequence.current) return;
      const foods = result.foods || [];
      setFoodResults(foods);
      setSearchMessage(
        foods.length
          ? `${foods.length} USDA records found. Choose the closest description.`
          : "No matching foods found. Try a broader search.",
      );
    } catch (error) {
      if (requestId === searchSequence.current)
        setSearchError(getApiErrorMessage(error));
    } finally {
      if (requestId === searchSequence.current) setSearching(false);
    }
  };
  const identifyPhoto = async () => {
    setPhotoError(""); setPhotoMessage(""); setPhotoSuggestions([]);
    if (!photoFile) { setPhotoError("Choose a dish photo first."); return; }
    if (!/^image\/(jpeg|png|webp)$/.test(photoFile.type)) { setPhotoError("Please choose a JPG, PNG, or WEBP image."); return; }
    if (photoFile.size > 8 * 1024 * 1024) { setPhotoError("Please choose an image smaller than 8 MB."); return; }
    setPhotoBusy(true);
    try {
      const imageDataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error("Could not read this image."));
        reader.readAsDataURL(photoFile);
      });
      const result = await identifyFoodsFromImage(imageDataUrl, activeMeal);
      setPhotoSuggestions((result.foods || []).map((food, index) => ({...food, key: `${Date.now()}-${index}`, selected: true, editedName: food.food_name, editedGrams: String(Math.round(food.estimated_quantity_g || 100))})));
      setPhotoMessage(result.message || "Review the suggested foods below.");
      if (!(result.foods || []).length) setPhotoMessage("No foods were confidently identified. Try a clearer photo or use food search.");
    } catch (error) { setPhotoError(getApiErrorMessage(error)); }
    finally { setPhotoBusy(false); }
  };
  const updatePhotoSuggestion = (key, field, value) => setPhotoSuggestions(items => items.map(item => item.key === key ? {...item, [field]: value} : item));
  const addPhotoFoods = async () => {
    const chosen = photoSuggestions.filter(item => item.selected && item.editedName.trim());
    if (!chosen.length) { setPhotoError("Select at least one food to add."); return; }
    setPhotoBusy(true); setPhotoError("");
    try {
      const resolved = [];
      for (const item of chosen) {
        const grams = Number(item.editedGrams);
        if (!Number.isFinite(grams) || grams <= 0) throw new Error(`Enter a valid portion for ${item.editedName}.`);
        const result = await searchFoods(item.editedName.trim(), 5);
        const food = (result.foods || [])[0];
        if (!food) { resolved.push({item, food: null}); continue; }
        resolved.push({item, food, grams});
      }
      const added = resolved.filter(row => row.food).map(({item,food,grams}) => ({...newEntry(activeDay,activeMeal), fdc_id:String(food.fdc_id), description:food.description, quantity:String(grams), unit:"g", servingNote:`Suggested from photo as “${item.editedName}”. Estimated portion: ${grams} g. Please verify the USDA match and portion.`}));
      setEntries(current => [...current, ...added]); setAnalysis(null);
      const unresolved = resolved.filter(row => !row.food).map(row => row.item.editedName);
      setPhotoMessage(`${added.length} food(s) added using USDA matches. Check every name and portion below.${unresolved.length ? ` Could not find USDA matches for: ${unresolved.join(", ")}. Add these manually using search.` : ""}`);
      if (unresolved.length) setPhotoError(`No USDA match found for: ${unresolved.join(", ")}.`);
      else setPhotoError("");
      setPhotoSuggestions([]); setPhotoFile(null);
    } catch (error) { setPhotoError(getApiErrorMessage(error)); }
    finally { setPhotoBusy(false); }
  };

  const addFood = (food) => {
    const servingUnit = (food.serving_size_unit || "").toLowerCase();
    const usesServing = servingUnit === "serving";
    const usesGrams = servingUnit === "g";
    setEntries((current) => [
      ...current,
      {
        ...newEntry(activeDay, activeMeal),
        fdc_id: String(food.fdc_id),
        description: food.description,
        quantity: food.serving_size ? String(food.serving_size) : "",
        unit: usesServing ? "serving" : "g",
        servingNote: food.serving_size
          ? `USDA lists a reference serving of ${food.serving_size} ${food.serving_size_unit || "units"}. ${usesGrams ? "This entry starts in grams because the record is mass-based." : "Confirm the unit before submitting."}`
          : "No serving size was provided; enter a quantity in grams or kilograms.",
      },
    ]);
    setAnalysis(null);
    setSearchError("");
  };

  const validateMeals = () => {
    if (!entries.length) return "Add at least one food to the meal plan.";
    for (const [index, entry] of entries.entries()) {
      if (!entry.fdc_id)
        return `Food ${index + 1} needs a USDA search result before analysis.`;
      const quantity = Number(entry.quantity);
      if (
        !entry.quantity ||
        !Number.isFinite(quantity) ||
        quantity <= 0 ||
        quantity > 100000
      )
        return `${entry.description || `Food ${index + 1}`} needs a quantity greater than 0 and no more than 100,000.`;
      if (!["g", "kg", "serving"].includes(entry.unit))
        return `${entry.description || `Food ${index + 1}`} needs a supported unit.`;
    }
    return "";
  };
  const goToBuild = () => {
    setAnalysisError("");
    setStep(2);
  };
  const submitAnalysis = async (event) => {
    event.preventDefault();
    const error = validateMeals();
    if (error) {
      setAnalysisError(error);
      return;
    }
    setAnalysis(null);
    setAnalysisError("");
    setAnalyzing(true);
    setStep(3);
    try {
      const payload = {
        entries: entries.map(({ day, meal, fdc_id, quantity, unit }) => ({
          day,
          meal,
          fdc_id: Number(fdc_id),
          quantity: Number(quantity),
          unit,
        })),
        selected_days: selectedDays,
        personal_profile: {
          age_years: Number(ageYears),
          bmi: bmi.trim() ? Number(bmi) : null,
          dietary_requirements: dietaryRequirements.split(",").map((item) => item.trim()).filter(Boolean),
        },
      };
      setAnalysis(await analyzeMealPlan(payload));
    } catch (errorResponse) {
      setAnalysisError(getApiErrorMessage(errorResponse));
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <main className="ci3-page">
      <header className="ci3-hero">
        <div>
          <p className="ci3-eyebrow">COMPONENT 3 · CAREGIVER WORKSPACE</p>
          <h1>DASH-Informed Personalized Meal Assessment</h1>
          <p className="ci3-subtitle">
            Build meals from USDA food records, calculate nutrient totals, assess dietary references, and—when you confirm a complete day's intake—see an ML estimate of daily reference alignment. The estimate is a rule-derived research proxy, not a clinical meal-suitability score.
          </p>
        </div>
        <div className={`ci3-api-status ci3-api-${apiState}`} role="status">
          <span className="ci3-status-dot" />
          <span>
            {apiState === "online"
              ? "Nutrition service connected"
              : apiState === "checking"
                ? "Checking nutrition service"
                : "Nutrition service unavailable"}
          </span>
          <button
            type="button"
            className="ci3-text-button"
            onClick={checkHealth}
          >
            Retry
          </button>
          <small>{apiMessage}</small>
        </div>
      </header>
      <Stepper step={step} />
      {step === 1 && (
        <section
          className="ci3-panel ci3-step-panel"
          aria-labelledby="setup-title"
        >
          <div className="ci3-section-heading">
            <span className="ci3-step">1</span>
            <div>
              <p className="ci3-eyebrow">MEAL PLAN SETUP</p>
              <h2 id="setup-title">Choose the dates to assess</h2>
              <p>
                Add one or more dates, then enter foods, quantities and serving units. Add relevant personal information to support the intended personalized assessment.
              </p>
            </div>
          </div>
          <div className="ci3-plan-choice">
            <h3>Personal profile</h3>
            <p>Enter only information relevant to meal assessment. These fields do not diagnose hypertension or replace professional advice.</p>
            <div className="ci3-entry-grid">
              <label>Age (years)
                <input type="number" min="19" max="119" value={ageYears} onChange={(event) => setAgeYears(event.target.value)} required />
              </label>
              <label>BMI (optional)
                <input type="number" min="10" max="100" step="0.1" value={bmi} onChange={(event) => setBmi(event.target.value)} placeholder="e.g. 26.5" />
              </label>
              <label>Sex code for optional ML estimate (optional)
                <select value={sexCode} onChange={(event) => setSexCode(event.target.value)}>
                  <option value="">Not provided</option>
                  <option value="1">Code 1</option>
                  <option value="2">Code 2</option>
                </select>
              </label>
              <label>Dietary requirements (optional, comma-separated)
                <input value={dietaryRequirements} onChange={(event) => setDietaryRequirements(event.target.value)} placeholder="e.g. lower sodium, vegetarian" />
              </label>
            </div>
            <label className="ci3-full-day-option">
              <input type="checkbox" checked={fullDayIntake} onChange={(event) => setFullDayIntake(event.target.checked)} />
              <span>
                <strong>These entries represent the complete day's food intake</strong>
                <small>Only select this if you have entered all foods for each selected day. This enables the optional daily ML estimate; it does not make the model a meal-suitability predictor.</small>
              </span>
            </label>
            <h3>How many days are you planning?</h3>
            <p>
              Start with one day, or add dates for a multi-day plan. You can
              change this later.
            </p>
            <div className="ci3-day-chips">
              {selectedDays.map((day) => (
                <span className="ci3-day-chip" key={day}>
                  {formatDay(day)}
                  <button
                    type="button"
                    aria-label={`Remove ${formatDay(day)}`}
                    onClick={() => removeDay(day)}
                    disabled={selectedDays.length === 1}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
            <div className="ci3-add-day">
              <label htmlFor="ci3-new-day">
                Add another day
                <input
                  id="ci3-new-day"
                  type="date"
                  value={newDay}
                  onChange={(event) => setNewDay(event.target.value)}
                />
              </label>
              <button
                type="button"
                className="ci3-button ci3-button-secondary"
                onClick={addDay}
                disabled={!newDay || selectedDays.includes(newDay)}
              >
                Add day
              </button>
            </div>
          </div>
          {analysisError && (
            <p className="ci3-alert ci3-alert-error" role="alert">
              {analysisError}
            </p>
          )}
          <div className="ci3-navigation">
            <span>Next: choose foods and portions for each meal.</span>
            <button type="button" className="ci3-button" onClick={goToBuild}>
              Continue to build meals
            </button>
          </div>
        </section>
      )}
      {step === 2 && (
        <section className="ci3-build-layout" aria-labelledby="build-title">
          <div className="ci3-panel ci3-build-main">
            <div className="ci3-section-heading">
              <span className="ci3-step">2</span>
              <div>
                <p className="ci3-eyebrow">BUILD MEALS AND PORTIONS</p>
                <h2 id="build-title">What will the resident eat?</h2>
                <p>
                  Choose a day and meal, then add foods from USDA search or
                  build the meal manually.
                </p>
              </div>
            </div>
            <div className="ci3-day-tabs" role="tablist" aria-label="Plan days">
              {selectedDays.map((day) => (
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeDay === day}
                  className={activeDay === day ? "active" : ""}
                  key={day}
                  onClick={() => setActiveDay(day)}
                >
                  {formatDay(day)}
                </button>
              ))}
            </div>
            <div
              className="ci3-meal-tabs"
              role="tablist"
              aria-label="Meals for selected day"
            >
              {MEALS.map((meal) => (
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeMeal === meal}
                  className={activeMeal === meal ? "active" : ""}
                  key={meal}
                  onClick={() => setActiveMeal(meal)}
                >
                  {meal}
                  <span>
                    {
                      entries.filter(
                        (entry) =>
                          entry.day === activeDay && entry.meal === meal,
                      ).length
                    }
                  </span>
                </button>
              ))}
            </div>
            <section className="ci3-photo-entry" aria-labelledby="ci3-photo-title">
              <h3 id="ci3-photo-title">Add food from a photo</h3>
              <p>Upload a clear picture of the dish. AI will suggest visible foods and rough portions; check everything before nutrition is calculated.</p>
              <div className="ci3-photo-controls">
                <input aria-label="Dish photo" type="file" accept="image/jpeg,image/png,image/webp" onChange={event => {setPhotoFile(event.target.files?.[0] || null); setPhotoError(""); setPhotoSuggestions([]);}} />
                <button type="button" className="ci3-button" onClick={identifyPhoto} disabled={photoBusy || !photoFile}>{photoBusy ? "Identifying / matching..." : "Identify foods"}</button>
              </div>
              {photoFile && <p className="ci3-muted">Selected: {photoFile.name}</p>}
              {photoMessage && <p className="ci3-live-region" role="status">{photoMessage}</p>}
              {photoError && <p className="ci3-alert ci3-alert-error" role="alert">{photoError}</p>}
              {photoSuggestions.length > 0 && <div className="ci3-photo-suggestions">
                <h4>Review AI suggestions</h4>
                <p className="ci3-muted">Estimated portions are approximate. Edit names and grams, then add the selected items.</p>
                {photoSuggestions.map(item => <div className="ci3-photo-item" key={item.key}>
                  <label className="ci3-photo-check"><input type="checkbox" checked={item.selected} onChange={e => updatePhotoSuggestion(item.key,"selected",e.target.checked)} /> Include</label>
                  <label>Food name<input value={item.editedName} onChange={e => updatePhotoSuggestion(item.key,"editedName",e.target.value)} /></label>
                  <label>Estimated portion (g)<input type="number" min="1" max="5000" value={item.editedGrams} onChange={e => updatePhotoSuggestion(item.key,"editedGrams",e.target.value)} /></label>
                  <small>AI confidence: {item.confidence || "unknown"}. {item.notes || "Check ingredients and portion."}</small>
                </div>)}
                <button type="button" className="ci3-button" onClick={addPhotoFoods} disabled={photoBusy}>{photoBusy ? "Adding foods..." : "Confirm foods and find nutrition records"}</button>
              </div>}
              <p className="ci3-photo-disclaimer">Photo estimates can miss oil, salt, sauces and hidden ingredients. You can still add these manually using food search.</p>
            </section>
            <form className="ci3-search-form" onSubmit={runFoodSearch}>
              <label htmlFor="ci3-food-query">
                Find a food for {activeMeal.toLowerCase()}{" "}
                <span>Try oats, rice, eggs, vegetables, or lentils</span>
              </label>
              <div className="ci3-search-row">
                <input
                  id="ci3-food-query"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search USDA foods"
                  maxLength={200}
                />
                <button
                  className="ci3-button"
                  type="submit"
                  disabled={searching}
                >
                  {searching ? "Searching..." : "Search"}
                </button>
              </div>
            </form>
            <div className="ci3-live-region" aria-live="polite">
              {searching ? "Searching USDA food records..." : searchMessage}
            </div>
            {searchError && (
              <p className="ci3-alert ci3-alert-error" role="alert">
                {searchError}
              </p>
            )}
            {foodResults.length > 0 && (
              <div className="ci3-food-results">
                <h3>Choose a food record</h3>
                {foodResults.map((food) => (
                  <div className="ci3-food-result" key={food.fdc_id}>
                    <div>
                      <strong>{food.description}</strong>
                      <small>
                        {food.data_type} · USDA record {food.fdc_id}
                        {food.serving_size
                          ? ` · ${food.serving_size} ${food.serving_size_unit || "per serving"}`
                          : " · No serving size listed"}
                      </small>
                    </div>
                    <button
                      type="button"
                      className="ci3-button ci3-button-small"
                      onClick={() => addFood(food)}
                    >
                      Add to {activeMeal.toLowerCase()}
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="ci3-current-meal">
              <div className="ci3-current-meal-heading">
                <div>
                  <p className="ci3-eyebrow">
                    {formatDay(activeDay)} · {activeMeal.toUpperCase()}
                  </p>
                  <h3>{activeMeal} foods</h3>
                </div>
              </div>
              {activeEntries.length ? (
                activeEntries.map((entry) => (
                  <EntryEditor
                    key={entry.rowId}
                    entry={entry}
                    onChange={changeEntry}
                    onRemove={removeEntry}
                  />
                ))
              ) : (
                <div className="ci3-empty-state">
                  <strong>No foods in this meal yet</strong>
                  <span>
                    Search above and add a verified USDA food record to begin.
                  </span>
                </div>
              )}
            </div>
            {analysisError && (
              <p className="ci3-alert ci3-alert-error" role="alert">
                {analysisError}
              </p>
            )}
            <div className="ci3-navigation">
              <button
                type="button"
                className="ci3-button ci3-button-secondary"
                onClick={() => setStep(1)}
              >
                Back to setup
              </button>
              <button
                type="button"
                className="ci3-button"
                onClick={() => {
                  const error = validateMeals();
                  if (error) setAnalysisError(error);
                  else {
                    setAnalysisError("");
                    setStep(3);
                  }
                }}
              >
                Review nutrition
              </button>
            </div>
          </div>
          <aside
            className="ci3-panel ci3-plan-summary"
            aria-label="Current plan summary"
          >
            <p className="ci3-eyebrow">PLAN SUMMARY</p>
            <h2>
              {selectedDays.length} {selectedDays.length === 1 ? "day" : "days"}
            </h2>
            <p className="ci3-muted">
              {entries.length} food {entries.length === 1 ? "entry" : "entries"}{" "}
              across the plan
            </p>
            {selectedDays.map((day) => (
              <div className="ci3-summary-day" key={day}>
                <strong>{formatDay(day)}</strong>
                {MEALS.map((meal) => {
                  const count = entries.filter(
                    (entry) => entry.day === day && entry.meal === meal,
                  ).length;
                  return (
                    <span key={meal}>
                      {meal}
                      <b>{count}</b>
                    </span>
                  );
                })}
              </div>
            ))}
          </aside>
        </section>
      )}
      {step === 3 && (
        <section className="ci3-results" aria-labelledby="results-title">
          <div className="ci3-results-heading">
            <div>
              <p className="ci3-eyebrow">3 · REVIEW NUTRITION</p>
              <h2 id="results-title">Your plan summary</h2>
              <p className="ci3-muted">
                {selectedDays.length}{" "}
                {selectedDays.length === 1 ? "day" : "days"} · {entries.length}{" "}
                food entries submitted
              </p>
            </div>
            <span className="ci3-results-tag">
              {analyzing
                ? "Analysis in progress"
                : analysis
                  ? "Analysis complete"
                  : "Ready to analyze"}
            </span>
          </div>
          {analyzing && (
            <div className="ci3-loading" role="status">
              <span className="ci3-spinner" /> Reviewing the plan with the
              nutrition service...
            </div>
          )}
          {analysisError && (
            <div className="ci3-alert ci3-alert-error" role="alert">
              <strong>We could not complete this analysis.</strong>
              <p>{analysisError}</p>
            </div>
          )}
          {analysis && (
            <>
              <div className="ci3-result-block ci3-actual-meals">
                <h3>What you entered</h3>
                <p className="ci3-muted">Check that these foods and portions match the dish you ate.</p>
                {selectedDays.map(day => <div className="ci3-daily-result" key={`entered-${day}`}>
                  <h4>{formatDay(day)}</h4>
                  {MEALS.map(meal => { const mealEntries = entries.filter(entry => entry.day === day && entry.meal === meal); if (!mealEntries.length) return null; return <div className="ci3-entered-meal" key={`${day}-${meal}`}><strong>{meal}</strong><ul>{mealEntries.map(entry => <li key={entry.rowId}>{entry.description} — {entry.quantity} {entry.unit}</li>)}</ul></div>; })}
                </div>)}
              </div>
              <div className="ci3-result-block">
                <h3>Nutrition at a glance</h3>
                <p className="ci3-muted">
                  This is the total across all selected days, not a daily
                  average.
                </p>
                <NutrientGrid summary={analysis.complete_plan_total} />
              </div>
              <div className="ci3-result-block">
                <h3>Daily nutrition</h3>
                <p className="ci3-muted">Totals for the foods entered on each day.</p>
                {Object.entries(analysis.daily_nutrients || {}).map(
                  ([day, summary]) => (
                    <div className="ci3-daily-result" key={day}>
                      <h4>{formatDay(day)}</h4>
                      <NutrientGrid summary={summary} />
                    </div>
                  ),
                )}
              </div>
              <div className="ci3-result-block">
                <h3>What to know about your meal</h3>
                <p className="ci3-muted">Simple findings from the nutrition references. These are guidance comparisons, not medical limits for a single meal.</p>
                {Object.entries(analysis.meal_assessments || {}).map(([mealKey, assessment]) => (
                  <article className="ci3-daily-result" key={`assessment-${mealKey}`}>
                    <h4>{mealKey}</h4>
                    <p><strong>{assessment.label || "Nutrient-reference assessment"}</strong></p>
                    {(assessment.items || []).map((item) => (
                      <p key={`${mealKey}-${item.nutrient}`}><strong>{item.nutrient}:</strong> {item.message}</p>
                    ))}
                    {(assessment.suggestions || []).map((suggestion, index) => (
                      <p key={`${mealKey}-suggestion-${index}`}>Suggestion: {suggestion}</p>
                    ))}
                    {(assessment.notes || []).map((note, index) => (
                      <p key={`${mealKey}-note-${index}`} className="ci3-muted">{note}</p>
                    ))}
                  </article>
                ))}
              </div>
              <div className="ci3-result-block">
                <h3>Daily diet estimate (AI)</h3>
                <p className="ci3-muted">Available only when you marked the entries as your full day. This estimates a research category, not medical suitability.</p>
                {Object.entries(analysis.daily_ml_alignment_estimates || {}).map(([day, result]) => (
                  <article className="ci3-daily-result" key={`ml-${day}`}>
                    <h4>{formatDay(day)}</h4>
                    {result.status === "estimated" ? (
                      <>
                        <p><strong>Estimated category:</strong> {result.predicted_daily_alignment_proxy === "reference_aligned_proxy" ? "Reference-aligned proxy" : "Needs review proxy"}</p>
                        <p><strong>Model:</strong> {result.model}</p>
                        {result.confidence !== null && result.confidence !== undefined && <p><strong>Model confidence:</strong> {(result.confidence * 100).toFixed(1)}% (not clinical certainty)</p>}
                        <p className="ci3-muted">{result.explanation}</p>
                      </>
                    ) : (
                      <p className="ci3-muted">{result.reason || "ML estimate unavailable."} {result.missing_features?.length ? `Missing: ${result.missing_features.join(", ")}.` : ""}</p>
                    )}
                  </article>
                ))}
              </div>
              <details className="ci3-technical-details"><summary>About the research model</summary><p>The daily AI estimate is trained on categories created from nutrition rules. It is not a doctor-labelled meal suitability prediction. Daily DASH optimization is a separate research tool.</p></details>
            </>
          )}
        </section>
      )}
      {step === 3 && (
        <div className="ci3-result-actions">
          <button
            type="button"
            className="ci3-button ci3-button-secondary"
            onClick={() => {
              setAnalysisError("");
              setStep(2);
            }}
          >
            Back to edit meals
          </button>
          {!analysis && !analyzing && (
            <button
              type="button"
              className="ci3-button"
              onClick={submitAnalysis}
            >
              Analyze plan
            </button>
          )}
          {analysis && (
            <button
              type="button"
              className="ci3-button"
              onClick={submitAnalysis}
              disabled={analyzing}
            >
              Recalculate nutrition
            </button>
          )}
        </div>
      )}
      <footer className="ci3-footer">
        Component 3 · Hypertension Dietary Risk Assessment System · Research
        prototype
      </footer>
    </main>
  );
}
