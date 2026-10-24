
require("dotenv").config();

const express = require("express");
const cors = require("cors");

const app = express();

app.use(cors());
app.use(express.json());
app.use("/api/auth", require("./auth"));

const AI_SERVICE_URL = (
  process.env.COMPONENT1_AI_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

// Existing backend health route
app.get("/", (req, res) => {
  res.send("Hypertension Management Ecosystem backend running");
});

// Check whether the Python AI service is available
app.get("/api/component1/health", async (req, res) => {
  try {
    const response = await fetch(`${AI_SERVICE_URL}/health`, {
      signal: AbortSignal.timeout(5000),
    });

    const result = await response.json();

    return res.status(response.status).json(result);
  } catch (error) {
    console.error("Component 1 health check failed:", error.message);

    return res.status(503).json({
      error: "AI service unavailable",
      message: "Check that the Python AI service is running.",
    });
  }
});

// Forward patient inputs to the Python prediction service
app.post("/api/component1/predict", async (req, res) => {
  try {
    const response = await fetch(`${AI_SERVICE_URL}/predict`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(req.body),
      signal: AbortSignal.timeout(20000),
    });

    const responseText = await response.text();

    let result;

    try {
      result = JSON.parse(responseText);
    } catch {
      result = {
        error: "The AI service returned an invalid response.",
      };
    }

    return res.status(response.status).json(result);
  } catch (error) {
    console.error("Component 1 prediction request failed:", error.message);

    const timedOut =
      error.name === "TimeoutError" || error.name === "AbortError";

    return res.status(timedOut ? 504 : 503).json({
      error: timedOut ? "AI service timed out" : "AI service unavailable",
      message: timedOut
        ? "The prediction service did not respond in time."
        : "Check that the Python AI service is running.",
    });
  }
});

const PORT = process.env.PORT || 5000;

// Component 2: Behavioral AI status
app.get("/api/behavioral/status", async (req, res) => {
  try {
    const response = await fetch(
      "http://127.0.0.1:8000/api/behavioral/status",
      { signal: AbortSignal.timeout(5000) }
    );

    const result = await response.json();
    return res.status(response.status).json(result);
  } catch (error) {
    console.error("Component 2 status check failed:", error.message);

    return res.status(503).json({
      connected: false,
      error: "Behavioral AI service unavailable",
      message: "Check that the Component 2 Python AI service is running.",
    });
  }
});

app.listen(PORT, () => {
  console.log(`Backend running on port ${PORT}`);
});
