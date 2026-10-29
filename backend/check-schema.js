
require("dotenv").config();

const pool = require("./src/db");

async function main() {
  try {
    const tables = await pool.query(`
      SELECT table_name
      FROM information_schema.tables
      WHERE table_schema = 'public'
      ORDER BY table_name
    `);

    console.log("\nDATABASE TABLES:");
    console.table(tables.rows);

    const columns = await pool.query(`
      SELECT column_name, data_type
      FROM information_schema.columns
      WHERE table_schema = 'public'
        AND table_name = 'fall_events'
      ORDER BY ordinal_position
    `);

    console.log("\nFALL_EVENTS COLUMNS:");
    console.table(columns.rows);

    const residents = await pool.query(`
      SELECT resident_id, resident_name
      FROM fall_events
      GROUP BY resident_id, resident_name
      ORDER BY resident_id
      LIMIT 20
    `);

    console.log("\nEXISTING FACE/RESIDENT IDs:");
    console.table(residents.rows);
  } catch (error) {
    console.error("DATABASE CHECK FAILED:", error.message);
  } finally {
    await pool.end();
  }
}

main();
