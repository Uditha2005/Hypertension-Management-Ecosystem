import axios from "axios";

const API_BASE_URL =
  process.env.REACT_APP_NUTRITION_API_URL || "http://127.0.0.1:8000";

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
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
