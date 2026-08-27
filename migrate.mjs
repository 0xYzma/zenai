/**
 * migrate.mjs — Run ZenAI AI migrations against both Neon DBs.
 *
 * Usage: node migrate.mjs
 *
 * Runs:
 *   1. ZenAI DB: migrations/zenai/001_ai_tables_up.sql
 *   2. SaaS DB:  migrations/saas/001_ai_saas_tables_up.sql
 *   3. SaaS DB:  migrations/saas/002_ai_analytics_role.sql (role only, grants skipped)
 *   4. Postflight verification on both DBs
 */

import pg from 'pg';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const { Client } = pg;
const __dirname = path.dirname(fileURLToPath(import.meta.url));

const SAAS_DB = process.env.SAAS_DATABASE_URL || process.env.SAAS_DB || '';
const ZENAI_DB = process.env.ZENAI_DATABASE_URL || process.env.ZENAI_DB || '';

const MIGRATIONS_BASE = path.join(path.dirname(fileURLToPath(import.meta.url)), 'migrations');

async function runSQL(client, label, sql) {
  console.log(`\n[${label}] Running...`);
  try {
    await client.query(sql);
    console.log(`[${label}] ✅ OK`);
  } catch (err) {
    console.error(`[${label}] ❌ FAILED: ${err.message}`);
    throw err;
  }
}

async function migrateZenAI() {
  const client = new Client({ connectionString: ZENAI_DB });
  await client.connect();
  console.log('\n══════════════════════════════════════════');
  console.log(' ZenAI DB migrations');
  console.log('══════════════════════════════════════════');

  const sql = fs.readFileSync(path.join(MIGRATIONS_BASE, 'zenai/001_ai_tables_up.sql'), 'utf8');
  await runSQL(client, '001_ai_tables_up', sql);

  // Postflight
  const { rows } = await client.query(`
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name LIKE 'integrated_%'
    ORDER BY table_name
  `);
  console.log('\n[Postflight] ZenAI tables:');
  if (rows.length === 0) {
    console.error('  ❌ No integrated_* tables found!');
  } else {
    rows.forEach(r => console.log(`  ✅ ${r.table_name}`));
  }

  await client.end();
  return rows.map(r => r.table_name);
}

async function migrateSaaS() {
  const client = new Client({ connectionString: SAAS_DB });
  await client.connect();
  console.log('\n══════════════════════════════════════════');
  console.log(' SaaS DB migrations');
  console.log('══════════════════════════════════════════');

  const sql001 = fs.readFileSync(path.join(MIGRATIONS_BASE, 'saas/001_ai_saas_tables_up.sql'), 'utf8');
  await runSQL(client, '001_ai_saas_tables_up', sql001);

  const sql002 = fs.readFileSync(path.join(MIGRATIONS_BASE, 'saas/002_ai_analytics_role.sql'), 'utf8');
  await runSQL(client, '002_ai_analytics_role', sql002);

  // Postflight: tables
  const { rows: tables } = await client.query(`
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name LIKE 'ai_%'
    ORDER BY table_name
  `);
  console.log('\n[Postflight] SaaS AI tables:');
  if (tables.length === 0) {
    console.error('  ❌ No ai_* tables found!');
  } else {
    tables.forEach(r => console.log(`  ✅ ${r.table_name}`));
  }

  // Postflight: plans columns
  const { rows: cols } = await client.query(`
    SELECT column_name, column_default
    FROM information_schema.columns
    WHERE table_name = 'plans'
      AND column_name IN ('max_ai_requests_per_month', 'max_ai_concurrent_requests')
    ORDER BY column_name
  `);
  console.log('\n[Postflight] plans AI columns:');
  if (cols.length === 0) {
    console.error('  ❌ AI columns not added to plans!');
  } else {
    cols.forEach(r => console.log(`  ✅ ${r.column_name} (default: ${r.column_default})`));
  }

  // Postflight: role
  const { rows: roles } = await client.query(`
    SELECT rolname FROM pg_catalog.pg_roles WHERE rolname = 'ai_analytics'
  `);
  console.log('\n[Postflight] ai_analytics role:');
  if (roles.length === 0) {
    console.error('  ❌ ai_analytics role not found!');
  } else {
    console.log(`  ✅ ai_analytics role exists`);
  }

  await client.end();
  return { tables: tables.map(r => r.table_name), cols, roles };
}

async function main() {
  let exitCode = 0;
  try {
    const zenaiTables = await migrateZenAI();
    const { tables: saasTables, cols, roles } = await migrateSaaS();

    console.log('\n══════════════════════════════════════════');
    console.log(' Summary');
    console.log('══════════════════════════════════════════');
    console.log(`ZenAI tables:  ${zenaiTables.join(', ') || 'NONE'}`);
    console.log(`SaaS AI tables: ${saasTables.join(', ') || 'NONE'}`);
    console.log(`Plans columns:  ${cols.map(c => c.column_name).join(', ') || 'NONE'}`);
    console.log(`ai_analytics role: ${roles.length > 0 ? 'EXISTS' : 'MISSING'}`);

    const allOk = zenaiTables.length >= 3 && saasTables.length >= 4 && cols.length === 2;
    if (allOk) {
      console.log('\n✅ All migrations applied and verified successfully.');
    } else {
      console.error('\n❌ Some checks failed — review output above.');
      exitCode = 1;
    }
  } catch (err) {
    console.error('\n❌ Fatal error:', err.message);
    exitCode = 1;
  }
  process.exit(exitCode);
}

main();
