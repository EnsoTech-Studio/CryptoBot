-- Keep the local/demo admin aligned with docs/note-duc.txt.
-- The Go auth service upgrades this legacy SHA-256 hash to Argon2id on login.
WITH demo_admin AS (
    INSERT INTO users(email, password_hash, display_name, role, is_active)
    VALUES (
        'demo-admin@cryptobot.local',
        '6193a66b95d6d2f7fb26e0f59fe32028649fc4ebe61f3b283089be7287dade2d',
        'Demo Admin',
        'ADMIN',
        TRUE
    )
    ON CONFLICT (email) DO UPDATE SET
        password_hash = EXCLUDED.password_hash,
        display_name = EXCLUDED.display_name,
        role = EXCLUDED.role,
        is_active = TRUE,
        updated_at = now()
    RETURNING id
)
INSERT INTO user_quotas(user_id)
SELECT id FROM demo_admin
ON CONFLICT (user_id) DO NOTHING;
