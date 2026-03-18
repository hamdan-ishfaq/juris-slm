-- ============================================================================
-- Schema Verification Script for Phase 2 Database Models
-- ============================================================================

-- 1. List all tables in public schema
\echo '==================== ALL TABLES ===================='
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public'
ORDER BY table_name;

-- 2. Check foreign key constraints and CASCADE rules
\echo '\n==================== FOREIGN KEY CONSTRAINTS ===================='
SELECT
    tc.table_name AS "Table", 
    kcu.column_name AS "Column",
    ccu.table_name AS "References Table",
    ccu.column_name AS "References Column",
    rc.delete_rule AS "On Delete"
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
JOIN information_schema.referential_constraints AS rc
    ON tc.constraint_name = rc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name, kcu.column_name;

-- 3. Check column details for new tables
\echo '\n==================== DOCUMENTS TABLE SCHEMA ===================='
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'documents'
ORDER BY ordinal_position;

\echo '\n==================== PARENT_CHUNKS TABLE SCHEMA ===================='
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'parent_chunks'
ORDER BY ordinal_position;

\echo '\n==================== QUERY_TRACES TABLE SCHEMA ===================='
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'query_traces'
ORDER BY ordinal_position;

-- 4. Check indexes
\echo '\n==================== INDEXES ===================='
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- 5. Test relationships with sample query
\echo '\n==================== RELATIONSHIP TEST ===================='
SELECT 
    u.email AS "User Email",
    u.role AS "Role",
    COUNT(DISTINCT d.id) AS "Documents",
    COUNT(DISTINCT pc.id) AS "Parent Chunks",
    COUNT(DISTINCT qt.id) AS "Query Traces"
FROM users u
LEFT JOIN documents d ON u.id = d.owner_id
LEFT JOIN parent_chunks pc ON d.id = pc.doc_id
LEFT JOIN query_traces qt ON u.id = qt.user_id
GROUP BY u.id, u.email, u.role
ORDER BY u.email;

-- 6. Access level enum check
\echo '\n==================== ACCESS LEVELS ENUM ===================='
SELECT 
    e.enumlabel AS "Access Level"
FROM pg_enum e
JOIN pg_type t ON e.enumtypid = t.oid
WHERE t.typname = 'accesslevel'
ORDER BY e.enumsortorder;
