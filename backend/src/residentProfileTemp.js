const fs = require("node:fs");
const path = require("node:path");
const { DatabaseSync } = require("node:sqlite");
const express = require("express");

const STORAGE_MODE = "temporary-sqlite";

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

module.exports = function createTemporaryResidentProfileRouter(
  authenticate
) {
  if (typeof authenticate !== "function") {
    throw new Error("Resident profile API requires authentication.");
  }

  const router = express.Router();
  const dataDirectory = path.resolve(__dirname, "../data");

  fs.mkdirSync(dataDirectory, { recursive: true });

  // Temporary prototype storage. This file is ignored by Git.
  const db = new DatabaseSync(
    path.join(dataDirectory, "component1_resident_profiles_temp.sqlite3")
  );

  db.exec(`
    PRAGMA journal_mode = WAL;

    CREATE TABLE IF NOT EXISTS resident_profiles (
      user_id TEXT PRIMARY KEY,
      profile_json TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
  `);



   router.get("/", authenticate, (req, res, next) => {
    try {
      const row = db.prepare(`
        SELECT profile_json, updated_at
        FROM resident_profiles
        WHERE user_id = ?
      `).get(req.account.id);

      if (!row) {
        return res.json({
          profile: null,
          updatedAt: null,
          storageMode: STORAGE_MODE,
        });
      }

      return res.json({
        profile: JSON.parse(row.profile_json),
        updatedAt: row.updated_at,
        storageMode: STORAGE_MODE,
      });
    } catch (error) {
      next(error);
    }
  });

  router.put("/", authenticate, (req, res, next) => {
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

      const updatedAt = new Date().toISOString();

        db.prepare(`
         INSERT INTO resident_profiles (
          user_id, profile_json, updated_at
        )
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
          profile_json = excluded.profile_json,
          updated_at = excluded.updated_at
      `).run(
        req.account.id,
        JSON.stringify(profile),
        updatedAt
      );

      return res.json({
        profile,
        updatedAt,
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
      console.error("Temporary resident profile error:", error.message);
    }

    return res.status(status).json({
      error:
        status >= 500
          ? "Could not access the temporary resident profile."
          : error.message,
    });
  });

  return router;
};