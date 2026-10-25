
const express = require("express");
const crypto = require("node:crypto");
const { promisify } = require("node:util");
const pool = require("../db");

const router = express.Router();
const scrypt = promisify(crypto.scrypt);

const SESSION_LIFETIME_MS = 7 * 24 * 60 * 60 * 1000;
const SCRYPT_OPTIONS = {
  N: 32768,
  r: 8,
  p: 3,
  maxmem: 64 * 1024 * 1024,
};

function failure(status, message) {
  const error = new Error(message);
  error.status = status;
  return error;
}

function clean(value, field, maximum, required = false) {
  if (typeof value !== "string" || value.length > maximum) {
    throw failure(422, `Invalid ${field}.`);
  }

  const result = value.trim();

  if (required && !result) {
    throw failure(422, `Enter ${field}.`);
  }

  return result;
}

function emailAddress(value) {
  const email = clean(value, "email address", 254, true).toLowerCase();

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    throw failure(422, "Enter a valid email address.");
  }

  return email;
}

function passwordValue(value) {
  if (
    typeof value !== "string" ||
    value.length < 10 ||
    value.length > 128 ||
    !value.trim()
  ) {
    throw failure(422, "Use a password between 10 and 128 characters.");
  }

  return value;
}

async function hashPassword(password) {
  const salt = crypto.randomBytes(16).toString("hex");
  const key = await scrypt(password, salt, 64, SCRYPT_OPTIONS);
  return `${salt}:${key.toString("hex")}`;
}

async function checkPassword(password, stored) {
  if (typeof password !== "string" || password.length > 128) {
    return false;
  }

  const parts = String(stored || "").split(":");

  if (
    parts.length !== 2 ||
    !/^[a-f0-9]{32}$/.test(parts[0]) ||
    !/^[a-f0-9]{128}$/.test(parts[1])
  ) {
    return false;
  }

  const expected = Buffer.from(parts[1], "hex");
  const actual = await scrypt(password, parts[0], 64, SCRYPT_OPTIONS);

  return crypto.timingSafeEqual(actual, expected);
}

function digestToken(token) {
  return crypto.createHash("sha256").update(token).digest("hex");
}

function publicUser(user) {
  return {
    id: user.id,
    name: user.name,
    email: user.email,
    phone: user.phone || "",
    careHome: user.care_home || "",
    createdAt: user.created_at,
  };
}

async function issueSession(client, user) {
  const token = crypto.randomBytes(32).toString("hex");
  const expiresAt = Date.now() + SESSION_LIFETIME_MS;

  await client.query(
    `INSERT INTO sessions (token_hash, user_id, expires_at)
     VALUES ($1, $2, $3)`,
    [digestToken(token), user.id, expiresAt]
  );

  return {
    token,
    expiresAt: new Date(expiresAt).toISOString(),
    user: publicUser(user),
  };
}

const attempts = new Map();

function authLimit(req, res, next) {
  const now = Date.now();
  const key = req.ip;
  let record = attempts.get(key);

  if (!record || now >= record.until) {
    record = { count: 0, until: now + 15 * 60 * 1000 };
    attempts.set(key, record);
  }

  record.count += 1;

  if (record.count > 30) {
    res.set("Retry-After", String(Math.ceil((record.until - now) / 1000)));
    return res.status(429).json({
      error: "Too many account requests. Try again later.",
    });
  }

  next();
}

const asyncRoute = (handler) => (req, res, next) =>
  Promise.resolve(handler(req, res, next)).catch(next);

router.use((req, res, next) => {
  res.set("Cache-Control", "no-store");
  next();
});

router.use((req, res, next) => {
  if (
    ["POST", "PATCH"].includes(req.method) &&
    (!req.body || typeof req.body !== "object" || Array.isArray(req.body))
  ) {
    return res.status(400).json({ error: "Send a valid JSON object." });
  }

  next();
});

// POST /api/auth/register
// Body: { name, email, password, phone?, careHome? }
router.post(
  "/register",
  authLimit,
  asyncRoute(async (req, res) => {
    const name = clean(req.body.name, "full name", 100, true);
    const email = emailAddress(req.body.email);
    const password = passwordValue(req.body.password);
    const phone = clean(req.body.phone ?? "", "phone number", 30);
    const careHome = clean(req.body.careHome ?? "", "care home name", 200);

    const passwordHash = await hashPassword(password);
    const id = crypto.randomUUID();
    const client = await pool.connect();

    try {
      await client.query("BEGIN");

      const inserted = await client.query(
        `INSERT INTO users (
           id, name, email, password_hash, phone, care_home,
           created_at, updated_at
         )
         VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
         RETURNING id, name, email, phone, care_home, created_at`,
        [id, name, email, passwordHash, phone, careHome]
      );

      const response = await issueSession(client, inserted.rows[0]);
      await client.query("COMMIT");

      return res.status(201).json(response);
    } catch (error) {
      await client.query("ROLLBACK");

      if (error.code === "23505") {
        throw failure(409, "An account already uses this email address.");
      }

      throw error;
    } finally {
      client.release();
    }
  })
);

