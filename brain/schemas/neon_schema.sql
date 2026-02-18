-- Mike's Brain - Neon Database Schema v0.1.0
-- Serverless Postgres with pgvector for embeddings

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================
-- CORE TABLES
-- ============================================

-- Knowledge entities (the atoms of the brain)
CREATE TABLE IF NOT EXISTS entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type VARCHAR(50) NOT NULL, -- 'insight', 'decision', 'question', 'answer', 'code', 'task', 'person', 'project'
    content TEXT NOT NULL,
    summary TEXT,
    embedding vector(1536), -- OpenAI ada-002 dimension
    source VARCHAR(100) NOT NULL, -- 'telegram', 'github', 'synthetic_kb', 'user_data'
    source_id VARCHAR(255), -- Original ID from source
    source_url TEXT,
    quality_score FLOAT DEFAULT 0.0, -- 0-10, set by Hammurabi
    actionable BOOLEAN DEFAULT FALSE,
    archived BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    indexed_at TIMESTAMPTZ
);

-- Relationships between entities
CREATE TABLE IF NOT EXISTS relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_entity_id UUID REFERENCES entities(id) ON DELETE CASCADE,
    to_entity_id UUID REFERENCES entities(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL, -- 'related_to', 'caused_by', 'leads_to', 'contradicts', 'supports', 'part_of'
    strength FLOAT DEFAULT 0.5, -- 0-1
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(from_entity_id, to_entity_id, type)
);

-- ============================================
-- SOURCE TRACKING
-- ============================================

-- Telegram conversations
CREATE TABLE IF NOT EXISTS telegram_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL,
    sender_id BIGINT,
    sender_name VARCHAR(255),
    content TEXT NOT NULL,
    is_voice BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMPTZ NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    entity_id UUID REFERENCES entities(id),
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(chat_id, message_id)
);

-- GitHub activity
CREATE TABLE IF NOT EXISTS github_activity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo VARCHAR(255) NOT NULL,
    activity_type VARCHAR(50) NOT NULL, -- 'commit', 'issue', 'pr', 'comment', 'release'
    activity_id VARCHAR(255) NOT NULL,
    title TEXT,
    content TEXT,
    author VARCHAR(255),
    timestamp TIMESTAMPTZ NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    entity_id UUID REFERENCES entities(id),
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(repo, activity_type, activity_id)
);

-- Synthetic KB entries
CREATE TABLE IF NOT EXISTS synthetic_kb (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category VARCHAR(100),
    persona VARCHAR(100),
    quality_score FLOAT DEFAULT 0.0,
    processed BOOLEAN DEFAULT FALSE,
    entity_id UUID REFERENCES entities(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- QA & JUDGING
-- ============================================

-- Judge evaluations (Hammurabi's verdicts)
CREATE TABLE IF NOT EXISTS evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID REFERENCES entities(id) ON DELETE CASCADE,
    judge VARCHAR(50) NOT NULL, -- 'hammurabi_quality', 'hammurabi_novelty', 'hammurabi_action'
    score FLOAT NOT NULL, -- 0-10
    reasoning TEXT,
    passed BOOLEAN NOT NULL,
    threshold FLOAT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Feedback loops
CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID REFERENCES entities(id),
    evaluation_id UUID REFERENCES evaluations(id),
    feedback_type VARCHAR(50) NOT NULL, -- 'rejection', 'improvement', 'user_correction'
    original_content TEXT,
    suggested_content TEXT,
    applied BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- ACTIONS & EXECUTION
-- ============================================

-- Actions taken by Tesla
CREATE TABLE IF NOT EXISTS actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger_entity_id UUID REFERENCES entities(id),
    action_type VARCHAR(50) NOT NULL, -- 'email', 'code_execute', 'web_search', 'notification', 'task_create'
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'executing', 'completed', 'failed'
    input JSONB,
    output JSONB,
    error TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- DIGITAL TWINS & VERSIONING
-- ============================================

-- Brain snapshots for digital twins
CREATE TABLE IF NOT EXISTS brain_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    description TEXT,
    entity_count INTEGER,
    relationship_count INTEGER,
    snapshot_data JSONB, -- Metadata about the snapshot
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(version)
);

-- ============================================
-- INDEXES
-- ============================================

-- Vector similarity search
CREATE INDEX IF NOT EXISTS idx_entities_embedding ON entities 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Full text search
CREATE INDEX IF NOT EXISTS idx_entities_content_trgm ON entities 
    USING gin (content gin_trgm_ops);

-- Common queries
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_source ON entities(source);
CREATE INDEX IF NOT EXISTS idx_entities_quality ON entities(quality_score);
CREATE INDEX IF NOT EXISTS idx_entities_actionable ON entities(actionable) WHERE actionable = TRUE;
CREATE INDEX IF NOT EXISTS idx_relationships_from ON relationships(from_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationships_to ON relationships(to_entity_id);
CREATE INDEX IF NOT EXISTS idx_telegram_processed ON telegram_messages(processed) WHERE processed = FALSE;
CREATE INDEX IF NOT EXISTS idx_github_processed ON github_activity(processed) WHERE processed = FALSE;

-- ============================================
-- FUNCTIONS
-- ============================================

-- Semantic search function
CREATE OR REPLACE FUNCTION search_brain(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    type VARCHAR(50),
    content TEXT,
    summary TEXT,
    similarity FLOAT,
    quality_score FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.id,
        e.type,
        e.content,
        e.summary,
        1 - (e.embedding <=> query_embedding) AS similarity,
        e.quality_score
    FROM entities e
    WHERE 1 - (e.embedding <=> query_embedding) > match_threshold
        AND e.archived = FALSE
    ORDER BY e.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER entities_updated_at
    BEFORE UPDATE ON entities
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
