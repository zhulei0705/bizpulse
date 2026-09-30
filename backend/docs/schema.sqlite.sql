CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

CREATE TABLE audit_logs (
	id VARCHAR(32) NOT NULL, 
	action VARCHAR(100) NOT NULL, 
	entity_type VARCHAR(80), 
	entity_id VARCHAR(64), 
	actor VARCHAR(100) NOT NULL, 
	payload_json JSON NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE collection_jobs (
	id VARCHAR(32) NOT NULL, 
	source_id VARCHAR(32), 
	name VARCHAR(300) NOT NULL, 
	"query" TEXT, 
	keywords_json JSON NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	progress INTEGER NOT NULL, 
	started_at DATETIME, 
	finished_at DATETIME, 
	record_count INTEGER NOT NULL, 
	error_count INTEGER NOT NULL, 
	error_message TEXT, 
	duration_seconds FLOAT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(source_id) REFERENCES sources (id) ON DELETE SET NULL
);

CREATE TABLE companies (
	id VARCHAR(32) NOT NULL, 
	company_name VARCHAR(300) NOT NULL, 
	normalized_name VARCHAR(300) NOT NULL, 
	website TEXT, 
	domain VARCHAR(255), 
	industry VARCHAR(150), 
	sub_industry VARCHAR(150), 
	country VARCHAR(100), 
	province VARCHAR(100), 
	city VARCHAR(100), 
	employee_range VARCHAR(100), 
	business_model VARCHAR(100), 
	main_products JSON NOT NULL, 
	main_markets JSON NOT NULL, 
	company_description TEXT, 
	pulse_score FLOAT, 
	opportunity_level VARCHAR(10), 
	status VARCHAR(30) NOT NULL, 
	source_count INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE company_aliases (
	id VARCHAR(32) NOT NULL, 
	company_id VARCHAR(32) NOT NULL, 
	alias VARCHAR(300) NOT NULL, 
	normalized_alias VARCHAR(300) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	CONSTRAINT uq_company_alias UNIQUE (company_id, normalized_alias)
);

CREATE TABLE company_contacts (
	id VARCHAR(32) NOT NULL, 
	company_id VARCHAR(32) NOT NULL, 
	name VARCHAR(200), 
	title VARCHAR(200), 
	department VARCHAR(200), 
	public_contact TEXT, 
	source_record_id VARCHAR(32), 
	confidence INTEGER NOT NULL, 
	verified_public BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(source_record_id) REFERENCES source_records (id) ON DELETE SET NULL
);

CREATE TABLE company_markets (
	company_id VARCHAR(32) NOT NULL, 
	market_id VARCHAR(32) NOT NULL, 
	PRIMARY KEY (company_id, market_id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(market_id) REFERENCES markets (id) ON DELETE CASCADE
);

CREATE TABLE experiment_opportunities (
	id VARCHAR(32) NOT NULL, 
	experiment_id VARCHAR(32) NOT NULL, 
	opportunity_id VARCHAR(32) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(experiment_id) REFERENCES experiments (id) ON DELETE CASCADE, 
	FOREIGN KEY(opportunity_id) REFERENCES opportunities (id) ON DELETE CASCADE, 
	CONSTRAINT uq_experiment_opportunity UNIQUE (experiment_id, opportunity_id)
);

CREATE TABLE experiments (
	id VARCHAR(32) NOT NULL, 
	name VARCHAR(300) NOT NULL, 
	description TEXT, 
	market_id VARCHAR(32), 
	hypothesis TEXT NOT NULL, 
	target_customer TEXT, 
	offer_name VARCHAR(300), 
	pricing_hypothesis VARCHAR(300), 
	target_company_count INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	conclusion VARCHAR(30), 
	started_at DATETIME, 
	ended_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(market_id) REFERENCES markets (id) ON DELETE SET NULL
);

CREATE TABLE interactions (
	id VARCHAR(32) NOT NULL, 
	company_id VARCHAR(32) NOT NULL, 
	opportunity_id VARCHAR(32), 
	experiment_id VARCHAR(32), 
	channel VARCHAR(50) NOT NULL, 
	contact_at DATETIME, 
	contact_name VARCHAR(200), 
	contact_title VARCHAR(200), 
	response_summary TEXT, 
	response_type VARCHAR(50), 
	meeting BOOLEAN NOT NULL, 
	quote_amount NUMERIC(14, 2), 
	deal BOOLEAN NOT NULL, 
	revenue NUMERIC(14, 2), 
	reject_reason VARCHAR(80), 
	notes TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(experiment_id) REFERENCES experiments (id) ON DELETE SET NULL, 
	FOREIGN KEY(opportunity_id) REFERENCES opportunities (id) ON DELETE SET NULL
);

CREATE TABLE llm_runs (
	id VARCHAR(32) NOT NULL, 
	module VARCHAR(100) NOT NULL, 
	target_type VARCHAR(50), 
	target_id VARCHAR(64), 
	prompt_name VARCHAR(100), 
	prompt_version VARCHAR(50), 
	model VARCHAR(100), 
	provider VARCHAR(100), 
	input_hash VARCHAR(64), 
	output_json JSON NOT NULL, 
	tokens_input INTEGER, 
	tokens_output INTEGER, 
	cost_amount NUMERIC(12, 4), 
	duration_seconds FLOAT, 
	status VARCHAR(30) NOT NULL, 
	error_message TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE markets (
	id VARCHAR(32) NOT NULL, 
	market_name VARCHAR(250) NOT NULL, 
	slug VARCHAR(250) NOT NULL, 
	target_customer TEXT, 
	problem TEXT, 
	current_solution TEXT, 
	current_cost VARCHAR(200), 
	frequency VARCHAR(100), 
	willingness_to_pay INTEGER, 
	automation_fit INTEGER, 
	competition INTEGER, 
	entry_difficulty INTEGER, 
	market_score FLOAT, 
	validation_status VARCHAR(30) NOT NULL, 
	company_count INTEGER NOT NULL, 
	signal_count INTEGER NOT NULL, 
	high_value_company_count INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE opportunities (
	id VARCHAR(32) NOT NULL, 
	company_id VARCHAR(32) NOT NULL, 
	market_id VARCHAR(32), 
	primary_signal_id VARCHAR(32), 
	pain_point_id VARCHAR(32), 
	title VARCHAR(500) NOT NULL, 
	problem TEXT NOT NULL, 
	solution TEXT NOT NULL, 
	value_proposition TEXT, 
	trigger_event TEXT, 
	purchase_intent VARCHAR(50), 
	estimated_budget_level VARCHAR(50), 
	budget_hypothesis_text TEXT, 
	pain_score INTEGER NOT NULL, 
	budget_score INTEGER NOT NULL, 
	intent_score INTEGER NOT NULL, 
	urgency_score INTEGER NOT NULL, 
	agent_fit_score INTEGER NOT NULL, 
	reachability_score INTEGER NOT NULL, 
	evidence_score INTEGER NOT NULL, 
	total_score FLOAT NOT NULL, 
	grade VARCHAR(5) NOT NULL, 
	confidence INTEGER NOT NULL, 
	stage VARCHAR(30) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	owner VARCHAR(200), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(market_id) REFERENCES markets (id) ON DELETE SET NULL, 
	FOREIGN KEY(pain_point_id) REFERENCES pain_points (id) ON DELETE SET NULL, 
	FOREIGN KEY(primary_signal_id) REFERENCES signals (id) ON DELETE SET NULL
);

CREATE TABLE opportunity_evidences (
	id VARCHAR(32) NOT NULL, 
	opportunity_id VARCHAR(32) NOT NULL, 
	source_record_id VARCHAR(32), 
	signal_id VARCHAR(32), 
	evidence_type VARCHAR(50) NOT NULL, 
	evidence_excerpt TEXT, 
	weight INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(opportunity_id) REFERENCES opportunities (id) ON DELETE CASCADE, 
	FOREIGN KEY(signal_id) REFERENCES signals (id) ON DELETE SET NULL, 
	FOREIGN KEY(source_record_id) REFERENCES source_records (id) ON DELETE SET NULL
);

CREATE TABLE pain_point_evidences (
	id VARCHAR(32) NOT NULL, 
	pain_point_id VARCHAR(32) NOT NULL, 
	signal_id VARCHAR(32), 
	source_record_id VARCHAR(32), 
	evidence_excerpt TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(pain_point_id) REFERENCES pain_points (id) ON DELETE CASCADE, 
	FOREIGN KEY(signal_id) REFERENCES signals (id) ON DELETE SET NULL, 
	FOREIGN KEY(source_record_id) REFERENCES source_records (id) ON DELETE SET NULL
);

CREATE TABLE pain_points (
	id VARCHAR(32) NOT NULL, 
	company_id VARCHAR(32) NOT NULL, 
	market_id VARCHAR(32), 
	category VARCHAR(100) NOT NULL, 
	description TEXT NOT NULL, 
	confidence INTEGER NOT NULL, 
	reason TEXT, 
	status VARCHAR(30) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(market_id) REFERENCES markets (id) ON DELETE SET NULL
);

CREATE TABLE signals (
	id VARCHAR(32) NOT NULL, 
	company_id VARCHAR(32) NOT NULL, 
	market_id VARCHAR(32), 
	source_record_id VARCHAR(32) NOT NULL, 
	signal_type VARCHAR(80) NOT NULL, 
	title VARCHAR(500) NOT NULL, 
	description TEXT, 
	published_at DATETIME, 
	collected_at DATETIME NOT NULL, 
	confidence INTEGER NOT NULL, 
	reliability_score INTEGER NOT NULL, 
	heat_score FLOAT, 
	status VARCHAR(30) NOT NULL, 
	fact_or_inference VARCHAR(20) NOT NULL, 
	payload_json JSON NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(market_id) REFERENCES markets (id) ON DELETE SET NULL, 
	FOREIGN KEY(source_record_id) REFERENCES source_records (id) ON DELETE CASCADE
);

CREATE TABLE source_records (
	id VARCHAR(32) NOT NULL, 
	source_id VARCHAR(32) NOT NULL, 
	company_id VARCHAR(32), 
	url TEXT NOT NULL, 
	title TEXT, 
	raw_text TEXT, 
	raw_html_path TEXT, 
	published_at DATETIME, 
	collected_at DATETIME NOT NULL, 
	content_hash VARCHAR(64) NOT NULL, 
	http_status INTEGER, 
	language VARCHAR(20), 
	metadata_json JSON NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE SET NULL, 
	FOREIGN KEY(source_id) REFERENCES sources (id) ON DELETE CASCADE, 
	CONSTRAINT uq_source_record_hash UNIQUE (source_id, content_hash)
);

CREATE TABLE sources (
	id VARCHAR(32) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	source_type VARCHAR(50) NOT NULL, 
	base_url TEXT, 
	reliability_grade VARCHAR(1) NOT NULL, 
	reliability_score INTEGER NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	collector_type VARCHAR(100), 
	collection_frequency VARCHAR(100), 
	last_run_at DATETIME, 
	success_rate FLOAT, 
	notes TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE system_configs (
	id INTEGER NOT NULL, 
	"key" VARCHAR(100) NOT NULL, 
	value TEXT NOT NULL, 
	description TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_audit_logs_action ON audit_logs (action);

CREATE INDEX ix_audit_logs_entity_id ON audit_logs (entity_id);

CREATE INDEX ix_audit_logs_entity_type ON audit_logs (entity_type);

CREATE INDEX ix_collection_jobs_finished_at ON collection_jobs (finished_at);

CREATE INDEX ix_collection_jobs_name ON collection_jobs (name);

CREATE INDEX ix_collection_jobs_source_id ON collection_jobs (source_id);

CREATE INDEX ix_collection_jobs_started_at ON collection_jobs (started_at);

CREATE INDEX ix_collection_jobs_status ON collection_jobs (status);

CREATE INDEX ix_companies_city ON companies (city);

CREATE INDEX ix_companies_company_name ON companies (company_name);

CREATE INDEX ix_companies_country ON companies (country);

CREATE INDEX ix_companies_domain ON companies (domain);

CREATE INDEX ix_companies_industry ON companies (industry);

CREATE INDEX ix_companies_normalized_name ON companies (normalized_name);

CREATE INDEX ix_companies_opportunity_level ON companies (opportunity_level);

CREATE INDEX ix_companies_province ON companies (province);

CREATE INDEX ix_companies_status ON companies (status);

CREATE INDEX ix_companies_sub_industry ON companies (sub_industry);

CREATE INDEX ix_company_aliases_company_id ON company_aliases (company_id);

CREATE INDEX ix_company_aliases_normalized_alias ON company_aliases (normalized_alias);

CREATE INDEX ix_company_contacts_company_id ON company_contacts (company_id);

CREATE INDEX ix_company_contacts_source_record_id ON company_contacts (source_record_id);

CREATE INDEX ix_experiment_opportunities_experiment_id ON experiment_opportunities (experiment_id);

CREATE INDEX ix_experiment_opportunities_opportunity_id ON experiment_opportunities (opportunity_id);

CREATE INDEX ix_experiments_conclusion ON experiments (conclusion);

CREATE INDEX ix_experiments_market_id ON experiments (market_id);

CREATE INDEX ix_experiments_name ON experiments (name);

CREATE INDEX ix_experiments_status ON experiments (status);

CREATE INDEX ix_interactions_company_id ON interactions (company_id);

CREATE INDEX ix_interactions_contact_at ON interactions (contact_at);

CREATE INDEX ix_interactions_experiment_id ON interactions (experiment_id);

CREATE INDEX ix_interactions_opportunity_id ON interactions (opportunity_id);

CREATE INDEX ix_interactions_reject_reason ON interactions (reject_reason);

CREATE INDEX ix_interactions_response_type ON interactions (response_type);

CREATE INDEX ix_llm_runs_input_hash ON llm_runs (input_hash);

CREATE INDEX ix_llm_runs_model ON llm_runs (model);

CREATE INDEX ix_llm_runs_module ON llm_runs (module);

CREATE INDEX ix_llm_runs_prompt_version ON llm_runs (prompt_version);

CREATE INDEX ix_llm_runs_status ON llm_runs (status);

CREATE INDEX ix_llm_runs_target_id ON llm_runs (target_id);

CREATE INDEX ix_llm_runs_target_type ON llm_runs (target_type);

CREATE UNIQUE INDEX ix_markets_market_name ON markets (market_name);

CREATE INDEX ix_markets_market_score ON markets (market_score);

CREATE UNIQUE INDEX ix_markets_slug ON markets (slug);

CREATE INDEX ix_markets_validation_status ON markets (validation_status);

CREATE INDEX ix_opportunities_company_id ON opportunities (company_id);

CREATE INDEX ix_opportunities_grade ON opportunities (grade);

CREATE INDEX ix_opportunities_market_id ON opportunities (market_id);

CREATE INDEX ix_opportunities_pain_point_id ON opportunities (pain_point_id);

CREATE INDEX ix_opportunities_primary_signal_id ON opportunities (primary_signal_id);

CREATE INDEX ix_opportunities_stage ON opportunities (stage);

CREATE INDEX ix_opportunities_status ON opportunities (status);

CREATE INDEX ix_opportunities_total_score ON opportunities (total_score);

CREATE INDEX ix_opportunity_evidences_opportunity_id ON opportunity_evidences (opportunity_id);

CREATE INDEX ix_opportunity_evidences_signal_id ON opportunity_evidences (signal_id);

CREATE INDEX ix_opportunity_evidences_source_record_id ON opportunity_evidences (source_record_id);

CREATE INDEX ix_pain_point_evidences_pain_point_id ON pain_point_evidences (pain_point_id);

CREATE INDEX ix_pain_point_evidences_signal_id ON pain_point_evidences (signal_id);

CREATE INDEX ix_pain_point_evidences_source_record_id ON pain_point_evidences (source_record_id);

CREATE INDEX ix_pain_points_category ON pain_points (category);

CREATE INDEX ix_pain_points_company_id ON pain_points (company_id);

CREATE INDEX ix_pain_points_market_id ON pain_points (market_id);

CREATE INDEX ix_pain_points_status ON pain_points (status);

CREATE INDEX ix_signals_collected_at ON signals (collected_at);

CREATE INDEX ix_signals_company_id ON signals (company_id);

CREATE INDEX ix_signals_market_id ON signals (market_id);

CREATE INDEX ix_signals_published_at ON signals (published_at);

CREATE INDEX ix_signals_signal_type ON signals (signal_type);

CREATE INDEX ix_signals_source_record_id ON signals (source_record_id);

CREATE INDEX ix_signals_status ON signals (status);

CREATE INDEX ix_source_records_collected_at ON source_records (collected_at);

CREATE INDEX ix_source_records_company_id ON source_records (company_id);

CREATE INDEX ix_source_records_content_hash ON source_records (content_hash);

CREATE INDEX ix_source_records_published_at ON source_records (published_at);

CREATE INDEX ix_source_records_source_id ON source_records (source_id);

CREATE INDEX ix_sources_name ON sources (name);

CREATE INDEX ix_sources_source_type ON sources (source_type);

CREATE UNIQUE INDEX ix_system_configs_key ON system_configs ("key");
