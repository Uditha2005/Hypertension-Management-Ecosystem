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
  getFoodDetails,
  saveMealRecord,
  submitRecommendationFeedback,
  optimizeCurrentDayDash,
} from "../services/nutritionApi";
import "./NutritionalIntelligence.css";
// Temporarily hidden: meal history/feedback needs a persistence and profile strategy.
// import Component3MealHistory from "./Component3MealHistory";

const MEALS = ["Breakfast", "Lunch", "Dinner", "Snacks"];
const UNIT_LABELS = {
  g: "grams (g)",
  kg: "kilograms (kg)",
  serving: "serving(s) as defined by USDA",
};

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
  referenceUnit: "",
  referenceQuantity: null,
  servingSize: null,
  servingSizeUnit: "",
  supportedUnits: [],
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
      {["Choose days", "Add foods", "View results"].map((label, index) => {
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
  const supportedUnits = entry.supportedUnits || [];
  const changeUnit = (nextUnit) => {
    const quantity = Number(entry.quantity);
    let converted = entry.quantity;
    const size = Number(entry.servingSize);
    const servingHasGramBasis = String(entry.servingSizeUnit || "").toLowerCase() === "g" && Number.isFinite(size) && size > 0;
    if (entry.quantity !== "" && Number.isFinite(quantity) && quantity > 0) {
      if (entry.unit === "g" && nextUnit === "kg") converted = String(quantity / 1000);
      else if (entry.unit === "kg" && nextUnit === "g") converted = String(quantity * 1000);
      else if (servingHasGramBasis && entry.unit === "serving" && nextUnit === "g") converted = String(quantity * size);
      else if (servingHasGramBasis && entry.unit === "serving" && nextUnit === "kg") converted = String(quantity * size / 1000);
      else if (servingHasGramBasis && entry.unit === "g" && nextUnit === "serving") converted = String(quantity / size);
      else if (servingHasGramBasis && entry.unit === "kg" && nextUnit === "serving") converted = String(quantity * 1000 / size);
    }
    onChange(entry.rowId, "quantity", converted);
    onChange(entry.rowId, "unit", nextUnit);
  };
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
            onChange={(event) => changeUnit(event.target.value)}
            disabled={!supportedUnits.length}
          >
            {supportedUnits.map((unit) => (
              <option value={unit} key={unit}>{UNIT_LABELS[unit] || unit}</option>
            ))}
          </select>
        </label>
        {entry.servingNote && <p className="ci3-serving-note">{entry.servingNote}</p>}
        {!supportedUnits.length && <p className="ci3-serving-note">Loading USDA quantity basis or this record could not be validated. Analysis is blocked until the record is reselected.</p>}
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
  const [confirmedMedications, setConfirmedMedications] = useState("");
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
  const [dashOptimizationResults, setDashOptimizationResults] = useState({});
  const [dashOptimizationLoading, setDashOptimizationLoading] = useState(false);
  const [savedMealRecordId, setSavedMealRecordId] = useState("");
  const [feedbackState, setFeedbackState] = useState({});
  const [analysisError, setAnalysisError] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const searchSequence = useRef(0);

  // Run the daily DASH food-group optimizer against the actual entered foods.
  // Only quantities with a defensible gram basis are submitted; unknowns are not guessed.
  useEffect(() => {
    if (step !== 3 || !analysis) return;
    let cancelled = false;
    const gramsForEntry = (entry) => {
      const quantity = Number(entry.quantity);
      if (!Number.isFinite(quantity) || quantity <= 0) return null;
      if (entry.unit === "g") return quantity;
      if (entry.unit === "kg") return quantity * 1000;
      const size = Number(entry.servingSize);
      if (entry.unit === "serving" && String(entry.servingSizeUnit || "").toLowerCase() === "g" && Number.isFinite(size) && size > 0) return quantity * size;
      return null;
    };
    const run = async () => {
      setDashOptimizationLoading(true);
      setDashOptimizationResults({});
      console.info("[DASH OPTIMIZER] Starting optimization after successful meal-plan analysis.", {
        selectedDays, entryCount: entries.length,
      });
      const results = {};
      for (const day of selectedDays) {
        const dayItems = entries.filter((entry) => entry.day === day).map((entry) => ({
          food_name: entry.description,
          quantity_grams: gramsForEntry(entry),
        }));
        const validItems = dayItems.filter((item) => item.food_name?.trim() && item.quantity_grams != null);
        if (!validItems.length) {
          results[day] = { status: "unavailable", message: "No foods on this day have a confirmed gram quantity, so the optimizer did not guess serving conversions." };
          continue;
        }
        try {
          console.info("[DASH OPTIMIZER] POST /dash/optimize-current-day", {
            day, submittedFoodCount: validItems.length, validItems,
          });
          results[day] = await optimizeCurrentDayDash(validItems);
          console.info("[DASH OPTIMIZER] Response received", {
            day, status: results[day]?.status,
            changes: results[day]?.changes?.length ?? 0,
            matchedFoods: results[day]?.matched_foods?.length ?? 0,
            unmatchedFoods: results[day]?.unmatched_foods?.length ?? 0,
            mlModelUsed: results[day]?.ml_preference_model?.used ?? false,
            mlModel: results[day]?.ml_preference_model?.model ?? null,
          });
        } catch (error) {
          console.error("[DASH OPTIMIZER] Request failed", {
            day, message: getApiErrorMessage(error),
            status: error?.response?.status,
          });
          results[day] = { status: "unavailable", message: getApiErrorMessage(error) };
        }
        if (cancelled) return;
        setDashOptimizationResults({ ...results });
      }
      if (!cancelled) setDashOptimizationLoading(false);
    };
    run();
    return () => { cancelled = true; };
  }, [step, analysis]); // analysis is replaced after each successful recalculation

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
    for (const item of chosen) {
      const grams = Number(item.editedGrams);
      if (!Number.isFinite(grams) || grams <= 0 || grams > 5000) { setPhotoError(`Enter a portion between 1 and 5,000 g for ${item.editedName}.`); return; }
    }
    setPhotoBusy(true); setPhotoError("");
    try {
      const added = [];
      const unresolved = [];
      for (const item of chosen) {
        const grams = Number(item.editedGrams);
        const result = await searchFoods(item.editedName.trim(), 5);
        const food = (result.foods || [])[0];
        if (!food) { unresolved.push(item.editedName); continue; }
        const details = await getFoodDetails(food.fdc_id);
        const unit = details.supported_units.includes("g") ? "g" : details.supported_units[0];
        let quantity = String(grams);
        let servingNote = `Suggested from photo as “${item.editedName}”. Estimated portion: ${grams} g. Please check the food name and portion; photo estimates are approximate.`;
        if (unit === "serving") {
          const size = details.serving_size;
          if (details.serving_size_unit?.toLowerCase() === "g" && size > 0) quantity = String(grams / size);
          else { quantity = ""; servingNote += " This record has no safe gram-to-serving conversion; enter the serving quantity before analysis."; }
        }
        added.push({...newEntry(activeDay,activeMeal), fdc_id:String(food.fdc_id), description:food.description, quantity, unit, referenceUnit:details.reference_unit, referenceQuantity:details.reference_quantity, servingSize:details.serving_size, servingSizeUnit:details.serving_size_unit, supportedUnits:details.supported_units, servingNote});
      }
      setEntries(current => [...current, ...added]); setAnalysis(null);
      setPhotoMessage(`${added.length} food(s) added using the first USDA search match. Review the food names and portions below.${unresolved.length ? ` Could not find matches for: ${unresolved.join(", ")}. Add these manually using food search.` : ""}`);
      if (unresolved.length) setPhotoError(`No USDA match found for: ${unresolved.join(", ")}.`);
      setPhotoSuggestions([]); setPhotoFile(null);
    } catch (error) { setPhotoError(getApiErrorMessage(error)); }
    finally { setPhotoBusy(false); }
  };

  const addFood = async (food) => {
    setSearchError("");
    try {
      const details = await getFoodDetails(food.fdc_id);
      const unit = details.supported_units.includes("g") ? "g" : details.supported_units[0];
      let quantity = "";
      let servingNote = `Nutrient values are based on ${details.reference_quantity} ${details.reference_unit}. Only compatible units are enabled.`;
      if (unit === "serving" && details.serving_size_unit?.toLowerCase() === "g" && details.serving_size > 0) {
        quantity = String(details.serving_size);
        servingNote += ` USDA lists ${details.serving_size} g per serving.`;
      } else if (unit === "serving") {
        quantity = "1";
        servingNote += " Confirm the serving quantity against the package or recipe.";
      } else {
        quantity = "100";
      }
      setEntries(current => [...current, {...newEntry(activeDay,activeMeal), fdc_id:String(food.fdc_id), description:details.description, quantity, unit, referenceUnit:details.reference_unit, referenceQuantity:details.reference_quantity, servingSize:details.serving_size, servingSizeUnit:details.serving_size_unit, supportedUnits:details.supported_units, servingNote}]);
      setAnalysis(null);
    } catch (error) {
      setSearchError(`Could not validate this USDA record: ${getApiErrorMessage(error)} Choose another record.`);
    }
  };

  const validateMeals = () => {
    if (!entries.length) return "Add at least one food to the meal plan.";
    for (const [index, entry] of entries.entries()) {
      if (!entry.fdc_id)
        return `Food ${index + 1} needs a USDA search result before analysis.`;
      if (!entry.supportedUnits?.length)
        return `${entry.description || `Food ${index + 1}`} has not been validated against its USDA nutrient reference. Remove and reselect this food.`;
      if (!entry.supportedUnits.includes(entry.unit))
        return `${entry.description || `Food ${index + 1}`} cannot be safely measured in ${entry.unit}. Choose one of: ${entry.supportedUnits.join(", ")}.`;
      const quantity = Number(entry.quantity);
      const quantityLimit = entry.unit === "g" ? 5000 : entry.unit === "kg" ? 5 : entry.unit === "serving" ? 50 : 0;
      if (
        !entry.quantity ||
        !Number.isFinite(quantity) ||
        quantity <= 0 ||
        !quantityLimit ||
        quantity > quantityLimit
      )
        return `${entry.description || `Food ${index + 1}`} needs a quantity greater than 0 and no more than ${quantityLimit || "the supported limit for"} ${entry.unit || "its selected unit"}.`;
    }
    return "";
  };
  const goToBuild = () => {
    setAnalysisError("");
    setStep(2);
  };
  const submitAnalysis = async (event) => {
    event.preventDefault();
    const age = Number(ageYears);
    if (!Number.isFinite(age) || age <= 18 || age >= 120) {
      setAnalysisError("Enter an age between 19 and 119 years.");
      return;
    }
    if (bmi.trim() && (!Number.isFinite(Number(bmi)) || Number(bmi) <= 10 || Number(bmi) >= 100)) {
      setAnalysisError("BMI must be greater than 10 and less than 100, or left blank.");
      return;
    }
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
        entries: entries.map(({ day, meal, description, fdc_id, quantity, unit }) => ({
          day,
          meal,
          description,
          fdc_id: Number(fdc_id),
          quantity: Number(quantity),
          unit,
        })),
        selected_days: selectedDays,
        personal_profile: {
          age_years: Number(ageYears),
          bmi: bmi.trim() ? Number(bmi) : null,
          dietary_requirements: dietaryRequirements.split(",").map((item) => item.trim()).filter(Boolean),
          confirmed_medications: confirmedMedications.split(",").map((item) => item.trim()).filter(Boolean),
          dietary_preferences: [],
          dietary_restrictions: [],
          allergies: [],
          preferred_foods: [],
          nutrition_goal: "dash_style",
        },
        full_day_intake: false,
      };
      const analysisResult = await analyzeMealPlan(payload);
      setAnalysis(analysisResult);
      setSavedMealRecordId("");
      setFeedbackState({});
      // History persistence is best-effort: an unavailable store should not hide
      // the successfully calculated analysis from the user.
      try {
        const saved = await saveMealRecord({
          meal_date: selectedDays[0],
          meals: entries.map(({ day, meal, description, fdc_id, quantity, unit }) => ({ day, meal, description, fdc_id: Number(fdc_id), quantity: Number(quantity), unit })),
          analysis: analysisResult,
        });
        setSavedMealRecordId(saved?.record?.record_id || "");
      } catch (historyError) {
        console.warn("Meal analysis succeeded but could not be saved to history.", historyError);
      }
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
            Build meals from searched or photo-identified foods, review portions, calculate nutrient totals, and see practical food-based suggestions with cautious medication-related reminders where applicable.
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
              <p className="ci3-eyebrow">YOUR MEALS</p>
              <h2 id="setup-title">Choose the days you want to review</h2>
              <p>
                Choose a day, add the foods you ate, and enter the requested details for this assessment.
              </p>
            </div>
          </div>
          <div className="ci3-plan-choice">
            <h3>About you (for this assessment)</h3>
            <p>Enter these details each time. They are not saved as a personal profile.</p>
            <div className="ci3-entry-grid">
              <label>Age (years)
                <input type="number" min="19" max="119" value={ageYears} onChange={(event) => setAgeYears(event.target.value)} required />
              </label>
              <label>BMI (optional)
                <input type="number" min="10" max="100" step="0.1" value={bmi} onChange={(event) => setBmi(event.target.value)} placeholder="e.g. 26.5" />
              </label>
              <label>Dietary requirements (optional, comma-separated)
                <input value={dietaryRequirements} onChange={(event) => setDietaryRequirements(event.target.value)} placeholder="e.g. lower sodium, vegetarian" />
              </label>
            </div>
            <label>Confirmed medicine active ingredients (optional, comma-separated)
              <input value={confirmedMedications} onChange={(event) => setConfirmedMedications(event.target.value)} placeholder="e.g. ramipril, spironolactone" />
              <small>Optional. Enter only medicine ingredients you have confirmed from the packaging or prescription.</small>
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
                  {MEALS.map(meal => { const mealEntries = entries.filter(entry => entry.day === day && entry.meal === meal); if (!mealEntries.length) return null; return <div className="ci3-entered-meal" key={`${day}-${meal}`}><strong>{meal}</strong><ul>{mealEntries.map(entry => <li key={entry.rowId}>
                    <strong>{entry.description}</strong> — {entry.quantity} {entry.unit}
                  </li>)}</ul></div>; })}
                </div>)}
              </div>
              <div className="ci3-result-block">
                <h3>Your nutrition summary</h3>
                <p className="ci3-muted">
                  This is the total across all selected days, not a daily
                  average.
                </p>
                <NutrientGrid summary={analysis.complete_plan_total} />
              </div>
              <div className="ci3-result-block">
                <h3>Daily nutrition</h3>
                <p className="ci3-muted">Totals for the foods entered for this day.</p>
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
                <h3>Ways to improve your daily food choices</h3>
                <p className="ci3-muted">Your recorded foods will not be changed. These are optional ideas for your day.</p>
                {dashOptimizationLoading && <p className="ci3-muted" role="status">Finding possible improvements…</p>}
                {selectedDays.map((day) => {
                  const result = dashOptimizationResults[day];
                  if (!result) return null;
                  const groupLabel = (raw) => {
                    const value = String(raw || "").toLowerCase();
                    if (/raw apple|apricot|avocado|banana|cantaloupe|cherries|fig|grapes|mango|pear|pineapple|fruit/.test(value)) return "Fruit";
                    if (/vegetable|tomato|leafy|greens/.test(value)) return "Vegetables";
                    if (/potato/.test(value)) return "Potatoes";
                    if (/pancake|waffle/.test(value)) return "Pancakes or waffles";
                    if (/seed/.test(value)) return "Seeds";
                    if (/smoothie/.test(value)) return "Fruit or vegetable smoothie";
                    if (/whole grain|grain|oat|rice|bread/.test(value)) return "Grains";
                    if (/bean|lentil|legume|pea/.test(value)) return "Beans and lentils";
                    if (/dairy|milk|yogurt|cheese/.test(value)) return "Dairy foods";
                    if (/nut/.test(value)) return "Nuts";
                    return String(raw || "Food group").replaceAll("/", " / ");
                  };
                  const plainReason = (raw) => {
                    const value = String(raw || "").toLowerCase();
                    if (value.includes("starting daily profile") || value.includes("lower bound") || value.includes("constraint")) return "This change moves your estimated daily food pattern closer to the balanced pattern used by this tool.";
                    return "This is part of the overall daily balance suggested by the tool; it is not proof of a specific health benefit.";
                  };
                  return <article className="ci3-daily-result" key={`dash-optimization-${day}`}>
                    <h4>{formatDay(day)}</h4>
                    {result.status === "unavailable" ? <p className="ci3-muted">{result.message || "Suggestions could not be prepared for this day. Your food log has not changed."}</p> : result.status !== "optimal" ? <p className="ci3-muted">We could not find a reliable set of changes for this day, so no suggestions are shown. Your food log has not changed.</p> : <>
                      <p className="ci3-muted" role="status">
                        {result.ml_preference_model?.used
                          ? "These optional ideas combine learned dietary patterns with DASH-based calculations. They are not medical advice."
                          : "These optional ideas were calculated using the DASH-based tool."}
                      </p>
                      {(result.changes || []).length ? <ul>{result.changes.slice(0, 5).map((change) => <li key={change.food_group_code}>
                        <strong>{groupLabel(change.food_group)}:</strong> {Number(change.current_servings).toFixed(1)} to {Number(change.suggested_servings).toFixed(1)} servings
                        <p className="ci3-muted"><strong>Why:</strong> {plainReason(change.reason)}</p>
                      </li>)}</ul> : <p>No changes were suggested for this day.</p>}
                      {(result.unmatched_foods || []).length > 0 && <p className="ci3-muted">Some foods could not be matched to a food group, so the suggestions may not account for them: {result.unmatched_foods.map(item => item.food_name).join(", ")}.</p>}
                      <p className="ci3-muted">These are general suggestions, not medical advice. Choose only changes that suit you.</p>
                    </>}
                  </article>;
                })}
              </div>
              <div className="ci3-result-block ci3-reference-details-block">
                <h3>More nutrition details (optional)</h3>
                <details className="ci3-reference-details">
                  <summary>View detailed nutrition information</summary>
                  <p className="ci3-muted">These are general reference comparisons, not medical limits for a single meal.</p>
                  {Object.entries(analysis.meal_assessments || {}).map(([mealKey, assessment]) => (
                    <article className="ci3-daily-result" key={`assessment-${mealKey}`}>
                      <h4>{mealKey}</h4>
                      <p><strong>{assessment.label || "Nutrient-reference assessment"}</strong></p>
                      {(assessment.items || []).map((item) => (
                        <p key={`${mealKey}-${item.nutrient}`}><strong>{item.nutrient}:</strong> {item.message}</p>
                      ))}
                      {(assessment.notes || []).map((note, index) => (
                        <p key={`${mealKey}-note-${index}`} className="ci3-muted">{note}</p>
                      ))}
                    </article>
                  ))}
                </details>
              </div>

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
      {/* Temporarily hidden until persistent user-specific storage is restored.
      <Component3MealHistory />
      */}
      <footer className="ci3-footer">
        Component 3 · Hypertension Dietary Risk Assessment System · Research
        prototype
      </footer>
    </main>
  );
}
