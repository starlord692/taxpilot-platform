"""Create RC1 baseline schema.

Revision ID: 20260726_0001_rc1_baseline

Revises: None

"""

# ruff: noqa: E501, PLR0915

from collections.abc import Sequence

from alembic import op

revision: str = "20260726_0001_rc1_baseline"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create the complete RC1 schema baseline."""
    op.execute("""CREATE TYPE business_type AS ENUM ('SOLE_PROPRIETOR', 'PARTNERSHIP', 'PRIVATE_LIMITED', 'LLP', 'FREELANCER', 'NON_PROFIT');""")
    op.execute("""CREATE TYPE business_registration_status AS ENUM ('REGISTERED', 'UNREGISTERED', 'PENDING');""")
    op.execute("""CREATE TYPE business_status AS ENUM ('ACTIVE', 'INACTIVE', 'ARCHIVED');""")
    op.execute("""CREATE TYPE gst_provider_type AS ENUM ('MOCK', 'GSP', 'NIC');""")
    op.execute("""CREATE TYPE identity_user_status AS ENUM ('PENDING', 'ACTIVE', 'DISABLED', 'LOCKED');""")
    op.execute("""CREATE TYPE document_type AS ENUM ('UNKNOWN', 'SALES_INVOICE', 'PURCHASE_INVOICE', 'EXPENSE_RECEIPT', 'BANK_STATEMENT', 'GST_CERTIFICATE', 'PAN', 'OTHER');""")
    op.execute("""CREATE TYPE document_extraction_status AS ENUM ('UPLOADED', 'OCR_PENDING', 'OCR_RUNNING', 'OCR_COMPLETED', 'OCR_FAILED');""")
    op.execute("""CREATE TYPE gst_registration_type AS ENUM ('REGULAR', 'COMPOSITION', 'CASUAL', 'NON_RESIDENT');""")
    op.execute("""CREATE TYPE gst_filing_frequency AS ENUM ('MONTHLY', 'QUARTERLY');""")
    op.execute("""CREATE TYPE gst_return_status AS ENUM ('GENERATED', 'FILED');""")
    op.execute("""CREATE TYPE gst_tax_mode AS ENUM ('INTRA_STATE', 'INTER_STATE');""")
    op.execute("""CREATE TYPE gst_rounding_method AS ENUM ('NEAREST', 'UP', 'DOWN');""")
    op.execute("""CREATE TYPE journal_status AS ENUM ('DRAFT', 'POSTED', 'REVERSED');""")
    op.execute("""CREATE TYPE document_automation_type AS ENUM ('SALES', 'PURCHASE', 'EXPENSE');""")
    op.execute("""CREATE TYPE document_automation_state AS ENUM ('NOT_STARTED', 'RUNNING', 'COMPLETED', 'FAILED', 'ROLLED_BACK');""")
    op.execute("""CREATE TYPE document_review_decision_type AS ENUM ('APPROVE', 'REJECT', 'REQUEST_CORRECTION');""")
    op.execute("""CREATE TYPE document_review_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED', 'CORRECTION_REQUESTED');""")
    op.execute("""CREATE TYPE document_validation_severity AS ENUM ('ERROR', 'WARNING', 'INFO');""")
    op.execute("""CREATE TYPE document_validation_category AS ENUM ('GST', 'PAN', 'TOTAL', 'TAX', 'DUPLICATE', 'DATE', 'CURRENCY', 'MANDATORY', 'MATCHING');""")
    op.execute("""CREATE TYPE expense_category AS ENUM ('TRAVEL', 'OFFICE', 'RENT', 'UTILITIES', 'MARKETING', 'SALARY', 'PROFESSIONAL_FEES', 'SOFTWARE', 'HARDWARE', 'OTHER');""")
    op.execute("""CREATE TYPE expense_status AS ENUM ('DRAFT', 'APPROVED', 'PAID', 'CANCELLED');""")
    op.execute("""CREATE TYPE extracted_document_type AS ENUM ('UNKNOWN', 'SALES_INVOICE', 'PURCHASE_INVOICE', 'EXPENSE_RECEIPT', 'BANK_STATEMENT', 'GST_CERTIFICATE', 'PAN', 'OTHER');""")
    op.execute("""CREATE TYPE document_extraction_run_status AS ENUM ('COMPLETED', 'FAILED', 'REVIEW_REQUIRED');""")
    op.execute("""CREATE TYPE inventory_movement_type AS ENUM ('PURCHASE', 'SALE', 'ADJUSTMENT', 'RETURN', 'TRANSFER');""")
    op.execute("""CREATE TYPE purchase_status AS ENUM ('DRAFT', 'APPROVED', 'RECEIVED', 'PAID', 'CANCELLED');""")
    op.execute("""CREATE TYPE invoice_status AS ENUM ('DRAFT', 'ISSUED', 'PARTIALLY_PAID', 'PAID', 'CANCELLED');""")
    op.execute("""CREATE TYPE extracted_field_source AS ENUM ('RULE', 'AI', 'VALIDATION');""")
    op.execute("""CREATE TYPE e_invoice_status AS ENUM ('GENERATED', 'CANCELLED');""")
    op.execute("""CREATE TYPE eway_bill_transport_mode AS ENUM ('ROAD', 'RAIL', 'AIR', 'SHIP');""")
    op.execute("""CREATE TYPE eway_bill_status AS ENUM ('GENERATED', 'CANCELLED', 'EXPIRED');""")
    op.execute("""CREATE TYPE payment_method AS ENUM ('CASH', 'BANK_TRANSFER', 'UPI', 'CARD', 'CHEQUE', 'OTHER');""")
    op.execute("""CREATE TABLE account_categories (
	name VARCHAR(100) NOT NULL,
	description VARCHAR(255),
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name)
);""")
    op.execute("""CREATE INDEX ix_account_categories_name ON account_categories (name);""")
    op.execute("""CREATE TABLE businesses (
	business_code VARCHAR(40),
	legal_name VARCHAR(255) NOT NULL,
	trade_name VARCHAR(255),
	business_type business_type NOT NULL,
	registration_status business_registration_status NOT NULL,
	business_email VARCHAR(320),
	business_phone VARCHAR(30),
	website VARCHAR(255),
	logo_url VARCHAR(500),
	status business_status NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (business_code)
);""")
    op.execute("""CREATE INDEX ix_businesses_business_type ON businesses (business_type);""")
    op.execute("""CREATE INDEX ix_businesses_legal_name ON businesses (legal_name);""")
    op.execute("""CREATE INDEX ix_businesses_status ON businesses (status);""")
    op.execute("""CREATE TABLE gst_audit_reports (
	business_id UUID NOT NULL,
	tax_period VARCHAR(10) NOT NULL,
	generated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	issue_count INTEGER NOT NULL,
	payload JSON NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id)
);""")
    op.execute("""CREATE INDEX ix_gst_audit_reports_business_id ON gst_audit_reports (business_id);""")
    op.execute("""CREATE TABLE gst_providers (
	name VARCHAR(100) NOT NULL,
	base_url VARCHAR(500) NOT NULL,
	provider_type gst_provider_type NOT NULL,
	is_active BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id)
);""")
    op.execute("""CREATE INDEX ix_gst_providers_is_active ON gst_providers (is_active);""")
    op.execute("""CREATE UNIQUE INDEX ix_gst_providers_name ON gst_providers (name);""")
    op.execute("""CREATE TABLE gst_tax_rates (
	name VARCHAR(120) NOT NULL,
	cgst_rate NUMERIC(5, 2) NOT NULL,
	sgst_rate NUMERIC(5, 2) NOT NULL,
	igst_rate NUMERIC(5, 2) NOT NULL,
	cess_rate NUMERIC(5, 2) NOT NULL,
	effective_from DATE NOT NULL,
	effective_to DATE,
	is_active BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name)
);""")
    op.execute("""CREATE INDEX ix_gst_tax_rates_effective_from ON gst_tax_rates (effective_from);""")
    op.execute("""CREATE INDEX ix_gst_tax_rates_is_active ON gst_tax_rates (is_active);""")
    op.execute("""CREATE INDEX ix_gst_tax_rates_name ON gst_tax_rates (name);""")
    op.execute("""CREATE TABLE identity_permissions (
	name VARCHAR(120) NOT NULL,
	description VARCHAR(255),
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name)
);""")
    op.execute("""CREATE INDEX ix_identity_permissions_name ON identity_permissions (name);""")
    op.execute("""CREATE TABLE identity_roles (
	name VARCHAR(80) NOT NULL,
	description VARCHAR(255),
	is_system BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name)
);""")
    op.execute("""CREATE INDEX ix_identity_roles_name ON identity_roles (name);""")
    op.execute("""CREATE TABLE identity_users (
	email VARCHAR(320) NOT NULL,
	first_name VARCHAR(100) NOT NULL,
	last_name VARCHAR(100) NOT NULL,
	display_name VARCHAR(150) NOT NULL,
	status identity_user_status NOT NULL,
	last_login_at TIMESTAMP WITHOUT TIME ZONE,
	failed_login_attempts INTEGER NOT NULL,
	locked_until TIMESTAMP WITHOUT TIME ZONE,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (email)
);""")
    op.execute("""CREATE INDEX ix_identity_users_email ON identity_users (email);""")
    op.execute("""CREATE INDEX ix_identity_users_status ON identity_users (status);""")
    op.execute("""CREATE TABLE account_types (
	category_id UUID NOT NULL,
	name VARCHAR(100) NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_account_types_category_name UNIQUE (category_id, name),
	FOREIGN KEY(category_id) REFERENCES account_categories (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_account_types_category_id ON account_types (category_id);""")
    op.execute("""CREATE INDEX ix_account_types_name ON account_types (name);""")
    op.execute("""CREATE TABLE business_addresses (
	business_id UUID NOT NULL,
	address_line_1 VARCHAR(255) NOT NULL,
	address_line_2 VARCHAR(255),
	city VARCHAR(100) NOT NULL,
	state VARCHAR(100) NOT NULL,
	country VARCHAR(100) NOT NULL,
	postal_code VARCHAR(20) NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (business_id),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_business_addresses_business_id ON business_addresses (business_id);""")
    op.execute("""CREATE TABLE business_memberships (
	business_id UUID NOT NULL,
	user_id UUID NOT NULL,
	role VARCHAR(80) NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_business_memberships_business_user UNIQUE (business_id, user_id),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE,
	FOREIGN KEY(user_id) REFERENCES identity_users (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_business_memberships_business_id ON business_memberships (business_id);""")
    op.execute("""CREATE INDEX ix_business_memberships_role ON business_memberships (role);""")
    op.execute("""CREATE INDEX ix_business_memberships_user_id ON business_memberships (user_id);""")
    op.execute("""CREATE TABLE business_settings (
	business_id UUID NOT NULL,
	currency VARCHAR(3) NOT NULL,
	timezone VARCHAR(100) NOT NULL,
	date_format VARCHAR(30) NOT NULL,
	language VARCHAR(10) NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (business_id),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_business_settings_business_id ON business_settings (business_id);""")
    op.execute("""CREATE TABLE business_tax_profiles (
	business_id UUID NOT NULL,
	gstin VARCHAR(15),
	pan VARCHAR(10),
	tan VARCHAR(10),
	financial_year_start DATE NOT NULL,
	gst_registered BOOLEAN NOT NULL,
	composition_scheme BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (business_id),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_business_tax_profiles_business_id ON business_tax_profiles (business_id);""")
    op.execute("""CREATE INDEX ix_business_tax_profiles_gstin ON business_tax_profiles (gstin);""")
    op.execute("""CREATE INDEX ix_business_tax_profiles_pan ON business_tax_profiles (pan);""")
    op.execute("""CREATE TABLE catalog_items (
	business_id UUID NOT NULL,
	code VARCHAR(80),
	name VARCHAR(255) NOT NULL,
	description TEXT,
	item_type VARCHAR(16) NOT NULL,
	status VARCHAR(16) NOT NULL,
	category VARCHAR(120),
	purchase_price NUMERIC(18, 2) NOT NULL,
	selling_price NUMERIC(18, 2) NOT NULL,
	default_unit VARCHAR(30) NOT NULL,
	barcode VARCHAR(100),
	hsn_code VARCHAR(8),
	sac_code VARCHAR(8),
	gst_rate NUMERIC(5, 2) NOT NULL,
	cess_rate NUMERIC(5, 2) NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_catalog_items_business_code UNIQUE (business_id, code),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_catalog_items_business_type ON catalog_items (business_id, item_type);""")
    op.execute("""CREATE INDEX ix_catalog_items_name ON catalog_items (name);""")
    op.execute("""CREATE TABLE customers (
	business_id UUID NOT NULL,
	customer_code VARCHAR(50) NOT NULL,
	name VARCHAR(255) NOT NULL,
	email VARCHAR(320),
	phone VARCHAR(30),
	gstin VARCHAR(15),
	pan VARCHAR(10),
	billing_address TEXT,
	shipping_address TEXT,
	is_active BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_customers_business_customer_code UNIQUE (business_id, customer_code),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_customers_business_id ON customers (business_id);""")
    op.execute("""CREATE INDEX ix_customers_customer_code ON customers (customer_code);""")
    op.execute("""CREATE INDEX ix_customers_email ON customers (email);""")
    op.execute("""CREATE INDEX ix_customers_name ON customers (name);""")
    op.execute("""CREATE TABLE documents (
	business_id UUID NOT NULL,
	uploaded_by UUID NOT NULL,
	original_filename VARCHAR(255) NOT NULL,
	mime_type VARCHAR(100) NOT NULL,
	file_size INTEGER NOT NULL,
	storage_path VARCHAR(500) NOT NULL,
	checksum VARCHAR(64) NOT NULL,
	document_type document_type NOT NULL,
	status document_extraction_status NOT NULL,
	page_count INTEGER NOT NULL,
	uploaded_at TIMESTAMP WITH TIME ZONE NOT NULL,
	processed_at TIMESTAMP WITH TIME ZONE,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE,
	FOREIGN KEY(uploaded_by) REFERENCES identity_users (id) ON DELETE RESTRICT
);""")
    op.execute("""CREATE INDEX ix_documents_business_id ON documents (business_id);""")
    op.execute("""CREATE INDEX ix_documents_checksum ON documents (checksum);""")
    op.execute("""CREATE INDEX ix_documents_document_type ON documents (document_type);""")
    op.execute("""CREATE INDEX ix_documents_status ON documents (status);""")
    op.execute("""CREATE INDEX ix_documents_uploaded_by ON documents (uploaded_by);""")
    op.execute("""CREATE TABLE gst_hsn_codes (
	code VARCHAR(8) NOT NULL,
	description TEXT NOT NULL,
	default_tax_rate_id UUID,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(default_tax_rate_id) REFERENCES gst_tax_rates (id) ON DELETE SET NULL
);""")
    op.execute("""CREATE UNIQUE INDEX ix_gst_hsn_codes_code ON gst_hsn_codes (code);""")
    op.execute("""CREATE INDEX ix_gst_hsn_codes_default_tax_rate_id ON gst_hsn_codes (default_tax_rate_id);""")
    op.execute("""CREATE TABLE gst_registrations (
	business_id UUID NOT NULL,
	gstin VARCHAR(15) NOT NULL,
	legal_name VARCHAR(150) NOT NULL,
	trade_name VARCHAR(150),
	registration_type gst_registration_type NOT NULL,
	state_code VARCHAR(2) NOT NULL,
	registration_date DATE NOT NULL,
	is_composition_scheme BOOLEAN NOT NULL,
	is_active BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_gst_registrations_gstin UNIQUE (gstin),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_gst_registrations_business_id ON gst_registrations (business_id);""")
    op.execute("""CREATE INDEX ix_gst_registrations_gstin ON gst_registrations (gstin);""")
    op.execute("""CREATE INDEX ix_gst_registrations_is_active ON gst_registrations (is_active);""")
    op.execute("""CREATE TABLE gst_return_periods (
	business_id UUID NOT NULL,
	financial_year VARCHAR(9) NOT NULL,
	tax_period VARCHAR(10) NOT NULL,
	filing_frequency gst_filing_frequency NOT NULL,
	status gst_return_status NOT NULL,
	generated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	filed_at TIMESTAMP WITH TIME ZONE,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_gst_return_period_business_period UNIQUE (business_id, financial_year, tax_period),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_gst_return_periods_business_id ON gst_return_periods (business_id);""")
    op.execute("""CREATE INDEX ix_gst_return_periods_status ON gst_return_periods (status);""")
    op.execute("""CREATE INDEX ix_gst_return_periods_tax_period ON gst_return_periods (tax_period);""")
    op.execute("""CREATE TABLE gst_sac_codes (
	code VARCHAR(6) NOT NULL,
	description TEXT NOT NULL,
	default_tax_rate_id UUID,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(default_tax_rate_id) REFERENCES gst_tax_rates (id) ON DELETE SET NULL
);""")
    op.execute("""CREATE UNIQUE INDEX ix_gst_sac_codes_code ON gst_sac_codes (code);""")
    op.execute("""CREATE INDEX ix_gst_sac_codes_default_tax_rate_id ON gst_sac_codes (default_tax_rate_id);""")
    op.execute("""CREATE TABLE gst_settings (
	business_id UUID NOT NULL,
	default_tax_mode gst_tax_mode NOT NULL,
	tax_inclusive BOOLEAN NOT NULL,
	rounding_method gst_rounding_method NOT NULL,
	allow_manual_override BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_gst_settings_business_id UNIQUE (business_id),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_gst_settings_business_id ON gst_settings (business_id);""")
    op.execute("""CREATE TABLE identity_credentials (
	user_id UUID NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	password_changed_at TIMESTAMP WITH TIME ZONE NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (user_id),
	FOREIGN KEY(user_id) REFERENCES identity_users (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_identity_credentials_user_id ON identity_credentials (user_id);""")
    op.execute("""CREATE TABLE identity_email_verifications (
	user_id UUID NOT NULL,
	verification_token VARCHAR(255) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	verified_at TIMESTAMP WITH TIME ZONE,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES identity_users (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_identity_email_verifications_token ON identity_email_verifications (verification_token);""")
    op.execute("""CREATE INDEX ix_identity_email_verifications_user_id ON identity_email_verifications (user_id);""")
    op.execute("""CREATE TABLE identity_login_history (
	user_id UUID NOT NULL,
	login_at TIMESTAMP WITH TIME ZONE NOT NULL,
	ip_address VARCHAR(45),
	user_agent VARCHAR(512),
	success BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES identity_users (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_identity_login_history_login_at ON identity_login_history (login_at);""")
    op.execute("""CREATE INDEX ix_identity_login_history_user_id ON identity_login_history (user_id);""")
    op.execute("""CREATE TABLE identity_password_resets (
	user_id UUID NOT NULL,
	reset_token VARCHAR(255) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	used_at TIMESTAMP WITH TIME ZONE,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES identity_users (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_identity_password_resets_token ON identity_password_resets (reset_token);""")
    op.execute("""CREATE INDEX ix_identity_password_resets_user_id ON identity_password_resets (user_id);""")
    op.execute("""CREATE TABLE identity_refresh_tokens (
	user_id UUID NOT NULL,
	token_hash VARCHAR(255) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	revoked_at TIMESTAMP WITH TIME ZONE,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES identity_users (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_identity_refresh_tokens_token_hash ON identity_refresh_tokens (token_hash);""")
    op.execute("""CREATE INDEX ix_identity_refresh_tokens_user_id ON identity_refresh_tokens (user_id);""")
    op.execute("""CREATE TABLE identity_role_permissions (
	role_id UUID NOT NULL,
	permission_id UUID NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_identity_role_permissions_role_permission UNIQUE (role_id, permission_id),
	FOREIGN KEY(role_id) REFERENCES identity_roles (id) ON DELETE CASCADE,
	FOREIGN KEY(permission_id) REFERENCES identity_permissions (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_identity_role_permissions_permission_id ON identity_role_permissions (permission_id);""")
    op.execute("""CREATE INDEX ix_identity_role_permissions_role_id ON identity_role_permissions (role_id);""")
    op.execute("""CREATE TABLE identity_user_roles (
	user_id UUID NOT NULL,
	role_id UUID NOT NULL,
	assigned_at TIMESTAMP WITH TIME ZONE NOT NULL,
	assigned_by UUID,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_identity_user_roles_user_role UNIQUE (user_id, role_id),
	FOREIGN KEY(user_id) REFERENCES identity_users (id) ON DELETE CASCADE,
	FOREIGN KEY(role_id) REFERENCES identity_roles (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_identity_user_roles_role_id ON identity_user_roles (role_id);""")
    op.execute("""CREATE INDEX ix_identity_user_roles_user_id ON identity_user_roles (user_id);""")
    op.execute("""CREATE TABLE inventory_products (
	business_id UUID NOT NULL,
	sku VARCHAR(80) NOT NULL,
	name VARCHAR(255) NOT NULL,
	description TEXT,
	category VARCHAR(120),
	unit_of_measure VARCHAR(30) NOT NULL,
	barcode VARCHAR(100),
	purchase_price NUMERIC(18, 2) NOT NULL,
	selling_price NUMERIC(18, 2) NOT NULL,
	reorder_level NUMERIC(18, 4) NOT NULL,
	is_active BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_inventory_products_business_sku UNIQUE (business_id, sku),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_inventory_products_barcode ON inventory_products (barcode);""")
    op.execute("""CREATE INDEX ix_inventory_products_business_id ON inventory_products (business_id);""")
    op.execute("""CREATE INDEX ix_inventory_products_category ON inventory_products (category);""")
    op.execute("""CREATE INDEX ix_inventory_products_sku ON inventory_products (sku);""")
    op.execute("""CREATE TABLE inventory_warehouses (
	business_id UUID NOT NULL,
	code VARCHAR(50) NOT NULL,
	name VARCHAR(255) NOT NULL,
	address TEXT,
	is_default BOOLEAN NOT NULL,
	is_active BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_inventory_warehouses_business_code UNIQUE (business_id, code),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_inventory_warehouses_business_id ON inventory_warehouses (business_id);""")
    op.execute("""CREATE INDEX ix_inventory_warehouses_code ON inventory_warehouses (code);""")
    op.execute("""CREATE INDEX ix_inventory_warehouses_name ON inventory_warehouses (name);""")
    op.execute("""CREATE TABLE journal_entries (
	business_id UUID NOT NULL,
	journal_number VARCHAR(50) NOT NULL,
	transaction_date DATE NOT NULL,
	posting_date DATE,
	reference VARCHAR(100),
	description VARCHAR(255),
	status journal_status NOT NULL,
	created_by UUID,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_journal_entries_business_journal_number UNIQUE (business_id, journal_number),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_journal_entries_business_id ON journal_entries (business_id);""")
    op.execute("""CREATE INDEX ix_journal_entries_journal_number ON journal_entries (journal_number);""")
    op.execute("""CREATE INDEX ix_journal_entries_status ON journal_entries (status);""")
    op.execute("""CREATE INDEX ix_journal_entries_transaction_date ON journal_entries (transaction_date);""")
    op.execute("""CREATE TABLE sales_invoice_number_sequences (
	business_id UUID NOT NULL,
	financial_year VARCHAR(9) NOT NULL,
	prefix VARCHAR(20) NOT NULL,
	next_value INTEGER NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_sales_invoice_sequence_business_year UNIQUE (business_id, financial_year),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE TABLE suppliers (
	business_id UUID NOT NULL,
	supplier_code VARCHAR(50) NOT NULL,
	name VARCHAR(255) NOT NULL,
	email VARCHAR(320),
	phone VARCHAR(30),
	gstin VARCHAR(15),
	pan VARCHAR(10),
	address TEXT,
	payment_terms VARCHAR(100),
	is_active BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_suppliers_business_supplier_code UNIQUE (business_id, supplier_code),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_suppliers_business_id ON suppliers (business_id);""")
    op.execute("""CREATE INDEX ix_suppliers_email ON suppliers (email);""")
    op.execute("""CREATE INDEX ix_suppliers_name ON suppliers (name);""")
    op.execute("""CREATE INDEX ix_suppliers_supplier_code ON suppliers (supplier_code);""")
    op.execute("""CREATE TABLE vendors (
	business_id UUID NOT NULL,
	vendor_code VARCHAR(50) NOT NULL,
	name VARCHAR(255) NOT NULL,
	email VARCHAR(320),
	phone VARCHAR(30),
	gstin VARCHAR(15),
	pan VARCHAR(10),
	address TEXT,
	is_active BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_vendors_business_vendor_code UNIQUE (business_id, vendor_code),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_vendors_business_id ON vendors (business_id);""")
    op.execute("""CREATE INDEX ix_vendors_email ON vendors (email);""")
    op.execute("""CREATE INDEX ix_vendors_name ON vendors (name);""")
    op.execute("""CREATE INDEX ix_vendors_vendor_code ON vendors (vendor_code);""")
    op.execute("""CREATE TABLE accounts (
	business_id UUID NOT NULL,
	account_code VARCHAR(50) NOT NULL,
	account_name VARCHAR(150) NOT NULL,
	account_type_id UUID NOT NULL,
	parent_account_id UUID,
	description VARCHAR(255),
	is_system BOOLEAN NOT NULL,
	is_active BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_accounts_business_account_code UNIQUE (business_id, account_code),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE,
	FOREIGN KEY(account_type_id) REFERENCES account_types (id) ON DELETE RESTRICT,
	FOREIGN KEY(parent_account_id) REFERENCES accounts (id) ON DELETE RESTRICT
);""")
    op.execute("""CREATE INDEX ix_accounts_account_name ON accounts (account_name);""")
    op.execute("""CREATE INDEX ix_accounts_account_type_id ON accounts (account_type_id);""")
    op.execute("""CREATE INDEX ix_accounts_business_id ON accounts (business_id);""")
    op.execute("""CREATE INDEX ix_accounts_parent_account_id ON accounts (parent_account_id);""")
    op.execute("""CREATE TABLE document_automation_runs (
	document_id UUID NOT NULL,
	business_id UUID NOT NULL,
	automation_type document_automation_type NOT NULL,
	idempotency_key VARCHAR(128) NOT NULL,
	status document_automation_state NOT NULL,
	erp_record_type VARCHAR(100),
	erp_record_id UUID,
	started_at TIMESTAMP WITH TIME ZONE,
	completed_at TIMESTAMP WITH TIME ZONE,
	failure_reason TEXT,
	retry_count INTEGER NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE,
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_document_automation_runs_business_id ON document_automation_runs (business_id);""")
    op.execute("""CREATE INDEX ix_document_automation_runs_document_id ON document_automation_runs (document_id);""")
    op.execute("""CREATE INDEX ix_document_automation_runs_erp_record ON document_automation_runs (erp_record_type, erp_record_id);""")
    op.execute("""CREATE UNIQUE INDEX ix_document_automation_runs_idempotency_key ON document_automation_runs (idempotency_key);""")
    op.execute("""CREATE INDEX ix_document_automation_runs_status ON document_automation_runs (status);""")
    op.execute("""CREATE TABLE document_pages (
	document_id UUID NOT NULL,
	page_number INTEGER NOT NULL,
	storage_path VARCHAR(500),
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_document_pages_document_page_number UNIQUE (document_id, page_number),
	FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_document_pages_document_id ON document_pages (document_id);""")
    op.execute("""CREATE TABLE document_review_decisions (
	document_id UUID NOT NULL,
	decision document_review_decision_type NOT NULL,
	decided_by UUID NOT NULL,
	decided_at TIMESTAMP WITH TIME ZONE NOT NULL,
	notes TEXT,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE,
	FOREIGN KEY(decided_by) REFERENCES identity_users (id) ON DELETE RESTRICT
);""")
    op.execute("""CREATE INDEX ix_document_review_decisions_decision ON document_review_decisions (decision);""")
    op.execute("""CREATE INDEX ix_document_review_decisions_document_id ON document_review_decisions (document_id);""")
    op.execute("""CREATE TABLE document_review_revisions (
	document_id UUID NOT NULL,
	field_name VARCHAR(100) NOT NULL,
	old_value TEXT,
	new_value TEXT NOT NULL,
	changed_by UUID NOT NULL,
	changed_at TIMESTAMP WITH TIME ZONE NOT NULL,
	reason TEXT NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE,
	FOREIGN KEY(changed_by) REFERENCES identity_users (id) ON DELETE RESTRICT
);""")
    op.execute("""CREATE INDEX ix_document_review_revisions_document_id ON document_review_revisions (document_id);""")
    op.execute("""CREATE INDEX ix_document_review_revisions_field_name ON document_review_revisions (field_name);""")
    op.execute("""CREATE TABLE document_reviews (
	document_id UUID NOT NULL,
	review_status document_review_status NOT NULL,
	reviewed_by UUID,
	reviewed_at TIMESTAMP WITH TIME ZONE,
	review_notes TEXT,
	ready_for_automation BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE,
	FOREIGN KEY(reviewed_by) REFERENCES identity_users (id) ON DELETE SET NULL
);""")
    op.execute("""CREATE UNIQUE INDEX ix_document_reviews_document_id ON document_reviews (document_id);""")
    op.execute("""CREATE INDEX ix_document_reviews_ready ON document_reviews (ready_for_automation);""")
    op.execute("""CREATE INDEX ix_document_reviews_status ON document_reviews (review_status);""")
    op.execute("""CREATE TABLE document_validation_issues (
	document_id UUID NOT NULL,
	severity document_validation_severity NOT NULL,
	category document_validation_category NOT NULL,
	field_name VARCHAR(100) NOT NULL,
	message TEXT NOT NULL,
	expected_value TEXT,
	actual_value TEXT,
	resolved BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_document_validation_issues_category ON document_validation_issues (category);""")
    op.execute("""CREATE INDEX ix_document_validation_issues_document_id ON document_validation_issues (document_id);""")
    op.execute("""CREATE INDEX ix_document_validation_issues_resolved ON document_validation_issues (resolved);""")
    op.execute("""CREATE INDEX ix_document_validation_issues_severity ON document_validation_issues (severity);""")
    op.execute("""CREATE TABLE expenses (
	business_id UUID NOT NULL,
	vendor_id UUID,
	expense_number VARCHAR(50) NOT NULL,
	expense_date DATE NOT NULL,
	category expense_category NOT NULL,
	description VARCHAR(255),
	status expense_status NOT NULL,
	subtotal NUMERIC(18, 2) NOT NULL,
	tax_amount NUMERIC(18, 2) NOT NULL,
	total_amount NUMERIC(18, 2) NOT NULL,
	notes TEXT,
	attachment_count INTEGER NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_expenses_business_expense_number UNIQUE (business_id, expense_number),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE,
	FOREIGN KEY(vendor_id) REFERENCES vendors (id) ON DELETE SET NULL
);""")
    op.execute("""CREATE INDEX ix_expenses_business_id ON expenses (business_id);""")
    op.execute("""CREATE INDEX ix_expenses_category ON expenses (category);""")
    op.execute("""CREATE INDEX ix_expenses_expense_date ON expenses (expense_date);""")
    op.execute("""CREATE INDEX ix_expenses_expense_number ON expenses (expense_number);""")
    op.execute("""CREATE INDEX ix_expenses_status ON expenses (status);""")
    op.execute("""CREATE INDEX ix_expenses_vendor_id ON expenses (vendor_id);""")
    op.execute("""CREATE TABLE extracted_documents (
	document_id UUID NOT NULL,
	business_id UUID NOT NULL,
	document_type extracted_document_type NOT NULL,
	overall_confidence NUMERIC(5, 2) NOT NULL,
	status document_extraction_run_status NOT NULL,
	review_required BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_extracted_documents_document_id UNIQUE (document_id),
	FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE,
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_extracted_documents_business_id ON extracted_documents (business_id);""")
    op.execute("""CREATE INDEX ix_extracted_documents_document_id ON extracted_documents (document_id);""")
    op.execute("""CREATE INDEX ix_extracted_documents_status ON extracted_documents (status);""")
    op.execute("""CREATE TABLE gst_gstr1_summaries (
	return_period_id UUID NOT NULL,
	generated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	taxable_value NUMERIC(18, 2) NOT NULL,
	tax_amount NUMERIC(18, 2) NOT NULL,
	payload JSON NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(return_period_id) REFERENCES gst_return_periods (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_gst_gstr1_return_period_id ON gst_gstr1_summaries (return_period_id);""")
    op.execute("""CREATE TABLE gst_gstr3b_summaries (
	return_period_id UUID NOT NULL,
	generated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	outward_taxable_supplies NUMERIC(18, 2) NOT NULL,
	input_tax_credit NUMERIC(18, 2) NOT NULL,
	net_gst_payable NUMERIC(18, 2) NOT NULL,
	payload JSON NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(return_period_id) REFERENCES gst_return_periods (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_gst_gstr3b_return_period_id ON gst_gstr3b_summaries (return_period_id);""")
    op.execute("""CREATE TABLE gst_itc_reconciliations (
	return_period_id UUID NOT NULL,
	eligible_itc NUMERIC(18, 2) NOT NULL,
	blocked_itc NUMERIC(18, 2) NOT NULL,
	rcm_itc NUMERIC(18, 2) NOT NULL,
	pending_itc NUMERIC(18, 2) NOT NULL,
	payload JSON NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(return_period_id) REFERENCES gst_return_periods (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_gst_itc_return_period_id ON gst_itc_reconciliations (return_period_id);""")
    op.execute("""CREATE TABLE inventory_item_profiles (
	catalog_item_id UUID NOT NULL,
	legacy_product_id UUID,
	stock_tracking BOOLEAN NOT NULL,
	reorder_level NUMERIC(18, 4),
	opening_quantity NUMERIC(18, 4),
	opening_value NUMERIC(18, 2),
	default_warehouse_id UUID,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_inventory_profiles_catalog_item UNIQUE (catalog_item_id),
	FOREIGN KEY(catalog_item_id) REFERENCES catalog_items (id) ON DELETE CASCADE,
	UNIQUE (legacy_product_id),
	FOREIGN KEY(legacy_product_id) REFERENCES inventory_products (id) ON DELETE SET NULL,
	FOREIGN KEY(default_warehouse_id) REFERENCES inventory_warehouses (id) ON DELETE SET NULL
);""")
    op.execute("""CREATE TABLE inventory_stock_balances (
	business_id UUID NOT NULL,
	product_id UUID NOT NULL,
	warehouse_id UUID NOT NULL,
	quantity_on_hand NUMERIC(18, 4) NOT NULL,
	quantity_reserved NUMERIC(18, 4) NOT NULL,
	quantity_available NUMERIC(18, 4) NOT NULL,
	last_updated TIMESTAMP WITH TIME ZONE NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_inventory_stock_balances_product_warehouse UNIQUE (product_id, warehouse_id),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE,
	FOREIGN KEY(product_id) REFERENCES inventory_products (id) ON DELETE CASCADE,
	FOREIGN KEY(warehouse_id) REFERENCES inventory_warehouses (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_inventory_stock_balances_business_id ON inventory_stock_balances (business_id);""")
    op.execute("""CREATE INDEX ix_inventory_stock_balances_product_id ON inventory_stock_balances (product_id);""")
    op.execute("""CREATE INDEX ix_inventory_stock_balances_warehouse_id ON inventory_stock_balances (warehouse_id);""")
    op.execute("""CREATE TABLE inventory_stock_movements (
	business_id UUID NOT NULL,
	product_id UUID NOT NULL,
	warehouse_id UUID NOT NULL,
	movement_type inventory_movement_type NOT NULL,
	quantity NUMERIC(18, 4) NOT NULL,
	reference_type VARCHAR(80),
	reference_id UUID,
	notes TEXT,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE,
	FOREIGN KEY(product_id) REFERENCES inventory_products (id) ON DELETE RESTRICT,
	FOREIGN KEY(warehouse_id) REFERENCES inventory_warehouses (id) ON DELETE RESTRICT
);""")
    op.execute("""CREATE INDEX ix_inventory_stock_movements_business_id ON inventory_stock_movements (business_id);""")
    op.execute("""CREATE INDEX ix_inventory_stock_movements_created_at ON inventory_stock_movements (created_at);""")
    op.execute("""CREATE INDEX ix_inventory_stock_movements_movement_type ON inventory_stock_movements (movement_type);""")
    op.execute("""CREATE INDEX ix_inventory_stock_movements_product_id ON inventory_stock_movements (product_id);""")
    op.execute("""CREATE INDEX ix_inventory_stock_movements_warehouse_id ON inventory_stock_movements (warehouse_id);""")
    op.execute("""CREATE TABLE ocr_results (
	document_id UUID NOT NULL,
	page_number INTEGER NOT NULL,
	provider VARCHAR(100) NOT NULL,
	language VARCHAR(20),
	raw_text TEXT NOT NULL,
	confidence_score NUMERIC(5, 2) NOT NULL,
	processing_time_ms INTEGER NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_ocr_results_document_id ON ocr_results (document_id);""")
    op.execute("""CREATE INDEX ix_ocr_results_page_number ON ocr_results (page_number);""")
    op.execute("""CREATE INDEX ix_ocr_results_provider ON ocr_results (provider);""")
    op.execute("""CREATE TABLE purchase_invoices (
	business_id UUID NOT NULL,
	supplier_id UUID NOT NULL,
	purchase_number VARCHAR(50) NOT NULL,
	invoice_number VARCHAR(50) NOT NULL,
	invoice_date DATE NOT NULL,
	due_date DATE,
	status purchase_status NOT NULL,
	subtotal NUMERIC(18, 2) NOT NULL,
	tax_amount NUMERIC(18, 2) NOT NULL,
	total_amount NUMERIC(18, 2) NOT NULL,
	notes TEXT,
	attachment_count INTEGER NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_purchase_invoices_business_purchase_number UNIQUE (business_id, purchase_number),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE,
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id) ON DELETE RESTRICT
);""")
    op.execute("""CREATE INDEX ix_purchase_invoices_business_id ON purchase_invoices (business_id);""")
    op.execute("""CREATE INDEX ix_purchase_invoices_invoice_date ON purchase_invoices (invoice_date);""")
    op.execute("""CREATE INDEX ix_purchase_invoices_purchase_number ON purchase_invoices (purchase_number);""")
    op.execute("""CREATE INDEX ix_purchase_invoices_status ON purchase_invoices (status);""")
    op.execute("""CREATE INDEX ix_purchase_invoices_supplier_id ON purchase_invoices (supplier_id);""")
    op.execute("""CREATE TABLE sales_invoices (
	business_id UUID NOT NULL,
	customer_id UUID NOT NULL,
	invoice_number VARCHAR(50) NOT NULL,
	invoice_date DATE NOT NULL,
	due_date DATE,
	status invoice_status NOT NULL,
	subtotal NUMERIC(18, 2) NOT NULL,
	discount_amount NUMERIC(18, 2) NOT NULL,
	taxable_amount NUMERIC(18, 2) NOT NULL,
	tax_amount NUMERIC(18, 2) NOT NULL,
	total_amount NUMERIC(18, 2) NOT NULL,
	round_off NUMERIC(18, 2) NOT NULL,
	currency VARCHAR(3),
	payment_terms_days INTEGER,
	notes TEXT,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_sales_invoices_business_invoice_number UNIQUE (business_id, invoice_number),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE,
	FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE RESTRICT
);""")
    op.execute("""CREATE INDEX ix_sales_invoices_business_id ON sales_invoices (business_id);""")
    op.execute("""CREATE INDEX ix_sales_invoices_customer_id ON sales_invoices (customer_id);""")
    op.execute("""CREATE INDEX ix_sales_invoices_invoice_date ON sales_invoices (invoice_date);""")
    op.execute("""CREATE INDEX ix_sales_invoices_invoice_number ON sales_invoices (invoice_number);""")
    op.execute("""CREATE INDEX ix_sales_invoices_status ON sales_invoices (status);""")
    op.execute("""CREATE TABLE account_balances (
	business_id UUID NOT NULL,
	account_id UUID NOT NULL,
	current_debit NUMERIC(18, 2) NOT NULL,
	current_credit NUMERIC(18, 2) NOT NULL,
	current_balance NUMERIC(18, 2) NOT NULL,
	last_posted_at TIMESTAMP WITH TIME ZONE,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_account_balances_account_id UNIQUE (account_id),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE,
	FOREIGN KEY(account_id) REFERENCES accounts (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_account_balances_account_id ON account_balances (account_id);""")
    op.execute("""CREATE INDEX ix_account_balances_business_id ON account_balances (business_id);""")
    op.execute("""CREATE TABLE expense_lines (
	expense_id UUID NOT NULL,
	description VARCHAR(255) NOT NULL,
	quantity NUMERIC(18, 2) NOT NULL,
	unit_cost NUMERIC(18, 2) NOT NULL,
	tax_rate NUMERIC(5, 2) NOT NULL,
	cgst_amount NUMERIC(18, 2) NOT NULL,
	sgst_amount NUMERIC(18, 2) NOT NULL,
	igst_amount NUMERIC(18, 2) NOT NULL,
	cess_amount NUMERIC(18, 2) NOT NULL,
	line_total NUMERIC(18, 2) NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(expense_id) REFERENCES expenses (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_expense_lines_expense_id ON expense_lines (expense_id);""")
    op.execute("""CREATE TABLE extracted_fields (
	extracted_document_id UUID NOT NULL,
	document_id UUID NOT NULL,
	field_name VARCHAR(100) NOT NULL,
	field_value TEXT NOT NULL,
	confidence NUMERIC(5, 2) NOT NULL,
	source extracted_field_source NOT NULL,
	page_number INTEGER NOT NULL,
	bounding_box JSON,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(extracted_document_id) REFERENCES extracted_documents (id) ON DELETE CASCADE,
	FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_extracted_fields_document_id ON extracted_fields (document_id);""")
    op.execute("""CREATE INDEX ix_extracted_fields_field_name ON extracted_fields (field_name);""")
    op.execute("""CREATE INDEX ix_extracted_fields_source ON extracted_fields (source);""")
    op.execute("""CREATE TABLE extraction_reviews (
	extracted_document_id UUID NOT NULL,
	reason VARCHAR(255) NOT NULL,
	notes TEXT,
	resolved BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(extracted_document_id) REFERENCES extracted_documents (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_extraction_reviews_extracted_document_id ON extraction_reviews (extracted_document_id);""")
    op.execute("""CREATE INDEX ix_extraction_reviews_resolved ON extraction_reviews (resolved);""")
    op.execute("""CREATE TABLE gst_einvoice_qr_codes (
	invoice_id UUID NOT NULL,
	qr_content TEXT NOT NULL,
	hash_value VARCHAR(128) NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(invoice_id) REFERENCES sales_invoices (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE UNIQUE INDEX ix_gst_einvoice_qr_codes_hash_value ON gst_einvoice_qr_codes (hash_value);""")
    op.execute("""CREATE UNIQUE INDEX ix_gst_einvoice_qr_codes_invoice_id ON gst_einvoice_qr_codes (invoice_id);""")
    op.execute("""CREATE TABLE gst_einvoices (
	business_id UUID NOT NULL,
	invoice_id UUID NOT NULL,
	irn VARCHAR(100) NOT NULL,
	ack_number VARCHAR(50) NOT NULL,
	ack_date TIMESTAMP WITH TIME ZONE NOT NULL,
	status e_invoice_status NOT NULL,
	provider_name VARCHAR(100) NOT NULL,
	request_payload JSON NOT NULL,
	response_payload JSON NOT NULL,
	cancel_reason TEXT,
	cancelled_at TIMESTAMP WITH TIME ZONE,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE,
	FOREIGN KEY(invoice_id) REFERENCES sales_invoices (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_gst_einvoices_business_id ON gst_einvoices (business_id);""")
    op.execute("""CREATE UNIQUE INDEX ix_gst_einvoices_invoice_id ON gst_einvoices (invoice_id);""")
    op.execute("""CREATE UNIQUE INDEX ix_gst_einvoices_irn ON gst_einvoices (irn);""")
    op.execute("""CREATE INDEX ix_gst_einvoices_status ON gst_einvoices (status);""")
    op.execute("""CREATE TABLE gst_eway_bills (
	invoice_id UUID NOT NULL,
	eway_bill_number VARCHAR(50) NOT NULL,
	valid_from TIMESTAMP WITH TIME ZONE NOT NULL,
	valid_to TIMESTAMP WITH TIME ZONE NOT NULL,
	vehicle_number VARCHAR(20),
	transport_mode eway_bill_transport_mode NOT NULL,
	status eway_bill_status NOT NULL,
	cancel_reason TEXT,
	cancelled_at TIMESTAMP WITH TIME ZONE,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(invoice_id) REFERENCES sales_invoices (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE UNIQUE INDEX ix_gst_eway_bills_invoice_id ON gst_eway_bills (invoice_id);""")
    op.execute("""CREATE UNIQUE INDEX ix_gst_eway_bills_number ON gst_eway_bills (eway_bill_number);""")
    op.execute("""CREATE INDEX ix_gst_eway_bills_status ON gst_eway_bills (status);""")
    op.execute("""CREATE TABLE journal_entry_lines (
	journal_entry_id UUID NOT NULL,
	account_id UUID NOT NULL,
	debit NUMERIC(18, 2) NOT NULL,
	credit NUMERIC(18, 2) NOT NULL,
	description VARCHAR(255),
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(journal_entry_id) REFERENCES journal_entries (id) ON DELETE CASCADE,
	FOREIGN KEY(account_id) REFERENCES accounts (id) ON DELETE RESTRICT
);""")
    op.execute("""CREATE INDEX ix_journal_entry_lines_account_id ON journal_entry_lines (account_id);""")
    op.execute("""CREATE INDEX ix_journal_entry_lines_journal_entry_id ON journal_entry_lines (journal_entry_id);""")
    op.execute("""CREATE TABLE payments (
	invoice_id UUID NOT NULL,
	payment_date DATE NOT NULL,
	amount NUMERIC(18, 2) NOT NULL,
	payment_method payment_method NOT NULL,
	reference_number VARCHAR(100),
	notes TEXT,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(invoice_id) REFERENCES sales_invoices (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_payments_invoice_id ON payments (invoice_id);""")
    op.execute("""CREATE INDEX ix_payments_payment_date ON payments (payment_date);""")
    op.execute("""CREATE INDEX ix_payments_payment_method ON payments (payment_method);""")
    op.execute("""CREATE TABLE purchase_invoice_lines (
	purchase_invoice_id UUID NOT NULL,
	description VARCHAR(255) NOT NULL,
	quantity NUMERIC(18, 2) NOT NULL,
	unit_cost NUMERIC(18, 2) NOT NULL,
	tax_rate NUMERIC(5, 2) NOT NULL,
	cgst_amount NUMERIC(18, 2) NOT NULL,
	sgst_amount NUMERIC(18, 2) NOT NULL,
	igst_amount NUMERIC(18, 2) NOT NULL,
	cess_amount NUMERIC(18, 2) NOT NULL,
	line_total NUMERIC(18, 2) NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(purchase_invoice_id) REFERENCES purchase_invoices (id) ON DELETE CASCADE
);""")
    op.execute("""CREATE INDEX ix_purchase_invoice_lines_purchase_invoice_id ON purchase_invoice_lines (purchase_invoice_id);""")
    op.execute("""CREATE TABLE sales_invoice_lines (
	invoice_id UUID NOT NULL,
	catalog_item_id UUID,
	description VARCHAR(255) NOT NULL,
	quantity NUMERIC(18, 2) NOT NULL,
	unit_price NUMERIC(18, 2) NOT NULL,
	discount NUMERIC(18, 2) NOT NULL,
	tax_rate NUMERIC(5, 2) NOT NULL,
	cgst_amount NUMERIC(18, 2) NOT NULL,
	sgst_amount NUMERIC(18, 2) NOT NULL,
	igst_amount NUMERIC(18, 2) NOT NULL,
	cess_amount NUMERIC(18, 2) NOT NULL,
	line_total NUMERIC(18, 2) NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(invoice_id) REFERENCES sales_invoices (id) ON DELETE CASCADE,
	FOREIGN KEY(catalog_item_id) REFERENCES catalog_items (id) ON DELETE RESTRICT
);""")
    op.execute("""CREATE INDEX ix_sales_invoice_lines_catalog_item_id ON sales_invoice_lines (catalog_item_id);""")
    op.execute("""CREATE INDEX ix_sales_invoice_lines_invoice_id ON sales_invoice_lines (invoice_id);""")
    op.execute("""CREATE TABLE general_ledger_entries (
	business_id UUID NOT NULL,
	journal_entry_id UUID NOT NULL,
	journal_line_id UUID NOT NULL,
	account_id UUID NOT NULL,
	transaction_date DATE NOT NULL,
	posting_date DATE NOT NULL,
	debit NUMERIC(18, 2) NOT NULL,
	credit NUMERIC(18, 2) NOT NULL,
	running_balance NUMERIC(18, 2),
	description VARCHAR(255),
	source_module VARCHAR(100),
	source_entity VARCHAR(100),
	source_entity_id UUID,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by UUID,
	updated_by UUID,
	is_deleted BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE RESTRICT,
	FOREIGN KEY(journal_entry_id) REFERENCES journal_entries (id) ON DELETE RESTRICT,
	FOREIGN KEY(journal_line_id) REFERENCES journal_entry_lines (id) ON DELETE RESTRICT,
	FOREIGN KEY(account_id) REFERENCES accounts (id) ON DELETE RESTRICT
);""")
    op.execute("""CREATE INDEX ix_general_ledger_entries_account_id ON general_ledger_entries (account_id);""")
    op.execute("""CREATE INDEX ix_general_ledger_entries_business_id ON general_ledger_entries (business_id);""")
    op.execute("""CREATE INDEX ix_general_ledger_entries_journal_entry_id ON general_ledger_entries (journal_entry_id);""")
    op.execute("""CREATE INDEX ix_general_ledger_entries_journal_line_id ON general_ledger_entries (journal_line_id);""")
    op.execute("""CREATE INDEX ix_general_ledger_entries_posting_date ON general_ledger_entries (posting_date);""")
    op.execute("""CREATE INDEX ix_general_ledger_entries_source ON general_ledger_entries (source_module, source_entity);""")
    op.execute("""CREATE INDEX ix_general_ledger_entries_transaction_date ON general_ledger_entries (transaction_date);""")


