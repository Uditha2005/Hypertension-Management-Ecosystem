const fs = require("node:fs");
const path = require("node:path");
const { DatabaseSync } = require("node:sqlite");
const express = require("express");

const STORAGE_MODE = "temporary-sqlite";
const MAX_HISTORY_RECORDS = 100;

function validationError(message) {
  const error = new Error(message);
  error.status = 422;
  return error;
}

function isObject(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value)
  );
}

function requiredNumber(value, label, min, max, integer = false) {
  const number = Number(value);

  if (
    value === undefined ||
    value === null ||
    value === "" ||
    !Number.isFinite(number) ||
    number < min ||
    number > max ||
    (integer && !Number.isInteger(number))
  ) {
    throw validationError(
      `Enter a valid ${label} between ${min} and ${max}.`
    );
  }

  return number;
}

function validateAssessment(body) {
  if (!isObject(body)) {
    throw validationError("Send a valid assessment object.");
  }

  if (!isObject(body.inputs)) {
    throw validationError("Assessment inputs are required.");
  }

  if (!isObject(body.result)) {
    throw validationError("The successful AI assessment result is required.");
  }

  const source = body.inputs;

  if (!["female", "male"].includes(source.sex)) {
    throw validationError("Invalid sex value.");
  }

  if (typeof source.diabetes_history !== "boolean") {
    throw validationError("Diabetes history must be true or false.");
  }

  if (typeof source.has_existing_hypertension !== "boolean") {
    throw validationError(
      "Existing hypertension status must be true or false."
    );
  }

  return {
    inputs: {
      age: requiredNumber(source.age, "age", 60, 74, true),
      sex: source.sex,
      systolic_bp: requiredNumber(
        source.systolic_bp,
        "systolic blood pressure",
        70,
        300
      ),
      diastolic_bp: requiredNumber(
        source.diastolic_bp,
        "diastolic blood pressure",
        30,
        180
      ),
      pulse_rate: requiredNumber(
        source.pulse_rate,
        "pulse rate",
        30,
        200
      ),
      height_cm: requiredNumber(
        source.height_cm,
        "height",
        100,
        220
      ),
      weight_kg: requiredNumber(
        source.weight_kg,
        "weight",
        25,
        300
      ),
      diabetes_history: source.diabetes_history,
      has_existing_hypertension:
        source.has_existing_hypertension,
    },
    result: body.result,
  };
}

module.exports = function createAssessmentHistoryRouter(authenticate) {
  if (typeof authenticate !== "function") {
    throw new Error("Assessment history requires authentication.");
  }

  const router = express.Router();
  const dataDirectory = path.resolve(__dirname, "../data");

  fs.mkdirSync(dataDirectory, { recursive: true });

  // Temporary prototype storage, separate from resident profiles.
  const db = new DatabaseSync(
    path.join(
      dataDirectory,
      "component1_assessment_history_temp.sqlite3"
    )
  );

  db.exec(`
    PRAGMA journal_mode = WAL;

    CREATE TABLE IF NOT EXISTS assessment_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id TEXT NOT NULL,
      assessed_at TEXT NOT NULL,
      inputs_json TEXT NOT NULL,
      result_json TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_assessment_history_user_date
      ON assessment_history(user_id, assessed_at DESC);
  `);

  // Retrieve the latest 100 records for the signed-in account.
  router.get("/", authenticate, (req, res, next) => {
    try {
      const rows = db.prepare(`
        SELECT id, assessed_at, inputs_json, result_json
        FROM assessment_history
        WHERE user_id = ?
        ORDER BY assessed_at DESC, id DESC
        LIMIT ?
      `).all(req.account.id, MAX_HISTORY_RECORDS);

      const history = rows.map((row) => ({
        id: row.id,
        assessedAt: row.assessed_at,
        inputs: JSON.parse(row.inputs_json),
        result: JSON.parse(row.result_json),
      }));

      return res.json({
        history,
        storageMode: STORAGE_MODE,
      });
    } catch (error) {
      next(error);
    }
  });

  // Save a successfully completed assessment.
  router.post("/", authenticate, (req, res, next) => {
    try {
      const { inputs, result } = validateAssessment(req.body);
      const assessedAt = new Date().toISOString();

      const saved = db.prepare(`
        INSERT INTO assessment_history (
          user_id,
          assessed_at,
          inputs_json,
          result_json
        )
        VALUES (?, ?, ?, ?)
      `).run(
        req.account.id,
        assessedAt,
        JSON.stringify(inputs),
        JSON.stringify(result)
      );

      return res.status(201).json({
        record: {
          id: Number(saved.lastInsertRowid),
          assessedAt,
          inputs,
          result,
        },
        storageMode: STORAGE_MODE,
      });
    } catch (error) {
      next(error);
    }
  });

  router.use((error, req, res, next) => {
    if (res.headersSent) return next(error);

    const status = error.status || 500;

    if (status >= 500) {
      console.error(
        "Temporary assessment history error:",
        error.message
      );
    }

    return res.status(status).json({
      error:
        status >= 500
          ? "Could not access temporary assessment history."
          : error.message,
    });
  });

  return router;
};