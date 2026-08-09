-- Nimbus Retail Analytics Pvt Ltd -- fictional internal company database.
-- Nothing here exists on the public internet, so a base LLM cannot know any of it.
-- That is the point: it forces the model to either say "I don't know" or hallucinate.

DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS quarterly_revenue;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS policies;

CREATE TABLE employees (
    emp_id      TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL,
    department  TEXT NOT NULL,
    location    TEXT NOT NULL,
    joined_on   TEXT NOT NULL,
    manager     TEXT
);

INSERT INTO employees VALUES
('NRA-1041','Priya Venkatesan','VP of Engineering','Engineering','Bengaluru','2019-03-11',NULL),
('NRA-1067','Marcus Ohene','Principal Data Engineer','Engineering','Manchester','2020-07-06','Priya Venkatesan'),
('NRA-1088','Sofia Marchetti','Engineering Manager','Engineering','Milan','2021-01-18','Priya Venkatesan'),
('NRA-1102','Daniel Kirchner','Staff Backend Engineer','Engineering','Berlin','2021-09-27','Sofia Marchetti'),
('NRA-1119','Aisha Rahman','Senior ML Engineer','Data Science','Kuala Lumpur','2022-02-14','Marcus Ohene'),
('NRA-1134','Tomas Lindqvist','Head of Finance','Finance','Stockholm','2018-11-05',NULL),
('NRA-1150','Renuka Iyer','Financial Analyst','Finance','Chennai','2022-06-20','Tomas Lindqvist'),
('NRA-1163','Grace Abbot','Director of Sales, APAC','Sales','Singapore','2020-04-13','NULL'),
('NRA-1177','Kenji Watanabe','Enterprise Account Executive','Sales','Osaka','2023-01-09','Grace Abbot'),
('NRA-1189','Olusegun Bello','Support Team Lead','Customer Success','Lagos','2021-11-22',NULL),
('NRA-1204','Hana Novak','Product Manager','Product','Prague','2022-08-01','Priya Venkatesan'),
('NRA-1218','Ravi Deshmukh','Site Reliability Engineer','Engineering','Pune','2023-05-15','Sofia Marchetti');

CREATE TABLE products (
    sku          TEXT PRIMARY KEY,
    product_line TEXT NOT NULL,
    tier         TEXT NOT NULL,
    launched_on  TEXT NOT NULL,
    list_price_usd REAL NOT NULL
);

INSERT INTO products VALUES
('NBS-SHELF-01','ShelfSense','Standard','2020-02-17',18400.0),
('NBS-SHELF-02','ShelfSense','Enterprise','2021-06-08',47250.0),
('NBS-FLOW-01','FlowCast','Standard','2021-10-04',22900.0),
('NBS-FLOW-02','FlowCast','Enterprise','2022-03-21',61500.0),
('NBS-PULSE-01','PulseGrid','Standard','2023-04-11',31750.0),
('NBS-ATLAS-01','AtlasLink','Enterprise','2024-01-30',88000.0);

CREATE TABLE quarterly_revenue (
    fiscal_quarter TEXT NOT NULL,
    region         TEXT NOT NULL,
    product_line   TEXT NOT NULL,
    revenue_usd    REAL NOT NULL,
    deals_closed   INTEGER NOT NULL
);

INSERT INTO quarterly_revenue VALUES
('FY2024-Q3','APAC','ShelfSense', 1842000.0, 31),
('FY2024-Q3','APAC','FlowCast',   2967500.0, 24),
('FY2024-Q3','APAC','PulseGrid',   734200.0,  9),
('FY2024-Q3','APAC','AtlasLink',  1120000.0,  5),
('FY2024-Q3','EMEA','ShelfSense', 2410000.0, 38),
('FY2024-Q3','EMEA','FlowCast',   1385000.0, 14),
('FY2024-Q3','EMEA','PulseGrid',   902750.0, 11),
('FY2024-Q3','AMER','ShelfSense', 3120000.0, 44),
('FY2024-Q3','AMER','FlowCast',   2044000.0, 19),
('FY2024-Q3','AMER','AtlasLink',  2640000.0, 12),
('FY2024-Q4','APAC','ShelfSense', 2015000.0, 34),
('FY2024-Q4','APAC','FlowCast',   3180000.0, 27),
('FY2024-Q4','APAC','AtlasLink',  1584000.0,  7),
('FY2024-Q4','EMEA','ShelfSense', 2288000.0, 35),
('FY2024-Q4','EMEA','FlowCast',   1712500.0, 17),
('FY2024-Q4','AMER','ShelfSense', 3455000.0, 47);

CREATE TABLE projects (
    project_code TEXT PRIMARY KEY,
    project_name TEXT NOT NULL,
    lead         TEXT NOT NULL,
    status       TEXT NOT NULL,
    engineers    INTEGER NOT NULL,
    target_date  TEXT NOT NULL,
    budget_usd   REAL NOT NULL
);

INSERT INTO projects VALUES
('PRJ-207','Atlas Migration','Sofia Marchetti','In Progress',9,'2025-04-30',1250000.0),
('PRJ-211','Realtime Ingest Rewrite','Marcus Ohene','In Progress',6,'2025-02-28',680000.0),
('PRJ-198','Forecast Model v3','Aisha Rahman','Completed',4,'2024-09-15',415000.0),
('PRJ-223','APAC Data Residency','Ravi Deshmukh','Blocked',3,'2025-07-31',290000.0),
('PRJ-230','Billing Consolidation','Hana Novak','Planning',5,'2025-09-30',540000.0);

CREATE TABLE policies (
    policy_id  TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL
);

INSERT INTO policies VALUES
('POL-014','Enterprise Support SLA',
 'Enterprise tier customers receive a first-response SLA of 30 minutes for Severity-1 incidents and 4 business hours for Severity-2. Standard tier customers receive 8 business hours for Severity-1. Severity-1 is defined as a complete production outage affecting more than 50 percent of a customer store fleet.'),
('POL-021','Refund and Credit Policy',
 'Refunds are issued only within 45 days of invoice date. Beyond 45 days, customers receive service credits capped at 15 percent of the annual contract value. All refunds above 25000 USD require written approval from the Head of Finance, currently Tomas Lindqvist.'),
('POL-033','Data Retention Policy',
 'Raw shelf-scan telemetry is retained for 18 months in hot storage and a further 5 years in cold archive. Personally identifiable information captured in store footage is purged after 90 days without exception. APAC customer data must remain in the ap-south-1 region under project PRJ-223.'),
('POL-040','Remote Work Policy',
 'Employees may work remotely up to 12 days per calendar month. Engineering staff on projects with a Blocked status are required to attend the Pune or Bengaluru office at least twice weekly until the block is cleared.'),
('POL-052','Procurement Approval Thresholds',
 'Purchases under 10000 USD require manager approval only. Purchases between 10000 and 100000 USD require Head of Finance approval. Purchases above 100000 USD require both Head of Finance and VP of Engineering sign-off, currently Tomas Lindqvist and Priya Venkatesan respectively.');
