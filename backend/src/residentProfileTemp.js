const express = require("express");
const pool = require("./db");

const STORAGE_MODE = "neon-postgresql";

function validationError(message) {
  const error = new Error(message);
  error.status = 422;
  return error;
}

function optionalNumber(value, label, min, max, integer = false) {
  if (value === undefined || value === null || value === "") {
    return null;
  }

  const number = Number(value);

  if (
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

function optionalChoice(value, label, choices) {
  if (value === undefined || value === null || value === "") {
    return "";
  }

  if (!choices.includes(value)) {
    throw validationError(`Invalid ${label}.`);
  }

  return value;
}

module.exports = function createResidentProfileRouter(authenticate) {
  if (typeof authenticate !== "function") {
    throw new Error("Resident profile API requires authentication.");
  }

  const router = express.Router();

  // Retrieve the profile belonging to the authenticated PostgreSQL user.
  router.get("/", authenticate, async (req, res, next) => {
    try {
      const result = await pool.query(
        `SELECT profile, updated_at
         FROM public.component1_resident_profiles
         WHERE user_id = $1`,
        [req.account.id]
      );

      if (result.rowCount === 0) {
        return res.json({
          profile: null,
          updatedAt: null,
          storageMode: STORAGE_MODE,
        });
      }

      return res.json({
        profile: result.rows[0].profile,
        updatedAt: result.rows[0].updated_at,
        storageMode: STORAGE_MODE,
      });
    } catch (error) {
      next(error);
    }
  });

  // Save or update the profile belonging to the authenticated user.
  router.put("/", authenticate, async (req, res, next) => {
    try {
      if (
        !req.body ||
        typeof req.body !== "object" ||
        Array.isArray(req.body)
      ) {
        throw validationError("Send a valid profile object.");
      }

      const profile = {
        age: optionalNumber(req.body.age, "age", 18, 120, true),
        sex: optionalChoice(
          req.body.sex,
          "sex",
          ["female", "male"]
        ),
        height_cm: optionalNumber(
          req.body.height_cm,
          "height",
          100,
          220
        ),
        weight_kg: optionalNumber(
          req.body.weight_kg,
          "weight",
          25,
          300
        ),
        diabetes_history: optionalChoice(
          req.body.diabetes_history,
          "diabetes history",
          ["yes", "no"]
        ),
        has_existing_hypertension: optionalChoice(
          req.body.has_existing_hypertension,
          "hypertension history",
          ["yes", "no"]
        ),
      };

      const result = await pool.query(
        `INSERT INTO public.component1_resident_profiles
           (user_id, profile, updated_at)
         VALUES ($1, $2::jsonb, NOW())
         ON CONFLICT (user_id) DO UPDATE SET
           profile = EXCLUDED.profile,
           updated_at = NOW()
         RETURNING profile, updated_at`,
        [req.account.id, JSON.stringify(profile)]
      );

      return res.json({
        profile: result.rows[0].profile,
        updatedAt: result.rows[0].updated_at,
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
      console.error("Resident profile error:", error.message);
    }

    return res.status(status).json({
      error:
        status >= 500
          ? "Could not access resident profile."
          : error.message,
    });
  });

  return router;
};