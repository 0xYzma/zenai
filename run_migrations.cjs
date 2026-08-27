const pg = require('pg');
const fs = require('fs');

const SAAS_DB = process.env.SAAS_DATABASE_URL || process.env.SAAS_DB || '';
const ZENAI_DB = process.env.ZENAI_DATABASE_URL || process.env.ZENAI_DB || '';

async function run() {
  // ZenAI postflight (migration already ran)
  const zenai = new pg.Client({ connectionString: ZENAI_DB });
  await zenai.connect();
  const ztRes = await zenai.query('SELECT table_name FROM information_schema.tables WHERE table_schema=$1 AND table_name LIKE $2 ORDER BY 1', ['public', 'integrated_%']);
  console.log('[ZenAI] Tables:', ztRes.rows.map(r => r.table_name).join(', '));
  await zenai.end();

  // SaaS migration
  const saas = new pg.Client({ connectionString: SAAS_DB });
  await saas.connect();
  console.log('[SaaS] Connected');

  await saas.query(fs.readFileSync('d:/PieceOfShit/Projects/AI/ZenAI/zenai/migrations/saas/001_ai_saas_tables_up.sql', 'utf8'));
  console.log('[SaaS 001] OK');

  await saas.query(fs.readFileSync('d:/PieceOfShit/Projects/AI/ZenAI/zenai/migrations/saas/002_ai_analytics_role.sql', 'utf8'));
  console.log('[SaaS 002] OK');

  const stRes = await saas.query('SELECT table_name FROM information_schema.tables WHERE table_schema=$1 AND table_name LIKE $2 ORDER BY 1', ['public', 'ai_%']);
  console.log('[SaaS] AI tables:', stRes.rows.map(r => r.table_name).join(', '));

  const colRes = await saas.query("SELECT column_name, column_default FROM information_schema.columns WHERE table_name='plans' AND column_name IN ('max_ai_requests_per_month','max_ai_concurrent_requests') ORDER BY 1");
  console.log('[SaaS] plans AI cols:', colRes.rows.map(c => c.column_name + '(default=' + c.column_default + ')').join(', ') || 'NONE');

  const roleRes = await saas.query("SELECT rolname FROM pg_catalog.pg_roles WHERE rolname='ai_analytics'");
  console.log('[SaaS] ai_analytics role:', roleRes.rows.length > 0 ? 'EXISTS' : 'MISSING');

  await saas.end();

  const allOk = ztRes.rows.length >= 3 && stRes.rows.length >= 4 && colRes.rows.length === 2;
  console.log(allOk ? '\nAll migrations verified OK.' : '\nSome checks FAILED.');
  if (!allOk) process.exit(1);
}

run().catch(e => { console.error('FATAL:', e.message); process.exit(1); });
