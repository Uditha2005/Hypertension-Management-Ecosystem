const path = require("node:path");

require("dotenv").config({
  path: path.resolve(__dirname, "../.env"),
});

const { DatabaseSync } = require("node:sqlite");
const pool = require("../src/db");

async function migrate() {
  const dataDir = path.resolve(__dirname, "../data");

  let accountsDb;
  let profilesDb;
  let client;

  try {
    accountsDb = new DatabaseSync(
      path.join(dataDir, "hypercare_accounts.sqlite3")
    );

    profilesDb = new DatabaseSync(
      path.join(dataDir, "component1_resident_profiles_temp.sqlite3")
    );

    const users = accountsDb.prepare(`
      SELECT id, name, email, password_hash, phone, care_home,
             created_at, updated_at
      FROM users
    `).all();

    if (users.length !== 1) {
      throw new Error(
        `Expected exactly one local account; found ${users.length}.`
      );
    }

    const user = users[0];

    const sessions = accountsDb.prepare(`
      SELECT token_hash, user_id, expires_at
      FROM sessions
      WHERE user_id = ? AND expires_at > ?
    `).all(user.id, Date.now());

    const profile = profilesDb.prepare(`
      SELECT profile_json, updated_at
      FROM resident_profiles
      WHERE user_id = ?
    `).get(user.id);

    const emailKey = String(user.email).trim().toLowerCase();

    client = await pool.connect();
    await client.query("BEGIN");

    // Never overwrite a different shared account.
    const existing = await client.query(
      `SELECT id, email
       FROM public.users
       WHERE id = $1 OR LOWER(email) = $2
       FOR UPDATE`,
      [user.id, emailKey]
    );

    const byId = existing.rows.find(
      (row) => String(row.id) === String(user.id)
    );

    const byEmail = existing.rows.find(
      (row) => String(row.email).trim().toLowerCase() === emailKey
    );

    if (byEmail && String(byEmail.id) !== String(user.id)) {
      throw new Error(
        "A different Neon account uses this email. Manual review is required."
      );
    }

    if (
      byId &&
      String(byId.email).trim().toLowerCase() !== emailKey
    ) {
      throw new Error(
        "The local account ID belongs to a different Neon account."
      );
    }

    let accountImported = false;

    if (!byId) {
      await client.query(
        `INSERT INTO public.users (
           id, name, email, password_hash, phone, care_home,
           created_at, updated_at
         )
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
        [
          user.id,
          user.name,
          user.email,
          user.password_hash,
          user.phone || "",
          user.care_home || "",
          user.created_at,
          user.updated_at,
        ]
      );

      accountImported = true;
    }

    let sessionsImported = 0;

    for (const session of sessions) {
      const existingSession = await client.query(
        `SELECT user_id
         FROM public.sessions
         WHERE token_hash = $1`,
        [session.token_hash]
      );

      if (existingSession.rowCount) {
        if (
          String(existingSession.rows[0].user_id) !== String(user.id)
        ) {
          throw new Error(
            "An existing session hash belongs to a different account."
          );
        }

        continue;
      }

      await client.query(
        `INSERT INTO public.sessions (token_hash, user_id, expires_at)
         VALUES ($1, $2, $3)`,
        [session.token_hash, user.id, session.expires_at]
      );

      sessionsImported++;
    }

    await client.query(`
      CREATE TABLE IF NOT EXISTS public.component1_resident_profiles (
        user_id TEXT PRIMARY KEY
          REFERENCES public.users(id) ON DELETE RESTRICT,
        profile JSONB NOT NULL
          CHECK (jsonb_typeof(profile) = 'object'),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
      )
    `);

    let profileImported = false;

    if (profile) {
      const existingProfile = await client.query(
        `SELECT user_id
         FROM public.component1_resident_profiles
         WHERE user_id = $1`,
        [user.id]
      );

      if (!existingProfile.rowCount) {
        await client.query(
          `INSERT INTO public.component1_resident_profiles
             (user_id, profile, updated_at)
           VALUES ($1, $2::jsonb, $3)`,
          [user.id, profile.profile_json, profile.updated_at]
        );

        profileImported = true;
      }
    }

    // Confirm every historical assessment can be linked to a user.
    const orphaned = await client.query(`
      SELECT COUNT(*)::int AS total
      FROM public.component1_assessment_history h
      LEFT JOIN public.users u ON u.id = h.local_account_id
      WHERE u.id IS NULL
    `);

    if (Number(orphaned.rows[0].total) !== 0) {
      throw new Error(
        "Assessment history contains an account without a matching Neon user."
      );
    }

    const constraint = await client.query(
      `SELECT 1
       FROM pg_constraint
       WHERE conname = $1
         AND conrelid =
           'public.component1_assessment_history'::regclass`,
      ["component1_assessment_history_user_fkey"]
    );

    if (!constraint.rowCount) {
      await client.query(`
        ALTER TABLE public.component1_assessment_history
        ADD CONSTRAINT component1_assessment_history_user_fkey
        FOREIGN KEY (local_account_id)
        REFERENCES public.users(id)
      `);
    }

    await client.query("COMMIT");

    const counts = await client.query(`
      SELECT
        COUNT(*)::int AS total_records,
        COUNT(legacy_sqlite_id)::int AS migrated_records,
        COUNT(DISTINCT local_account_id)::int AS linked_accounts
      FROM public.component1_assessment_history
    `);

    console.log("=== MIGRATION COMPLETED ===");
    console.table([{
      accountImported,
      activeSessionsFound: sessions.length,
      sessionsImported,
      localProfileFound: Boolean(profile),
      profileImported,
    }]);

    console.log("=== ASSESSMENT HISTORY VERIFICATION ===");
    console.table(counts.rows);
  } catch (error) {
    if (client) {
      try {
        await client.query("ROLLBACK");
      } catch {
        // Preserve the original error.
      }
    }

    console.error("Migration failed:", error.message);
    process.exitCode = 1;
  } finally {
    if (accountsDb) accountsDb.close();
    if (profilesDb) profilesDb.close();

    if (client) client.release();

    await pool.end();
  }
}

migrate();