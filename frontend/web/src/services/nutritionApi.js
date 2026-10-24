import axios from "axios";

const API_BASE_URL =
  process.env.REACT_APP_NUTRITION_API_URL || "http://127.0.0.1:8000";

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // Allow up to 120 seconds for USDA-backed full-plan analysis and DASH optimization.
  headers: { "Content-Type": "application/json" },
});

export async function checkNutritionApiHealth() {
  const { data } = await client.get("/health");
  return data;
}

export async function searchFoods(query, limit = 10) {
  const { data } = await client.get("/foods/search", {
    params: { query, limit },
  });
  return data;
}

export async function findFoodAlternatives(fdcId, quantityUnit = "g", limit = 5) {
  const { data } = await client.post("/foods/alternatives", {
    fdc_id: fdcId,
    quantity_unit: quantityUnit,
    limit,
  });
  return data;
}

export async function getFoodDetails(fdcId) {
  const { data } = await client.get(`/foods/${encodeURIComponent(fdcId)}/details`);
  return data;
}

export async function analyzeMealPlan(payload) {
  const { data } = await client.post("/meal-plans/analyze", payload);
  return data;
}

export function getApiErrorMessage(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || "Invalid input").join("; ");
  }
  if (error?.code === "ECONNABORTED") {
    return "The request timed out. Please try again.";
  }
  if (error?.message === "Network Error") {
    return "Cannot reach the nutrition API. Check that it is running and that CORS permits this frontend origin.";
  }
  return error?.message || "An unexpected error occurred.";
}

export async function identifyFoodsFromImage(imageDataUrl, mealContext) {
  const { data } = await client.post("/foods/identify-image", {
    image_data_url: imageDataUrl,
    meal_context: mealContext,
  }, { timeout: 60000 });
  return data;
}


export async function saveMealRecord(payload) {
  const { data } = await client.post("/meal-records", payload);
  return data;
}

export async function getMealRecords(limit = 30) {
  const { data } = await client.get("/meal-records", { params: { limit } });
  return data;
}

export async function submitRecommendationFeedback(recordId, feedback) {
  const { data } = await client.post(`/meal-records/${encodeURIComponent(recordId)}/feedback`, feedback);
  return data;
}

export async function getNutritionContext(days = 7) {
  const { data } = await client.get("/nutrition-context", { params: { days } });
  return data;
}

export async function getRecommendationFeedback(limit = 100) {
  const { data } = await client.get("/recommendation-feedback", { params: { limit } });
  return data;
}

export async function optimizeCurrentDayDash(items) {
  const { data } = await client.post("/dash/optimize-current-day", { items });
  return data;
}
