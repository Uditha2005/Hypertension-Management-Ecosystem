
require("dotenv").config();

const express = require("express");
const cors = require("cors");
const authRoutes = require("./routes/auth");

const pool = require("./db");

const app = express();

app.use(cors());
app.use(express.json());

app.use("/api/auth", authRoutes);

app.use(
  "/api/component1/resident-profile",
  require("./residentProfileTemp")(authRoutes.authenticate)
);
app.use(
  "/api/component1/assessment-history",
  require("./assessmentHistoryTemp")(authRoutes.authenticate)
);
const AI_SERVICE_URL = (
  process.env.COMPONENT1_AI_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

// Existing backend health route
app.get("/", (req, res) => {
  res.send("Hypertension Management Ecosystem backend running");
});

// Check PostgreSQL database connection
app.get("/api/db/health", async (req, res) => {
  try {
    const result = await pool.query(
      "SELECT current_database() AS database, NOW() AS server_time"
    );

    return res.json({
      connected: true,
      database: result.rows[0].database,
      serverTime: result.rows[0].server_time,
    });
  } catch (error) {
    console.error("Database health check failed:", error.message);

    return res.status(503).json({
      connected: false,
      error: "Database connection failed",
    });
  }
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


app.post("/api/behavioral/fall-events", async (req, res) => {
  try {
    const {
      residentId,
      residentName,
      trackId,
      probability,
      source,
      videoTimeSeconds,
    } = req.body || {};

    // Validate the event source
    if (!["uploaded_video", "live_camera"].includes(source)) {
      return res.status(400).json({
        error: "source must be uploaded_video or live_camera",
      });
    }

    // Validate probability
    if (
      probability !== undefined &&
      probability !== null &&
      (!Number.isFinite(Number(probability)) ||
        Number(probability) < 0 ||
        Number(probability) > 1)
    ) {
      return res.status(400).json({
        error: "probability must be between 0 and 1",
      });
    }

    const result = await pool.query(
      `INSERT INTO fall_events (
         resident_id,
         resident_name,
         track_id,
         probability,
         source,
         video_time_seconds
       )
       VALUES ($1, $2, $3, $4, $5, $6)
       RETURNING
         id,
         resident_id AS "residentId",
         resident_name AS "residentName",
         track_id AS "trackId",
         probability,
         source,
         occurred_at AS "occurredAt",
         video_time_seconds AS "videoTimeSeconds"`,
      [
        residentId ?? null,
        residentName ?? null,
        trackId == null ? null : String(trackId),
        probability == null ? null : Number(probability),
        source,
        videoTimeSeconds == null
          ? null
          : Number(videoTimeSeconds),
      ]
    );

    return res.status(201).json({
      success: true,
      event: result.rows[0],
    });
  } catch (error) {
    console.error("Failed to save fall event:", error.message);

    return res.status(500).json({
      error: "Could not save fall event",
    });
  }
});



/* Component 2: Fall notification history */
app.get("/api/behavioral/fall-events", async (req, res) => {
  try {
    const { from, to, source } = req.query;

    const conditions = [];
    const values = [];

    if (from) {
      values.push(from);
      conditions.push(`occurred_at >= $${values.length}::date`);
    }

    if (to) {
      values.push(to);
      conditions.push(
        `occurred_at < ($${values.length}::date + INTERVAL '1 day')`
      );
    }

    if (source && source !== "all") {
      if (!["uploaded_video", "live_camera"].includes(source)) {
        return res.status(400).json({
          error: "Invalid source filter",
        });
      }

      values.push(source);
      conditions.push(`source = $${values.length}`);
    }

    const whereClause = conditions.length
      ? `WHERE ${conditions.join(" AND ")}`
      : "";

    const result = await pool.query(
      `SELECT
         id,
         resident_id AS "residentId",
         resident_name AS "residentName",
         track_id AS "trackId",
         probability,
         source,
         occurred_at AS "occurredAt",
         video_time_seconds AS "videoTimeSeconds"
       FROM fall_events
       ${whereClause}
       ORDER BY occurred_at DESC
       LIMIT 500`,
      values
    );

    return res.json({
      events: result.rows,
      count: result.rowCount,
    });
  } catch (error) {
    console.error("Fall history query failed:", error.message);

    return res.status(500).json({
      error: "Could not load fall notification history",
    });
  }
});


app.listen(PORT, () => {
  console.log(`Backend running on port ${PORT}`);
});