def downgrade() -> None:
    """Drop the complete RC1 schema baseline."""
    op.execute("""DROP TABLE general_ledger_entries;""")
    op.execute("""DROP TABLE sales_invoice_lines;""")
    op.execute("""DROP TABLE purchase_invoice_lines;""")
    op.execute("""DROP TABLE payments;""")
    op.execute("""DROP TABLE journal_entry_lines;""")
    op.execute("""DROP TABLE gst_eway_bills;""")
    op.execute("""DROP TABLE gst_einvoices;""")
    op.execute("""DROP TABLE gst_einvoice_qr_codes;""")
    op.execute("""DROP TABLE extraction_reviews;""")
    op.execute("""DROP TABLE extracted_fields;""")
    op.execute("""DROP TABLE expense_lines;""")
    op.execute("""DROP TABLE account_balances;""")
    op.execute("""DROP TABLE sales_invoices;""")
    op.execute("""DROP TABLE purchase_invoices;""")
    op.execute("""DROP TABLE ocr_results;""")
    op.execute("""DROP TABLE inventory_stock_movements;""")
    op.execute("""DROP TABLE inventory_stock_balances;""")
    op.execute("""DROP TABLE inventory_item_profiles;""")
    op.execute("""DROP TABLE gst_itc_reconciliations;""")
    op.execute("""DROP TABLE gst_gstr3b_summaries;""")
    op.execute("""DROP TABLE gst_gstr1_summaries;""")
    op.execute("""DROP TABLE extracted_documents;""")
    op.execute("""DROP TABLE expenses;""")
    op.execute("""DROP TABLE document_validation_issues;""")
    op.execute("""DROP TABLE document_reviews;""")
    op.execute("""DROP TABLE document_review_revisions;""")
    op.execute("""DROP TABLE document_review_decisions;""")
    op.execute("""DROP TABLE document_pages;""")
    op.execute("""DROP TABLE document_automation_runs;""")
    op.execute("""DROP TABLE accounts;""")
    op.execute("""DROP TABLE vendors;""")
    op.execute("""DROP TABLE suppliers;""")
    op.execute("""DROP TABLE sales_invoice_number_sequences;""")
    op.execute("""DROP TABLE journal_entries;""")
    op.execute("""DROP TABLE inventory_warehouses;""")
    op.execute("""DROP TABLE inventory_products;""")
    op.execute("""DROP TABLE identity_user_roles;""")
    op.execute("""DROP TABLE identity_role_permissions;""")
    op.execute("""DROP TABLE identity_refresh_tokens;""")
    op.execute("""DROP TABLE identity_password_resets;""")
    op.execute("""DROP TABLE identity_login_history;""")
    op.execute("""DROP TABLE identity_email_verifications;""")
    op.execute("""DROP TABLE identity_credentials;""")
    op.execute("""DROP TABLE gst_settings;""")
    op.execute("""DROP TABLE gst_sac_codes;""")
    op.execute("""DROP TABLE gst_return_periods;""")
    op.execute("""DROP TABLE gst_registrations;""")
    op.execute("""DROP TABLE gst_hsn_codes;""")
    op.execute("""DROP TABLE documents;""")
    op.execute("""DROP TABLE customers;""")
    op.execute("""DROP TABLE catalog_items;""")
    op.execute("""DROP TABLE business_tax_profiles;""")
    op.execute("""DROP TABLE business_settings;""")
    op.execute("""DROP TABLE business_memberships;""")
    op.execute("""DROP TABLE business_addresses;""")
    op.execute("""DROP TABLE account_types;""")
    op.execute("""DROP TABLE identity_users;""")
    op.execute("""DROP TABLE identity_roles;""")
    op.execute("""DROP TABLE identity_permissions;""")
    op.execute("""DROP TABLE gst_tax_rates;""")
    op.execute("""DROP TABLE gst_providers;""")
    op.execute("""DROP TABLE gst_audit_reports;""")
    op.execute("""DROP TABLE businesses;""")
    op.execute("""DROP TABLE account_categories;""")
    op.execute("""DROP TYPE payment_method;""")
    op.execute("""DROP TYPE eway_bill_status;""")
    op.execute("""DROP TYPE eway_bill_transport_mode;""")
    op.execute("""DROP TYPE e_invoice_status;""")
    op.execute("""DROP TYPE extracted_field_source;""")
    op.execute("""DROP TYPE invoice_status;""")
    op.execute("""DROP TYPE purchase_status;""")
    op.execute("""DROP TYPE inventory_movement_type;""")
    op.execute("""DROP TYPE document_extraction_run_status;""")
    op.execute("""DROP TYPE extracted_document_type;""")
    op.execute("""DROP TYPE expense_status;""")
    op.execute("""DROP TYPE expense_category;""")
    op.execute("""DROP TYPE document_validation_category;""")
    op.execute("""DROP TYPE document_validation_severity;""")
    op.execute("""DROP TYPE document_review_status;""")
    op.execute("""DROP TYPE document_review_decision_type;""")
    op.execute("""DROP TYPE document_automation_state;""")
    op.execute("""DROP TYPE document_automation_type;""")
    op.execute("""DROP TYPE journal_status;""")
    op.execute("""DROP TYPE gst_rounding_method;""")
    op.execute("""DROP TYPE gst_tax_mode;""")
    op.execute("""DROP TYPE gst_return_status;""")
    op.execute("""DROP TYPE gst_filing_frequency;""")
    op.execute("""DROP TYPE gst_registration_type;""")
    op.execute("""DROP TYPE document_extraction_status;""")
    op.execute("""DROP TYPE document_type;""")
    op.execute("""DROP TYPE identity_user_status;""")
    op.execute("""DROP TYPE gst_provider_type;""")
    op.execute("""DROP TYPE business_status;""")
    op.execute("""DROP TYPE business_registration_status;""")
    op.execute("""DROP TYPE business_type;""")
