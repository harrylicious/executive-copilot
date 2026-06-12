-- =============================================================================
-- Demo Users for Executive Copilot
-- =============================================================================
--
-- IMPORTANT: bcrypt hashes are unique per generation. Use the Python script
-- to seed users with freshly generated hashes:
--
--   cd backend
--   python -m scripts.seed_demo_users
--
-- Or generate a fresh SQL dump:
--   python -m scripts.seed_demo_users --sql
--
-- =============================================================================
-- Demo Accounts:
--
--   | Email                          | Password    | Role      | Department     |
--   |--------------------------------|-------------|-----------|----------------|
--   | admin@jembatanbaru.co.id       | admin123    | admin     | Accounting Tax |
--   | director@jembatanbaru.co.id    | exec123     | executive | Board          |
--   | demand@jembatanbaru.co.id      | demand123   | staff     | Demand Supply  |
--   | finance@jembatanbaru.co.id     | finance123  | staff     | Finance        |
--
-- =============================================================================

-- The hashes below were generated at build time. If they don't work,
-- regenerate using: python -m scripts.seed_demo_users

INSERT OR IGNORE INTO users (name, email, role, department, status, password_hash, avatar, created_at, updated_at)
VALUES
  ('Ahmad Rizki', 'admin@jembatanbaru.co.id', 'admin', 'Accounting Tax', 'active',
   '$2b$12$iQbAGMuVIHpYE6itpzUvTeeDRlxlPtOJ6tu6fjb.j3j7160bHkzIW', 'AR',
   datetime('now'), datetime('now')),

  ('Siti Rahayu', 'director@jembatanbaru.co.id', 'executive', 'Board', 'active',
   '$2b$12$TWpR6n3.EDIdx/k/zWiRl.HMiZDYEYTlPjD4Nip8Q0KvoTaetfZj2', 'SR',
   datetime('now'), datetime('now')),

  ('Budi Santoso', 'demand@jembatanbaru.co.id', 'staff', 'Demand Supply', 'active',
   '$2b$12$Ba2G5fj7dAOUQerNKscPbOQLlysjX7cDL6QTpl9yDMwN5ZLTFEph.', 'BS',
   datetime('now'), datetime('now')),

  ('Dewi Kusuma', 'finance@jembatanbaru.co.id', 'staff', 'Finance', 'active',
   '$2b$12$P9dlOvBPBPVH5cGp3cW59.jLhUsrPVSP8VESdlRz423NuJQYm6xEi', 'DK',
   datetime('now'), datetime('now'));
