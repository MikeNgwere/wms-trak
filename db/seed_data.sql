-- =========================================================
-- Seed data: roles, ports, bond rules, permissions
-- =========================================================

INSERT INTO roles (role_name) VALUES
('Agent'), ('Officer'), ('Supervisor'), ('Manager');

INSERT INTO ports (port_code, port_name, region) VALUES
('ZWFB', 'Forbes',      'Mutare'),
('ZWCH', 'Chirundu',    'Mashonaland West'),
('ZWBB', 'Beitbridge',  'Matabeleland South');

-- Bond / transit periods, verified against the Customs and Excise Act [Chapter 23:02],
-- the Customs and Excise (General) Regulations (S.I. 154/2001), and ZIMRA CEP procedures.
-- See docs/LEGAL_FRAMEWORK.md for full citations and explanatory notes.
INSERT INTO bond_rules (entry_type, load_condition, allowed_days, legal_reference, description) VALUES
('RIT', 'transit_shed',      10, 'C&E Act s.39(1)(b); CEP0114',                       'Goods removed to a transit shed must be entered within 10 days of importation, else treated as abandoned'),
('RIT', 'normal',             3, 'C&E General Regs s.60(1)(e); CEP0114',              'Normal-load goods in transit must be re-exported within 3 days of entry/removal'),
('RIT', 'abnormal',           5, 'C&E General Regs s.60(1)(e)',                        'Abnormal-load goods in transit must be re-exported within 5 days of entry/removal'),
('RIB', 'rewarehousing',      3, 'C&E General Regs s.76(4)',                           'Goods removed in bond port-to-port must be entered for re-warehousing/consumption within 3 days of arrival at the receiving port'),
('RIB', 'acquittal',         10, 'C&E General Regs s.27(2)(b) proviso',                'An RIB entry becomes "outstanding" (flagged, fines apply) if not acquitted with proof of arrival within 10 days'),
('RIB', 'export_in_bond',    10, 'CEP0024',                                            'Goods entered for Export in Bond must be exported within 10 days of release'),
('RIH',  NULL,                60, 'C&E Act s.39(2); CEP0114',                          'Goods in State Warehouse (RIH) must be entered/duty paid within 60 days, else disposed of by Rummage Sale/auction. NOTE: this period was reduced from 3 months to 60 days by the Finance (No.3) Act 10 of 2009, w.e.f. 8 Jan 2010 — flag this for your literature review, as 3 months is commonly (and incorrectly) still cited operationally.'),
('BONDED_WHS', NULL,          730, 'C&E Act s.76; CEP0038 s.7.10',                      'Maximum period goods may remain in a private bonded warehouse is 2 years (730 days) before compulsory export/consumption entry');

-- Additional non-day-count rules to encode as business logic (not bond_rules rows):
--   * NOS/seizure appeal window: 3 months from notice of seizure (C&E Act s.193(12)) —
--     after this, if no proceedings instituted, goods vest for forfeiture/disposal (s.193(13)).
--   * Public auction of forfeited/unentered goods requires at least 1 month's Gazette notice
--     before the sale date (C&E Act s.39(3)).

-- Baseline permission matrix (extend as workflows are built out)
INSERT INTO permissions (role_id, action)
SELECT role_id, action FROM roles, (VALUES
    ('create_entry'), ('upload_nos_rih_book'), ('view_own_entries')
) AS a(action) WHERE role_name = 'Agent';

INSERT INTO permissions (role_id, action)
SELECT role_id, action FROM roles, (VALUES
    ('process_entry'), ('update_status'), ('record_payment'),
    ('record_transit_movement'), ('view_port_entries')
) AS a(action) WHERE role_name = 'Officer';

INSERT INTO permissions (role_id, action)
SELECT role_id, action FROM roles, (VALUES
    ('view_flagged_entries'), ('escalate_to_manager'),
    ('view_port_dashboard'), ('view_port_entries')
) AS a(action) WHERE role_name = 'Supervisor';

INSERT INTO permissions (role_id, action)
SELECT role_id, action FROM roles, (VALUES
    ('approve_disposal'), ('view_all_ports'), ('view_all_dashboard'),
    ('approve_forfeiture')
) AS a(action) WHERE role_name = 'Manager';