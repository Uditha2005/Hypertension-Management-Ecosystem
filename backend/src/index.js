const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { promisify } = require("node:util");
const { DatabaseSync } = require("node:sqlite");

const express = require("express");
const cors = require("cors");

require("dotenv").config({
  path: path.resolve(__dirname, "../.env"),
});

const app = express();
const scrypt = promisify(crypto.scrypt);

app.disable("x-powered-by");
app.use(cors());
app.use(express.json({ limit: "32kb" }));

// Account records are separate from the medicine comparison database.
const dataDirectory = path.resolve(__dirname, "../data");
fs.mkdirSync(dataDirectory, { recursive: true });

const databasePath = path.join(dataDirectory, "hypercare_accounts.sqlite3");

const db = new DatabaseSync(databasePath, {
  timeout: 5000,
});

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
    )
    VALUES (?, ?, ?, ?, '', '', ?, ?)
  `),

  updateProfile: db.prepare(`
    UPDATE users
    SET name = ?, phone = ?, care_home = ?, updated_at = ?
    WHERE id = ?
  `),

  updatePassword: db.prepare(`
    UPDATE users
    SET password_hash = ?, updated_at = ?
    WHERE id = ? AND password_hash = ?
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

  deleteUserSessions: db.prepare(
    "DELETE FROM sessions WHERE user_id = ?"
  ),

  deleteExpiredSessions: db.prepare(
    "DELETE FROM sessions WHERE expires_at <= ?"
  ),
};

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

function failure(status, message) {
  const error = new Error(message);
  error.status = status;
  return error;
}

function clean(value, field, maximum, required = false) {
  if (typeof value !== "string" || value.length > maximum) {
    throw failure(422, `Invalid ${field}.`);
  }

  const text = value.trim();

  if (required && !text) {
    throw failure(422, `Enter ${field}.`);
  }

  return text;
}

