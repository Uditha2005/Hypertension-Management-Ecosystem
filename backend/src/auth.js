const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { promisify } = require("node:util");
const { DatabaseSync } = require("node:sqlite");
const express = require("express");

const router = express.Router();
const scrypt = promisify(crypto.scrypt);

// Store account data separately from the Component 1 AI service.
const dataDirectory = path.resolve(__dirname, "../data");
fs.mkdirSync(dataDirectory, { recursive: true });

const db = new DatabaseSync(
  path.join(dataDirectory, "hypercare_accounts.sqlite3")
);

db.exec(`
  PRAGMA foreign_keys = ON;
  PRAGMA journal_mode = WAL;

  CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    care_home TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
  );

  CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL
  );

  CREATE INDEX IF NOT EXISTS sessions_user_id
    ON sessions(user_id);

  CREATE INDEX IF NOT EXISTS sessions_expires_at
    ON sessions(expires_at);
`);

const queries = {
  userByEmail: db.prepare(
    "SELECT * FROM users WHERE email = ?"
  ),
  userById: db.prepare(
    "SELECT * FROM users WHERE id = ?"
  ),
  insertUser: db.prepare(`
    INSERT INTO users (
      id, name, email, password_hash,
      phone, care_home, created_at, updated_at
    ) VALUES (?, ?, ?, ?, '', '', ?, ?)
  `),
  insertSession: db.prepare(`
    INSERT INTO sessions (token_hash, user_id, expires_at)
    VALUES (?, ?, ?)
  `),
  activeSession: db.prepare(`
    SELECT token_hash, user_id, expires_at
    FROM sessions
    WHERE token_hash = ? AND expires_at > ?
  `),
  deleteSession: db.prepare(
    "DELETE FROM sessions WHERE token_hash = ?"
  ),
  deleteExpiredSessions: db.prepare(
    "DELETE FROM sessions WHERE expires_at <= ?"
  ),
};

function failure(status, message) {
  const error = new Error(message);
  error.status = status;
  return error;
}

function transaction(operation) {
  db.exec("BEGIN IMMEDIATE");

  try {
    const result = operation();
    db.exec("COMMIT");
    return result;
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
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
  const email = clean(value, "email address", 254, true)
    .toLowerCase();

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
    throw failure(
      422,
      "Use a password between 10 and 128 characters."
    );
  }

  return value;
}

const SCRYPT_OPTIONS = {
  N: 32768,
  r: 8,
  p: 3,
  maxmem: 64 * 1024 * 1024,
};

async function hashPassword(password) {
  const salt = crypto.randomBytes(16).toString("hex");
  const key = await scrypt(
    password,
    salt,
    64,
    SCRYPT_OPTIONS
  );

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
  const actual = await scrypt(
    password,
    parts[0],
    64,
    SCRYPT_OPTIONS
  );

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

function issueSession(user) {
  const token = crypto.randomBytes(32).toString("hex");
  const expiresAt = Date.now() + 7 * 24 * 60 * 60 * 1000;

  queries.insertSession.run(
    digestToken(token),
    user.id,
    expiresAt
  );

  return {
    token,
    expiresAt: new Date(expiresAt).toISOString(),
    user: publicUser(user),
  };
}

// Simple in-process rate limit for account requests.
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
    res.set(
      "Retry-After",
      String(Math.ceil((record.until - now) / 1000))
    );

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
    (
      !req.body ||
      typeof req.body !== "object" ||
      Array.isArray(req.body)
    )
  ) {
    return res.status(400).json({
      error: "Send a valid JSON object.",
    });
  }

  next();
});

// POST /api/auth/register
router.post(
  "/register",
  authLimit,
  asyncRoute(async (req, res) => {
    const name = clean(req.body.name, "full name", 100, true);
    const email = emailAddress(req.body.email);
    const password = passwordValue(req.body.password);

    if (queries.userByEmail.get(email)) {
      throw failure(
        409,
        "An account already uses this email address."
      );
    }

    const hashed = await hashPassword(password);
    const id = crypto.randomUUID();
    const timestamp = new Date().toISOString();

    const response = transaction(() => {
      // Check again immediately before inserting.
      if (queries.userByEmail.get(email)) {
        throw failure(
          409,
          "An account already uses this email address."
        );
      }

      queries.insertUser.run(
        id,
        name,
        email,
        hashed,
        timestamp,
        timestamp
      );

      const user = queries.userById.get(id);
      return issueSession(user);
    });

    res.status(201).json(response);
  })
);

// POST /api/auth/login
router.post(
  "/login",
  authLimit,
  asyncRoute(async (req, res) => {
    const email = emailAddress(req.body.email);
    const password = req.body.password;
    const user = queries.userByEmail.get(email);

    if (
      !user ||
      !(await checkPassword(password, user.password_hash))
    ) {
      throw failure(401, "Email or password is incorrect.");
    }

    const response = transaction(() => {
      const latestUser = queries.userById.get(user.id);

      if (
        !latestUser ||
        latestUser.password_hash !== user.password_hash
      ) {
        throw failure(
          401,
          "Account credentials changed. Sign in again."
        );
      }

      return issueSession(latestUser);
    });

    res.json(response);
  })
);

function authenticate(req, res, next) {
  try {
    const match = /^Bearer ([a-f0-9]{64})$/i.exec(
      req.headers.authorization || ""
    );

    if (!match) {
      throw failure(401, "Sign in to continue.");
    }

    const sessionHash = digestToken(match[1]);
    const session = queries.activeSession.get(
      sessionHash,
      Date.now()
    );

    if (!session) {
      throw failure(401, "Your session expired. Sign in again.");
    }

    const user = queries.userById.get(session.user_id);

    if (!user) {
      throw failure(401, "Account not found. Sign in again.");
    }

    req.account = user;
    req.sessionHash = sessionHash;
    next();
  } catch (error) {
    next(error);
  }
}

// GET /api/auth/me
router.get("/me", authenticate, (req, res) => {
  res.json({ user: publicUser(req.account) });
});

// POST /api/auth/logout
router.post("/logout", authenticate, (req, res) => {
  queries.deleteSession.run(req.sessionHash);
  res.json({ message: "Signed out." });
});

// Remove expired sessions periodically.
const cleanup = setInterval(() => {
  queries.deleteExpiredSessions.run(Date.now());
}, 60 * 1000);

cleanup.unref();

// Convert account errors to JSON responses.
router.use((error, req, res, next) => {
  const status = error.status || 500;

  if (status >= 500) {
    console.error("Account request failed:", error.message);
  }

  res.status(status).json({
    error:
      status >= 500
        ? "Account service failed. Try again."
        : error.message,
  });
});

module.exports = router;