// POST /api/auth/login
router.post(
  "/login",
  authLimit,
  asyncRoute(async (req, res) => {
    const email = emailAddress(req.body.email);
    const password = req.body.password;

    if (typeof password !== "string" || password.length > 128) {
      throw failure(401, "Email or password is incorrect.");
    }

    const result = await pool.query(
      `SELECT id, name, email, password_hash, phone, care_home, created_at
       FROM users
       WHERE LOWER(email) = $1
       LIMIT 1`,
      [email]
    );

    const user = result.rows[0];

    if (!user || !(await checkPassword(password, user.password_hash))) {
      throw failure(401, "Email or password is incorrect.");
    }

    const client = await pool.connect();

    try {
      await client.query("BEGIN");

      const latest = await client.query(
        `SELECT id, name, email, password_hash, phone, care_home, created_at
         FROM users
         WHERE id = $1
         FOR UPDATE`,
        [user.id]
      );

      const latestUser = latest.rows[0];

      if (!latestUser || latestUser.password_hash !== user.password_hash) {
        throw failure(401, "Account credentials changed. Sign in again.");
      }

      const response = await issueSession(client, latestUser);
      await client.query("COMMIT");

      return res.json(response);
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  })
);

async function authenticate(req, res, next) {
  try {
    const match = /^Bearer ([a-f0-9]{64})$/i.exec(
      req.headers.authorization || ""
    );

    if (!match) {
      throw failure(401, "Sign in to continue.");
    }

    const sessionHash = digestToken(match[1]);

    const result = await pool.query(
      `SELECT
         u.id,
         u.name,
         u.email,
         u.phone,
         u.care_home,
         u.created_at
       FROM sessions s
       JOIN users u ON u.id = s.user_id
       WHERE s.token_hash = $1
         AND s.expires_at > $2`,
      [sessionHash, Date.now()]
    );

    if (result.rowCount === 0) {
      throw failure(401, "Your session expired. Sign in again.");
    }

    req.sessionHash = sessionHash;
    req.account = result.rows[0];

    return next();
  } catch (error) {
    return next(error);
  }
}


// GET /api/auth/me
router.get(
  "/me",
  authenticate,
  asyncRoute(async (req, res) => {
    const result = await pool.query(
      `SELECT u.id, u.name, u.email, u.phone, u.care_home, u.created_at
       FROM sessions s
       JOIN users u ON u.id = s.user_id
       WHERE s.token_hash = $1 AND s.expires_at > $2`,
      [req.sessionHash, Date.now()]
    );

    if (result.rowCount === 0) {
      throw failure(401, "Your session expired. Sign in again.");
    }

    return res.json({ user: publicUser(result.rows[0]) });
  })
);

// PATCH /api/auth/me
// Update the signed-in user's account details.
router.patch(
  "/me",
  authenticate,
  asyncRoute(async (req, res) => {
    const name = clean(req.body.name ?? req.account.name, "full name", 100, true);
    const email = emailAddress(req.body.email ?? req.account.email);
    const phone = clean(
      req.body.phone ?? req.account.phone ?? "",
      "phone number",
      30
    );
    const careHome = clean(
      req.body.careHome ?? req.account.care_home ?? "",
      "care home name",
      200
    );

    let updated;

    try {
      updated = await pool.query(
        `UPDATE users
         SET name = $1,
             email = $2,
             phone = $3,
             care_home = $4,
             updated_at = NOW()
         WHERE id = $5
         RETURNING id, name, email, phone, care_home, created_at`,
        [name, email, phone, careHome, req.account.id]
      );
    } catch (error) {
      if (error.code === "23505") {
        throw failure(409, "An account already uses this email address.");
      }

      throw error;
    }

    if (updated.rowCount === 0) {
      throw failure(404, "Account not found.");
    }

    return res.json({ user: publicUser(updated.rows[0]) });
  })
);

// POST /api/auth/password
// Change the signed-in user's password and issue a fresh session.
router.post(
  "/password",
  authenticate,
  asyncRoute(async (req, res) => {
    const currentPassword = req.body.currentPassword;

    if (
      typeof currentPassword !== "string" ||
      currentPassword.length > 128
    ) {
      throw failure(422, "Enter your current password.");
    }

    const newPassword = passwordValue(req.body.newPassword);
    const client = await pool.connect();

    try {
      await client.query("BEGIN");

      const current = await client.query(
        "SELECT password_hash FROM users WHERE id = $1 FOR UPDATE",
        [req.account.id]
      );

      if (current.rowCount === 0) {
        throw failure(404, "Account not found.");
      }

      if (!(await checkPassword(currentPassword, current.rows[0].password_hash))) {
        throw failure(401, "Current password is incorrect.");
      }

      const passwordHash = await hashPassword(newPassword);

      const updated = await client.query(
        `UPDATE users
         SET password_hash = $1,
             updated_at = NOW()
         WHERE id = $2
         RETURNING id, name, email, phone, care_home, created_at`,
        [passwordHash, req.account.id]
      );

      // Revoke previous sessions and return a fresh session to the mobile app.
      await client.query(
        "DELETE FROM sessions WHERE user_id = $1",
        [req.account.id]
      );

      const response = await issueSession(client, updated.rows[0]);

      await client.query("COMMIT");

      return res.json(response);
    } catch (error) {
      try {
        await client.query("ROLLBACK");
      } catch {
        // Preserve the original error.
      }

      throw error;
    } finally {
      client.release();
    }
  })
);

// POST /api/auth/logout
router.post(
  "/logout",
  authenticate,
  asyncRoute(async (req, res) => {
    await pool.query(
      "DELETE FROM sessions WHERE token_hash = $1",
      [req.sessionHash]
    );

    return res.json({ message: "Signed out." });
  })
);

// Remove expired sessions periodically.
const cleanup = setInterval(() => {
  pool
    .query("DELETE FROM sessions WHERE expires_at <= $1", [Date.now()])
    .catch((error) => {
      console.error("Expired session cleanup failed:", error.message);
    });
}, 60 * 1000);

cleanup.unref();

// Convert account errors to JSON responses.
router.use((error, req, res, next) => {
  if (res.headersSent) return next(error);

  const status = error.status || 500;

  if (status >= 500) {
    console.error("Account request failed:", error.message);
  }

  return res.status(status).json({
    error:
      status >= 500
        ? "Account service failed. Try again."
        : error.message,
  });
});

router.authenticate = authenticate;

module.exports = router;
