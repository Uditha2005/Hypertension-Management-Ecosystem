
const express = require("express");
const pool = require("./db");

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
    throw validationError(
      "The successful AI assessment result is required."
    );
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
      pulse_rate: requiredNumber(source.pulse_rate, "pulse rate", 30, 200),
      height_cm: requiredNumber(source.height_cm, "height", 100, 220),
      weight_kg: requiredNumber(source.weight_kg, "weight", 25, 300),
      diabetes_history: source.diabetes_history,
      has_existing_hypertension: source.has_existing_hypertension,
    },
    result: body.result,
  };
}

module.exports = function createAssessmentHistoryRouter(authenticate) {
  if (typeof authenticate !== "function") {
    throw new Error("Assessment history requires authentication.");
  }

  const router = express.Router();

  // Retrieve up to 100 assessments for the signed-in account.
  router.get("/", authenticate, async (req, res, next) => {
    try {
      const result = await pool.query(
        `SELECT id, assessed_at, inputs, result
         FROM public.component1_assessment_history
         WHERE local_account_id = $1
         ORDER BY assessed_at DESC, id DESC
         LIMIT $2`,
        [req.account.id, MAX_HISTORY_RECORDS]
      );

      const history = result.rows.map((row) => ({
        id: Number(row.id),
        assessedAt: row.assessed_at,
        inputs: row.inputs,
        result: row.result,
      }));

      return res.json({
        history,
        storageMode: "neon-postgresql",
      });
    } catch (error) {
      next(error);
    }
  });

  // Save a successfully completed assessment in Neon.
  router.post("/", authenticate, async (req, res, next) => {
    try {
      const { inputs, result: assessmentResult } =
        validateAssessment(req.body);

      const assessedAt = new Date().toISOString();

      const saved = await pool.query(
        `INSERT INTO public.component1_assessment_history
           (local_account_id, assessed_at, inputs, result)
         VALUES ($1, $2, $3::jsonb, $4::jsonb)
         RETURNING id, assessed_at, inputs, result`,
        [
          req.account.id,
          assessedAt,
          JSON.stringify(inputs),
          JSON.stringify(assessmentResult),
        ]
      );

      const row = saved.rows[0];

      return res.status(201).json({
        record: {
          id: Number(row.id),
          assessedAt: row.assessed_at,
          inputs: row.inputs,
          result: row.result,
        },
        storageMode: "neon-postgresql",
      });
    } catch (error) {
      next(error);
    }
  });

  router.use((error, req, res, next) => {
    if (res.headersSent) return next(error);

    const status = error.status || 500;

    if (status >= 500) {
      console.error("Assessment history error:", error.message);
    }

    return res.status(status).json({
      error:
        status >= 500
          ? "Could not access assessment history."
          : error.message,
    });
  });

  return router;
};