function emailAddress(value) {
  const email = clean(
    value,
    "email address",
    254,
    true
  ).toLowerCase();

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

  // Preserve the password exactly as entered.
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
  if (
    typeof password !== "string" ||
    password.length > 128
  ) {
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
  return crypto
    .createHash("sha256")
    .update(token)
    .digest("hex");
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

function requireCurrentSession(req) {
  const session = queries.activeSession.get(
    req.sessionHash,
    Date.now()
  );

  if (!session) {
    throw failure(
      401,
      "Your session expired. Sign in again."
    );
  }

  return session;
}

function authenticate(req, res, next) {
  try {
    const match = /^Bearer ([a-f0-9]{64})$/i.exec(
      req.headers.authorization || ""
    );

    if (!match) {
      throw failure(401, "Sign in to continue.");
    }

    req.sessionHash = digestToken(match[1]);

    const session = requireCurrentSession(req);
    const user = queries.userById.get(session.user_id);

    if (!user) {
      throw failure(
        401,
        "Account not found. Sign in again."
      );
    }

    req.account = user;
    next();
  } catch (error) {
    next(error);
  }
}

const asyncRoute = (handler) => (req, res, next) =>
  Promise.resolve(handler(req, res, next)).catch(next);

// Basic rate limiting for this single-process research backend.
const attempts = new Map();

function authLimit(req, res, next) {
  const now = Date.now();
  const key = req.ip;

  let record = attempts.get(key);

  if (!record || now >= record.until) {
    record = {
      count: 0,
      until: now + 15 * 60 * 1000,
    };
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

const cleanup = setInterval(() => {
  const now = Date.now();

  for (const [key, record] of attempts) {
    if (now >= record.until) attempts.delete(key);
  }

  queries.deleteExpiredSessions.run(now);
}, 60000);

cleanup.unref();
queries.deleteExpiredSessions.run(Date.now());

app.get("/", (req, res) => {
  res.json({
    message: "Hypertension Management Ecosystem backend running",
    accountService: true,
    database: "sqlite",
    databaseReady: true,
  });
});

app.use("/api/auth", (req, res, next) => {
  res.set("Cache-Control", "no-store");

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

app.post(
  "/api/auth/register",
  authLimit,
  asyncRoute(async (req, res) => {
    const name = clean(
      req.body.name,
      "full name",
      100,
      true
    );

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
      // Check again after the asynchronous password hashing.
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

      return issueSession(queries.userById.get(id));
    });

    res.status(201).json(response);
  })
);

app.post(
  "/api/auth/login",
  authLimit,
  asyncRoute(async (req, res) => {
    const email = emailAddress(req.body.email);
    const password = req.body.password;

    if (
      typeof password !== "string" ||
      password.length > 128
    ) {
      throw failure(
        401,
        "Email or password is incorrect."
      );
    }

    const user = queries.userByEmail.get(email);

    if (
      !user ||
      !(await checkPassword(password, user.password_hash))
    ) {
      throw failure(
        401,
        "Email or password is incorrect."
      );
    }

    const response = transaction(() => {
      const latest = queries.userById.get(user.id);

      if (
        !latest ||
        latest.password_hash !== user.password_hash
      ) {
        throw failure(
          401,
          "Account credentials changed. Sign in again."
        );
      }

      return issueSession(latest);
    });

    res.json(response);
  })
);

app.get(
  "/api/auth/me",
  authenticate,
  (req, res) => {
    res.json({
      user: publicUser(req.account),
    });
  }
);

app.patch(
  "/api/auth/me",
  authenticate,
  asyncRoute(async (req, res) => {
    const name = clean(
      req.body.name,
      "full name",
      100,
      true
    );

    const phone = clean(
      req.body.phone ?? "",
      "phone number",
      30
    );

    const careHome = clean(
      req.body.careHome ?? "",
      "care-home name",
      150
    );

    queries.updateProfile.run(
      name,
      phone,
      careHome,
      new Date().toISOString(),
      req.account.id
    );

    res.json({
      user: publicUser(
        queries.userById.get(req.account.id)
      ),
    });
  })
);

app.post(
  "/api/auth/password",
  authLimit,
  authenticate,
  asyncRoute(async (req, res) => {
    const currentPassword = req.body.currentPassword;
    const newPassword = passwordValue(
      req.body.newPassword
    );

    const user = queries.userById.get(req.account.id);

    if (
      !(await checkPassword(
        currentPassword,
        user.password_hash
      ))
    ) {
      throw failure(
        401,
        "The current password is incorrect."
      );
    }

    if (newPassword === currentPassword) {
      throw failure(
        422,
        "Choose a different new password."
      );
    }

    const hashed = await hashPassword(newPassword);

    const response = transaction(() => {
      requireCurrentSession(req);

      const changed = queries.updatePassword.run(
        hashed,
        new Date().toISOString(),
        user.id,
        user.password_hash
      );

      if (changed.changes !== 1) {
        throw failure(
          409,
          "The account changed. Sign in again."
        );
      }

      // Revoke all old sessions and issue a replacement.
      queries.deleteUserSessions.run(user.id);

      return issueSession(
        queries.userById.get(user.id)
      );
    });

    res.json(response);
  })
);

app.post(
  "/api/auth/logout",
  authenticate,
  (req, res) => {
    queries.deleteSession.run(req.sessionHash);

    res.json({
      message: "Signed out.",
    });
  }
);

app.use((error, req, res, next) => {
  if (error.type === "entity.parse.failed") {
    return res.status(400).json({
      error: "Invalid JSON request.",
    });
  }

  if (error.type === "entity.too.large") {
    return res.status(413).json({
      error: "Request is too large.",
    });
  }

  const status = error.status || 500;

  if (status >= 500) {
    console.error(
      "Account request failed:",
      error.name || "Error"
    );
  }

  res.status(status).json({
    error:
      status >= 500
        ? "Account service failed. Try again."
        : error.message,
  });
});

const port = Number(process.env.PORT || 5000);

const server = app.listen(port, "0.0.0.0", () => {
  console.log("SQLite account database ready.");
  console.log(`Account backend running on port ${port}`);
  console.log(`Database file: ${databasePath}`);
});

server.on("error", (error) => {
  console.error(
    error.code === "EADDRINUSE"
      ? `Port ${port} is already in use. Stop the old backend terminal first.`
      : "Account backend could not start."
  );

  clearInterval(cleanup);
  db.close();
  process.exitCode = 1;
});

function shutdown() {
  clearInterval(cleanup);

  server.close(() => {
    db.close();
    process.exit(0);
  });
}

process.once("SIGINT", shutdown);
process.once("SIGTERM", shutdown);