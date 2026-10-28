"""Generate the synthetic world behind the 40 eval cases. Prototype.

Code makes every record and every number (accounts, contacts, opportunities, leads,
usage rows, ARR, seats, dates). An LLM writes only transcript prose, and each transcript
must contain the sentences `data/answer_key/planted_facts.json` plants in it, word for word.

The hand-written L-001 records are kept as they are. Transcripts already on disk are kept
when their header matches and they still pass validation, so a rerun calls the API only for
missing or changed transcripts.

Usage: python scripts/generate_data.py [--offline] [--force-transcripts]
"""

import argparse
import json
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import anthropic

from lead_brief import config

CRM = config.DATA_DIR / "crm"
USAGE = config.DATA_DIR / "usage"
TRANSCRIPTS = config.DATA_DIR / "transcripts"
PLANTED_PATH = config.DATA_DIR / "answer_key" / "planted_facts.json"

# Records written by hand for L-001 (tasks/01-first-end-to-end.md). Never regenerated.
HAND_WRITTEN = {
    "ACC-001", "ACC-002", "ACC-003", "CON-010", "CON-011", "CON-020", "OPP-004", "L-001",
    "T-0001", "T-0002", "T-0003", "T-0004",
}

WEEK_ENDINGS = [date(2026, 7, 19) + timedelta(weeks=i) for i in range(12)]

# ---- The world ----
# Accounts: id, name, name_variants, parent, domain, industry, is_customer, owner, arr_usd, seats, renewal
ACCOUNTS = [
    # Net new look-alikes
    ("ACC-004", "Brannock Orthodontics", ["Brannock Ortho"], None, "brannockortho.example", "Orthodontic practice group", True, "Tess Harlow", 18000, 30, "2027-02-15"),
    ("ACC-005", "Corvane Hospitality Group", ["Corvane Hotels"], None, "corvanehotels.example", "Hotels", False, "Owen Castellano", None, None, None),
    ("ACC-006", "Strand & Mercer Legal", ["Strand Mercer"], None, "strandmercer.example", "Law firm", True, "Abel Okafor", 30000, 45, "2027-05-01"),
    ("ACC-007", "Marlowe Ridge Winery", ["Marlowe Ridge", "MRW"], None, "marloweridgewine.example", "Winery", True, "Sofia Brandt", 22000, 35, "2026-12-01"),
    ("ACC-008", "Halvard Financial Group", ["Halvard"], None, "halvardfg.example", "Banking", False, None, None, None, None),
    ("ACC-009", "Halvard Bank (Retail Banking)", ["Halvard Retail"], "ACC-008", "halvardfg.example", "Banking", True, "Nikhil Varma", 140000, 200, "2027-06-30"),
    # Healthy departments
    ("ACC-010", "Ostrander Mills Inc.", ["Ostrander Mills", "Ostrander"], None, "ostrandermills.example", "Paper and packaging", False, None, None, None, None),
    ("ACC-011", "Ostrander Mills (Finance)", ["Ostrander Finance"], "ACC-010", "ostrandermills.example", "Paper and packaging", True, "Priya Nandakumar", 64000, 90, "2027-04-15"),
    ("ACC-012", "Ferncliff Bioscience Holdings", ["Ferncliff Bioscience", "Ferncliff"], None, "ferncliff.example", "Biotechnology", False, None, None, None, None),
    ("ACC-013", "Ferncliff Labs", ["Ferncliff Laboratories"], "ACC-012", "ferncliff.example", "Biotechnology", False, None, None, None, None),
    ("ACC-014", "Ferncliff Bioscience (Clinical Operations)", ["Ferncliff Clinical Ops"], "ACC-012", "ferncliff.example", "Biotechnology", True, "Mei Lindqvist", 98000, 150, "2027-01-31"),
    ("ACC-015", "Orrin Aerospace Corporation", ["Orrin Aerospace", "Orrin Aero"], None, "orrinaero.example", "Aerospace manufacturing", False, None, None, None, None),
    ("ACC-016", "Orrin Aerospace (Manufacturing Engineering)", ["Orrin Mfg Engineering"], "ACC-015", "orrinaero.example", "Aerospace manufacturing", True, "Lucas Moretti", 120000, 160, "2027-03-20"),
    ("ACC-017", "Orrin Pet Supply", ["Orrin Pets"], None, "orrinpets.example", "Pet supply retail", True, "Tess Harlow", 15000, 25, "2026-11-05"),
    ("ACC-018", "Kestrel Transit Corporation", ["Kestrel Transit", "KTC"], None, "kestreltransit.example", "Public transit", False, None, None, None, None),
    ("ACC-019", "Kestrel Transit (Fleet Maintenance)", ["KTC Fleet"], "ACC-018", "kestreltransit.example", "Public transit", True, "Jordan Pike", 52000, 70, "2027-02-28"),
    ("ACC-020", "Glenhollow Insurance Group", ["Glenhollow Insurance", "Glenhollow"], None, "glenhollow.example", "Insurance", False, None, None, None, None),
    ("ACC-021", "Glenhollow Insurance (Claims)", ["Glenhollow Claims"], "ACC-020", "glenhollow.example", "Insurance", True, "Grace Adeyemi", 110000, 140, "2027-07-31"),
    ("ACC-022", "Juniper and Vale Outfitters", ["Juniper and Vale", "J&V Outfitters"], None, "junipervale.example", "Outdoor retail", False, None, None, None, None),
    ("ACC-023", "Juniper and Vale (Retail Stores)", ["J&V Retail"], "ACC-022", "junipervale.example", "Outdoor retail", True, "Kendall Ross", 47000, 60, "2027-05-15"),
    ("ACC-024", "Tamsworth University", ["Tamsworth"], None, "tamsworth.example", "Higher education", False, None, None, None, None),
    ("ACC-025", "Tamsworth University (Admissions)", ["Tamsworth Admissions"], "ACC-024", "tamsworth.example", "Higher education", True, "Abel Okafor", 38000, 55, "2027-08-31"),
    ("ACC-026", "Tamsworth University (Advancement)", ["Tamsworth Advancement"], "ACC-024", "tamsworth.example", "Higher education", True, "Abel Okafor", 29000, 40, "2027-08-31"),
    ("ACC-027", "Cobaltline Software Inc.", ["Cobaltline Software", "Cobaltline"], None, "cobaltline.example", "Software", False, None, None, None, None),
    ("ACC-028", "Cobaltline Software (Customer Success)", ["Cobaltline CS"], "ACC-027", "cobaltline.example", "Software", True, "Riley Chen", 58000, 80, "2027-01-15"),
    ("ACC-029", "Cobaltline Plumbing Supply", ["Cobaltline Plumbing"], None, "cobaltlineplumbing.example", "Plumbing wholesale", False, "Owen Castellano", None, None, None),
    # At-risk departments
    ("ACC-030", "Bramblecote Foods plc", ["Bramblecote Foods", "Bramblecote"], None, "bramblecote.example", "Packaged foods", False, None, None, None, None),
    ("ACC-031", "Bramblecote Foods (Category Management)", ["Bramblecote Category"], "ACC-030", "bramblecote.example", "Packaged foods", True, "Sofia Brandt", 76000, 100, "2026-11-30"),
    ("ACC-032", "Bramblecote Veterinary Clinics", ["Bramblecote Vets"], None, "bramblecotevets.example", "Veterinary clinics", True, "Priya Nandakumar", 21000, 30, "2027-04-01"),
    ("ACC-033", "Northgate Health System", ["Northgate Health", "NGHS"], None, "northgatehs.example", "Hospital system", False, None, None, None, None),
    ("ACC-034", "Northgate Health System (Population Health)", ["NGHS Population Health"], "ACC-033", "northgatehs.example", "Hospital system", True, "Nikhil Varma", 132000, 180, "2026-12-15"),
    ("ACC-035", "Arvelle Group", ["Arvelle"], None, "arvelle.example", "Chemicals", False, None, None, None, None),
    ("ACC-036", "Arvelle Chemicals", ["Arvelle Chem"], "ACC-035", "arvelle.example", "Chemicals", False, None, None, None, None),
    ("ACC-037", "Arvelle Chemicals (Procurement)", ["Arvelle Procurement"], "ACC-036", "arvelle.example", "Chemicals", True, "Lucas Moretti", 54000, 75, "2026-11-12"),
    ("ACC-038", "Wexmoor Telecom", ["Wexmoor"], None, "wexmoor.example", "Telecommunications", False, None, None, None, None),
    ("ACC-039", "Wexmoor Telecom (Network Planning)", ["Wexmoor Network Planning"], "ACC-038", "wexmoor.example", "Telecommunications", True, "Grace Adeyemi", 90000, 110, "2026-12-01"),
    ("ACC-040", "Vantris Health Partners", ["Vantris Health", "Vantris"], None, "vantrishealth.example", "Physician groups", False, None, None, None, None),
    ("ACC-041", "Clarion Billing", ["Clarion Billing Services, a Vantris Health company"], "ACC-040", "clarionbilling.example", "Medical billing", False, None, None, None, None),
    ("ACC-042", "Vantris Health Partners (Revenue Cycle)", ["Vantris Revenue Cycle"], "ACC-040", "vantrishealth.example", "Physician groups", True, "Kendall Ross", 104000, 130, "2026-11-25"),
    # Closed-lost history
    ("ACC-043", "Pemberton Hardware Co.", ["Pemberton Hardware", "Pemberton"], None, "pembertonhw.example", "Hardware retail", False, "Owen Castellano", None, None, None),
    ("ACC-044", "Silverbrook Mutual Insurance", ["Silverbrook Mutual", "SMI"], None, "silverbrookmutual.example", "Insurance", False, "Jordan Pike", None, None, None),
    ("ACC-045", "Duskfield Energy", ["Duskfield"], None, "duskfield.example", "Energy utility", False, "Sofia Brandt", None, None, None),
    ("ACC-046", "Fenwick Retail Group", ["Fenwick Retail", "Fenwick"], None, "fenwickretail.example", "Home goods retail", False, "Abel Okafor", None, None, None),
    ("ACC-047", "Fenwick Home Outlet", ["Fenwick Home"], "ACC-046", "fenwickretail.example", "Home goods retail", False, None, None, None, None),
    ("ACC-048", "Graywater Shipping Lines", ["Graywater Shipping"], None, "graywatership.example", "Ocean shipping", False, "Jordan Pike", None, None, None),
    ("ACC-049", "Graywater Brewing Company", ["Graywater Brewing"], None, "graywaterbrewing.example", "Brewery", True, "Tess Harlow", 16000, 25, "2027-02-01"),
    ("ACC-050", "Kinsale Robotics", ["Kinsale"], None, "kinsalerobotics.example", "Industrial robotics", False, "Mei Lindqvist", None, None, None),
    # Job changers' former employers
    ("ACC-051", "Penhallow Outdoor Gear", ["Penhallow Outdoor", "Penhallow"], None, "penhallow.example", "Outdoor equipment", True, "Riley Chen", 44000, 60, "2027-03-31"),
    ("ACC-052", "Lockridge Staffing", ["Lockridge"], None, "lockridgestaffing.example", "Staffing", True, "Grace Adeyemi", 36000, 50, "2027-06-15"),
    ("ACC-053", "Tillery Department Stores", ["Tillery"], None, "tillery.example", "Department stores", True, "Kendall Ross", 88000, 120, "2027-02-20"),
    ("ACC-054", "Ashby Lane Dental Partners", ["Ashby Lane Dental"], None, "ashbylanedental.example", "Dental practice group", True, "Nikhil Varma", 19000, 28, "2026-11-18"),
    ("ACC-055", "Corrigan Freightways", ["Corrigan"], None, "corriganfreight.example", "Trucking", True, "Lucas Moretti", 70000, 95, "2027-05-31"),
    ("ACC-056", "Mossgiel Group", ["Mossgiel"], None, "mossgiel.example", "Wholesale distribution", False, None, None, None, None),
    ("ACC-057", "Mossgiel Group (Distribution)", ["Mossgiel Distribution"], "ACC-056", "mossgiel.example", "Wholesale distribution", True, "Priya Nandakumar", 61000, 85, "2027-04-30"),
    ("ACC-058", "Halstead Water Utility", ["Halstead Water"], None, "halsteadwater.example", "Water utility", True, "Sofia Brandt", 57000, 75, "2027-01-31"),
    ("ACC-059", "Rosslyn Dental Labs", ["Rosslyn Dental"], None, "rosslyndental.example", "Dental laboratory", True, "Tess Harlow", 12000, 18, "2027-03-15"),
    # Conflicts
    ("ACC-060", "Redfern Construction Ltd", ["Redfern Construction", "Redfern"], None, "redfernbuild.example", "Construction", False, "Jordan Pike", None, None, None),
    ("ACC-061", "Thistlecombe Hospitality", ["Thistlecombe"], None, "thistlecombe.example", "Hotels and resorts", False, "Mei Lindqvist", None, None, None),
    ("ACC-062", "Thistlecombe Hotels", ["Thistlecombe Hotel Group"], "ACC-061", "thistlecombe.example", "Hotels and resorts", False, None, None, None, None),
    ("ACC-063", "Thistlecombe Resorts", ["Thistlecombe Resort Collection"], "ACC-061", "thistlecombe.example", "Hotels and resorts", False, "Mei Lindqvist", None, None, None),
    ("ACC-064", "Stonemere Insurance Brokers", ["Stonemere Brokers"], None, "stonemerebrokers.example", "Insurance brokerage", False, "Owen Castellano", None, None, None),
    ("ACC-065", "Stonemere Garden Centers", ["Stonemere Gardens"], None, "stonemeregardens.example", "Garden retail", True, "Abel Okafor", 14000, 20, "2027-04-10"),
    ("ACC-066", "Everhart Credit Union", ["Everhart CU", "ECU"], None, "everhartcu.example", "Credit union", False, "Lucas Moretti", None, None, None),
    ("ACC-067", "Corbel Architecture Partners", ["Corbel Architecture", "Corbel"], None, "corbelarch.example", "Architecture", False, "Grace Adeyemi", None, None, None),
    ("ACC-068", "Alderton Provisions", ["Alderton Foods", "Alderton"], None, "alderton.example", "Food distribution", False, "Kendall Ross", None, None, None),
]

# Customer accounts whose usage slides from green to red. Every other customer is healthy.
DECLINING = {"ACC-007", "ACC-017", "ACC-031", "ACC-034", "ACC-037", "ACC-039", "ACC-042", "ACC-054"}

# Contacts: id, account, name, title, role_tags, last_updated, start, end, email_domain (None: the account's)
CONTACTS = [
    ("CON-030", "ACC-004", "Paloma Reyes", "Practice Manager", ["champion"], "2026-08-25", "2020-03-02", None, None),
    ("CON-031", "ACC-005", "Beatrix Holm", "Director of Revenue Management", ["champion"], "2026-04-10", "2019-06-01", None, None),
    ("CON-032", "ACC-006", "Harriet Osei", "Paralegal Operations Lead", ["champion"], "2026-09-29", "2019-01-14", None, None),
    ("CON-033", "ACC-006", "Victor Lam", "Managing Partner", ["economic_buyer"], "2026-03-02", "2012-09-01", None, None),
    ("CON-034", "ACC-007", "Odile Fournier", "General Manager", ["champion", "economic_buyer"], "2026-09-21", "2018-04-01", None, None),
    ("CON-035", "ACC-009", "Celia Okonkwo", "SVP Retail Analytics", ["champion"], "2026-08-12", "2017-11-06", None, None),
    ("CON-036", "ACC-011", "Gideon Barlow", "VP Finance", ["champion"], "2026-09-16", "2020-02-03", None, None),
    ("CON-037", "ACC-011", "Lucia Ferrante", "CFO", ["economic_buyer"], "2026-07-08", "2018-05-14", None, None),
    ("CON-038", "ACC-014", "Anika Rao", "Director of Clinical Data", ["champion"], "2026-09-09", "2021-01-11", None, None),
    ("CON-039", "ACC-014", "Paul Merriman", "COO", ["economic_buyer"], "2026-06-24", "2016-08-01", None, None),
    ("CON-040", "ACC-016", "Trevor Nakamura", "Director of Manufacturing Engineering", ["champion"], "2026-09-22", "2019-10-07", None, None),
    ("CON-041", "ACC-017", "Becca Lowry", "Ecommerce Manager", ["champion"], "2026-09-15", "2021-04-19", None, None),
    ("CON-042", "ACC-019", "Hamid Farouk", "Fleet Maintenance Director", ["champion"], "2026-09-08", "2015-03-02", None, None),
    ("CON-043", "ACC-021", "Isaac Mendel", "VP Claims Operations", ["champion"], "2026-09-28", "2018-07-16", None, None),
    ("CON-044", "ACC-023", "Farah Siddiqui", "Director of Retail Analytics", ["champion"], "2026-09-17", "2020-09-08", None, None),
    ("CON-045", "ACC-025", "Jonah Whitcombe", "Director of Admissions Analytics", ["champion"], "2026-09-14", "2019-07-01", None, None),
    ("CON-046", "ACC-026", "Priyanka Sethi", "Advancement Data Manager", ["champion"], "2026-09-24", "2021-02-15", None, None),
    ("CON-047", "ACC-028", "Yvette Laurent", "VP Customer Success", ["champion"], "2026-09-29", "2020-11-02", None, None),
    ("CON-048", "ACC-029", "Dale Hutchins", "Owner", ["economic_buyer"], "2026-02-20", "2004-01-05", None, None),
    ("CON-049", "ACC-031", "Naomi Kerr", "Head of Category Insights", ["champion"], "2026-04-02", "2020-06-01", None, None),
    ("CON-050", "ACC-031", "Ralph Dunmore", "Commercial Director", ["economic_buyer"], "2026-04-02", "2016-02-15", None, None),
    ("CON-051", "ACC-032", "Hugo Strand", "Clinic Operations Manager", ["champion"], "2026-08-19", "2019-05-20", None, None),
    ("CON-052", "ACC-034", "Simone Achterberg", "Director of Population Health Analytics", ["champion"], "2026-06-10", "2018-09-04", None, None),
    ("CON-053", "ACC-034", "Gareth Pollard", "CFO", ["economic_buyer"], "2026-06-10", "2017-01-09", None, None),
    ("CON-054", "ACC-037", "Henrietta Vos", "Procurement Analytics Lead", ["champion"], "2026-05-01", "2020-04-13", None, None),
    ("CON-055", "ACC-037", "Anders Kjeldsen", "VP Procurement", ["economic_buyer"], "2026-05-01", "2015-10-01", None, None),
    ("CON-056", "ACC-039", "Rupert Glass", "Director of Network Planning", ["champion"], "2026-03-10", "2017-06-12", None, None),
    ("CON-057", "ACC-039", "Leona Fitz", "CTO", ["economic_buyer"], "2026-03-10", "2019-01-07", None, None),
    ("CON-058", "ACC-039", "Mina Osterberg", "Network Planning Manager", ["user"], "2026-09-29", "2021-08-02", None, None),
    ("CON-059", "ACC-042", "Delphine Arceneaux", "VP Revenue Cycle", ["champion"], "2026-05-20", "2019-03-18", None, None),
    ("CON-060", "ACC-042", "Stuart Ingram", "CFO", ["economic_buyer"], "2026-05-20", "2016-11-01", None, None),
    ("CON-061", "ACC-042", "Kofi Mensah", "Revenue Cycle Analyst", ["user"], "2026-09-23", "2022-05-09", None, None),
    ("CON-062", "ACC-043", "Leon Fairbanks", "VP Merchandising", ["champion"], "2026-05-29", "2014-02-03", None, None),
    ("CON-063", "ACC-043", "Ida Marchetti", "CFO", ["economic_buyer"], "2026-05-29", "2018-08-20", None, None),
    ("CON-064", "ACC-044", "Valerie Strout", "Head of Actuarial Analytics", ["champion"], "2026-06-30", "2017-04-03", None, None),
    ("CON-065", "ACC-044", "Bernard Oduya", "CISO", ["technical_evaluator"], "2026-06-30", "2020-01-13", None, None),
    ("CON-066", "ACC-045", "Rosalind Thorne", "Analytics Manager", ["champion"], "2026-03-18", "2019-09-09", None, None),
    ("CON-067", "ACC-045", "Emeka Obi", "VP Operations", ["economic_buyer"], "2026-03-18", "2013-05-06", None, None),
    ("CON-068", "ACC-046", "Yolanda Pierce", "SVP Finance", ["economic_buyer"], "2026-07-22", "2016-03-14", None, None),
    ("CON-069", "ACC-048", "Bram Hoekstra", "Fleet Planning Director", ["champion"], "2026-08-14", "2015-08-24", None, None),
    ("CON-070", "ACC-049", "Shay Mulgrew", "Taproom Operations Manager", ["champion"], "2026-09-02", "2020-05-01", None, None),
    ("CON-071", "ACC-050", "Ngozi Eze", "Director of Business Intelligence", ["champion"], "2026-05-14", "2022-02-07", None, None),
    ("CON-072", "ACC-050", "Tilde Sorensen", "COO", ["economic_buyer"], "2026-06-05", "2019-03-04", None, None),
    ("CON-073", "ACC-051", "Celeste Moravec", "Director of Analytics", ["champion"], "2026-08-04", "2021-03-01", "2026-07-31", None),
    ("CON-074", "ACC-051", "Wes Calloway", "CFO", ["economic_buyer"], "2026-09-10", "2018-10-15", None, None),
    ("CON-075", "ACC-052", "Dmitri Hale", "Senior Manager, Sales Operations", ["champion"], "2026-06-03", "2022-01-10", None, None),
    ("CON-076", "ACC-053", "Lorna Fitzgerald", "Merchandising Analytics Manager", ["champion"], "2026-07-08", "2020-05-04", "2026-07-03", None),
    ("CON-077", "ACC-054", "Gemma Okoro", "Office Manager", ["champion"], "2026-09-16", "2019-02-11", None, None),
    ("CON-078", "ACC-055", "Katherine Moreau", "Finance Systems Manager", ["champion"], "2026-06-11", "2019-09-01", None, None),
    ("CON-079", "ACC-057", "Samir Qureshi", "Distribution Planning Manager", ["champion"], "2026-05-27", "2021-06-01", None, None),
    ("CON-080", "ACC-058", "Daniel Ferreira", "Data Platform Lead", ["champion"], "2026-05-20", "2020-02-03", None, None),
    ("CON-081", "ACC-058", "Priti Banerjee", "Senior Data Engineer", ["user"], "2026-09-02", "2021-07-19", None, None),
    ("CON-082", "ACC-059", "Daniel Ferreira", "Lab Technician Supervisor", ["champion"], "2026-09-30", "2017-04-10", None, None),
    ("CON-083", "ACC-060", "Moira Castell", "VP Project Controls", ["champion"], "2026-09-22", "2016-06-06", None, None),
    ("CON-084", "ACC-063", "Inez Calder", "Resorts Revenue Director", ["champion"], "2026-10-01", "2020-01-20", None, None),
    ("CON-085", "ACC-064", "Felicity Barrow", "COO", ["champion", "economic_buyer"], "2026-09-25", "2018-03-12", None, None),
    ("CON-086", "ACC-065", "Rowan Tate", "Store Operations Manager", ["champion"], "2026-08-27", "2021-03-08", None, None),
    ("CON-087", "ACC-066", "Noemi Brandvold", "Director of Customer Analytics", ["champion"], "2026-09-25", "2019-11-04", None, None),
    ("CON-088", "ACC-067", "Pavel Novak", "Data Analyst", [], "2024-09-12", "2022-08-01", None, None),
    ("CON-089", "ACC-068", "Wilhelmina Royce", "Operations Manager", [], "2024-06-20", "2018-04-09", None, "aldertonfoods.example"),
    ("CON-090", "ACC-068", "Bart Lindahl", "Procurement Manager", [], "2024-06-20", "2015-07-13", None, "aldertonfoods.example"),
    ("CON-091", "ACC-053", "Imogen Clarke", "Merchandising Analytics Lead", ["champion"], "2026-08-20", "2022-03-14", None, None),
    ("CON-092", "ACC-055", "Rafael Ortiz", "Finance Systems Analyst", ["champion"], "2026-09-03", "2022-10-03", None, None),
    ("CON-093", "ACC-057", "Hana Sato", "Distribution Planning Manager", ["champion"], "2026-09-09", "2023-01-16", None, None),
]

# Opportunities: id, account, name, type, stage, status, owner, amount, close_date, closed_lost_reason, meddpicc
OPPS = [
    ("OPP-005", "ACC-005", "Corvane revenue analytics", "new_business", "Closed Lost", "closed_lost", "Owen Castellano", 42000, "2026-04-10", "Budget", None),
    ("OPP-006", "ACC-007", "Marlowe Ridge renewal", "renewal", "Renewal: Proposal", "open", "Sofia Brandt", 22000, "2026-12-01", None, None),
    ("OPP-007", "ACC-017", "Orrin Pets renewal", "renewal", "Renewal: Proposal", "open", "Tess Harlow", 15000, "2026-11-05", None, None),
    ("OPP-008", "ACC-029", "Cobaltline Plumbing sales reporting", "new_business", "Closed Lost", "closed_lost", "Owen Castellano", 18000, "2026-02-20", "Price", None),
    ("OPP-009", "ACC-031", "Bramblecote Category renewal", "renewal", "Renewal: Proposal", "open", "Sofia Brandt", 76000, "2026-11-30", None,
     {"champion": ("CON-049", "2026-04-02"), "economic_buyer": ("CON-050", "2026-04-02"), "pain": ("Promotion analysis takes a week per retailer", "2026-04-02")}),
    ("OPP-010", "ACC-034", "NGHS Population Health renewal", "renewal", "Renewal: Negotiation", "open", "Nikhil Varma", 132000, "2026-12-15", None,
     {"champion": ("CON-052", "2026-06-10"), "economic_buyer": ("CON-053", "2026-06-10"), "pain": ("Care gap reports are three weeks stale", "2026-06-10")}),
    ("OPP-011", "ACC-037", "Arvelle Procurement renewal", "renewal", "Renewal: Proposal", "open", "Lucas Moretti", 54000, "2026-11-12", None,
     {"champion": ("CON-054", "2026-05-01"), "economic_buyer": ("CON-055", "2026-05-01"), "pain": ("No view of spend by supplier across plants", "2026-05-01")}),
    ("OPP-012", "ACC-039", "Wexmoor Network Planning renewal", "renewal", "Renewal: Discovery", "open", "Grace Adeyemi", 90000, "2026-12-01", None,
     {"champion": ("CON-056", "2026-03-10"), "economic_buyer": ("CON-057", "2026-03-10"), "pain": ("Capacity forecasts built by hand each quarter", "2026-03-10")}),
    ("OPP-013", "ACC-042", "Vantris Revenue Cycle renewal", "renewal", "Renewal: Proposal", "open", "Kendall Ross", 104000, "2026-11-25", None,
     {"champion": ("CON-059", "2026-05-20"), "economic_buyer": ("CON-060", "2026-05-20"), "pain": ("Denials tracked in spreadsheets per clinic", "2026-05-20")}),
    ("OPP-014", "ACC-043", "Pemberton store reporting", "new_business", "Closed Lost", "closed_lost", "Owen Castellano", 68000, "2026-05-29", "Price", None),
    ("OPP-015", "ACC-044", "Silverbrook actuarial analytics", "new_business", "Closed Lost", "closed_lost", "Jordan Pike", 95000, "2026-06-30", "No decision", None),
    ("OPP-016", "ACC-045", "Duskfield operations analytics", "new_business", "Closed Lost", "closed_lost", "Sofia Brandt", 61000, "2026-03-18", "Lost to competitor", None),
    ("OPP-017", "ACC-046", "Fenwick finance and store analytics", "new_business", "Closed Lost", "closed_lost", "Abel Okafor", 120000, "2026-07-22", "Timing", None),
    ("OPP-018", "ACC-048", "Graywater fleet analytics", "new_business", "Closed Lost", "closed_lost", "Jordan Pike", 57000, "2026-08-14", "Missing feature", None),
    ("OPP-019", "ACC-050", "Kinsale finance reporting", "new_business", "Closed Lost", "closed_lost", "Mei Lindqvist", 45000, "2024-11-08", "Price", None),
    ("OPP-020", "ACC-050", "Kinsale operations analytics", "new_business", "Closed Lost", "closed_lost", "Mei Lindqvist", 52000, "2026-06-05", "Champion left", None),
    ("OPP-021", "ACC-054", "Ashby Lane Dental renewal", "renewal", "Renewal: Proposal", "open", "Nikhil Varma", 19000, "2026-11-18", None, None),
    ("OPP-022", "ACC-060", "Redfern project controls analytics", "new_business", "Proposal", "open", "Jordan Pike", 72000, "2026-11-14", None,
     {"champion": ("CON-083", "2026-09-22"), "pain": ("Cost overruns found a month late", "2026-09-22")}),
    ("OPP-023", "ACC-063", "Thistlecombe Resorts revenue analytics", "new_business", "Discovery", "open", "Mei Lindqvist", 55000, "2026-12-18", None,
     {"champion": ("CON-084", "2026-10-01"), "pain": ("Rate decisions made without occupancy forecasts", "2026-10-01")}),
    ("OPP-024", "ACC-064", "Stonemere broker analytics", "new_business", "Evaluation", "open", "Owen Castellano", 48000, "2026-11-30", None,
     {"champion": ("CON-085", "2026-09-25"), "economic_buyer": ("CON-085", "2026-09-25")}),
    ("OPP-025", "ACC-066", "Everhart member analytics", "new_business", "Proposal", "open", "Lucas Moretti", 39000, "2026-10-30", None,
     {"champion": ("CON-087", "2026-09-25"), "pain": ("Member churn spotted only after accounts close", "2026-09-25")}),
]

# Leads: id, name, title, company, email, source, created_date, form_note
LEADS = [
    ("L-002", "Ines Valcourt", "Head of Analytics", "Quillfeather Studios", "ines.valcourt@quillfeather.example", "Inbound demo request", "2026-10-02", "We want one place to track production budgets across our animation projects."),
    ("L-003", "Tobias Wren", "VP Operations", "Brannock Logistics", "tobias.wren@brannocklogistics.example", "Webinar signup", "2026-10-03", "Interested in on-time delivery reporting for our regional carriers."),
    ("L-004", "Yusuf Adler", "Controller", "Corvane Systems", "yusuf.adler@corvanesystems.example", "Inbound demo request", "2026-10-01", "Need faster month-end close reporting."),
    ("L-005", "Ama Kusi", "Data Lead", "Tidewell Grain Cooperative", "ama.kusi@tidewellgrain.example", "Content download", "2026-10-04", "Downloaded the harvest forecasting guide."),
    ("L-006", "Harriet Osei", "Director of Planning", "Lumenfold Packaging", "harriet.osei@lumenfold.example", "Inbound demo request", "2026-10-05", "I've run planning here for eleven years and we still do it all in spreadsheets."),
    ("L-007", "Felix Duarte", "CFO", "Marlowe Ridge Capital", "felix.duarte@marloweridgecap.example", "Inbound demo request", "2026-10-02", "Looking for portfolio reporting for our limited partners."),
    ("L-008", "Noor Haddad", "Operations Analyst", "Sablewood Robotics", "noor.haddad@sablewood.example", "Free trial signup", "2026-10-03", "Want to try dashboards for our assembly line throughput."),
    ("L-009", "Wendell Pryce", "Head of Quality", "Halvard Medical Devices", "wendell.pryce@halvardmed.example", "Inbound demo request", "2026-10-04", "Tracking complaint trends and corrective action cycle times."),
    ("L-010", "Maren Solberg", "Director of Supply Chain", "Ostrander Mills", "maren.solberg@ostrandermills.example", "Inbound demo request", "2026-10-01", "Our supplier lead times are all over the place and we need better visibility."),
    ("L-011", "Desmond Achebe", "Lab Operations Manager", "Ferncliff Labs", "desmond.achebe@ferncliff.example", "Webinar signup", "2026-10-02", "Interested in instrument utilization dashboards."),
    ("L-012", "Selma Varga", "Head of Program Finance", "Orrin Aerospace", "selma.varga@orrinaero.example", "Inbound demo request", "2026-10-03", "Need earned value reporting across programs."),
    ("L-013", "Ruth Abernathy", "Service Planning Manager", "KTC", "ruth.abernathy@kestreltransit.example", "Inbound demo request", "2026-10-05", "Looking at ridership and on-time performance reporting."),
    ("L-014", "Bianca Torvald", "Marketing Operations Lead", "Glenhollow Insurance", "bianca.torvald@glenhollow.example", "Content download", "2026-10-02", "Downloaded the campaign attribution guide."),
    ("L-015", "Oscar Beaumont", "E-commerce Director", "Juniper & Vale", "oscar.beaumont@junipervale.example", "Inbound demo request", "2026-10-04", "Want online and store sales in one view."),
    ("L-016", "Elena Marsh", "Head of Research Operations", "Tamsworth University", "elena.marsh@tamsworth.example", "Inbound demo request", "2026-10-01", "We need grant spend reporting across departments."),
    ("L-017", "Patrick Ndiaye", "Revenue Operations Manager", "Cobaltline Software", "patrick.ndiaye@cobaltline.example", "Free trial signup", "2026-10-03", "Pipeline reporting for our sales team."),
    ("L-018", "Ivo Petrakis", "Director of Sales Operations", "Bramblecote Foods", "ivo.petrakis@bramblecote.example", "Inbound demo request", "2026-10-02", "Looking for retailer sell-in reporting for the sales team."),
    ("L-019", "Colette Banner", "Director of HR Analytics", "Northgate Health", "colette.banner@northgatehs.example", "Inbound demo request", "2026-10-03", "Nurse staffing and turnover dashboards."),
    ("L-020", "Tomasz Wilk", "Plant Controller", "Arvelle Chemicals", "tomasz.wilk@arvelle.example", "Webinar signup", "2026-10-01", "Plant cost reporting."),
    ("L-021", "Ayla Demir", "Head of Pricing", "Wexmoor Telecom", "ayla.demir@wexmoor.example", "Inbound demo request", "2026-10-04", "Need price elasticity analysis for our consumer plans."),
    ("L-022", "Jasper Quill", "Billing Operations Manager", "Clarion Billing", "jasper.quill@clarionbilling.example", "Inbound demo request", "2026-10-02", "Claims denial reporting for our billing team."),
    ("L-023", "Gwen Halloran", "Director of FP&A", "Pemberton Hardware", "gwen.halloran@pembertonhw.example", "Inbound demo request", "2026-10-03", "Store-level P&L reporting."),
    ("L-024", "Mateo Iglesias", "IT Director", "Silverbrook Mutual", "mateo.iglesias@silverbrookmutual.example", "Inbound demo request", "2026-10-01", "Evaluating analytics platforms for the actuarial and claims teams."),
    ("L-025", "Rosalind Thorne", "Analytics Manager", "Duskfield Energy", "rosalind.thorne@duskfield.example", "Inbound demo request", "2026-10-05", "Want to take another look at forecasting tools."),
    ("L-026", "Hollis Grady", "Director of Store Operations", "Fenwick Home Outlet", "hollis.grady@fenwickretail.example", "Inbound demo request", "2026-10-02", "Store labor and foot traffic reporting."),
    ("L-027", "Anouk Visser", "Head of Logistics Analytics", "Graywater Shipping", "anouk.visser@graywatership.example", "Inbound demo request", "2026-10-04", "Port turnaround reporting."),
    ("L-028", "Bertrand Lacroix", "VP Finance", "Kinsale Robotics", "bertrand.lacroix@kinsalerobotics.example", "Inbound demo request", "2026-10-03", "Board reporting and cash forecasting."),
    ("L-029", "Celeste Moravec", "VP Analytics", "Harrowgate Logistics", "celeste.moravec@harrowgate.example", "Inbound demo request", "2026-10-01", "We used Larkspur at my previous company and I want it for my new team."),
    ("L-030", "Dmitri Hale", "Head of Revenue Operations", "Brightmoor Payments", "dmitri.hale@brightmoorpay.example", "Inbound demo request", "2026-10-02", "Need pipeline and quota attainment dashboards."),
    ("L-031", "Lorna Fitzgerald", "Director of Merchandising Analytics", "Ashby Lane Home", "lorna.fitzgerald@ashbylanehome.example", "Inbound demo request", "2026-10-04", "Assortment and markdown reporting."),
    ("L-032", "Kate Moreau", "Head of Finance Systems", "Lindale Pharmacy", "kate.moreau@lindalepharmacy.example", "Inbound demo request", "2026-10-03", "Looking to replace our reporting stack."),
    ("L-033", "Samir Qureshi", "Director of Planning", "Ellery Cold Storage", "samir.qureshi@ellerycold.example", "Inbound demo request", "2026-10-05", "I rolled out Larkspur for the distribution team at Mossgiel and want the same here."),
    ("L-034", "Daniel Ferreira", "Head of Data", "Quaybridge Marine", "daniel.ferreira@quaybridge.example", "Inbound demo request", "2026-10-02", "Building a data team from scratch and need a BI layer."),
    ("L-035", "Harper Lund", "Director of Operations Finance", "Redfern Construction", "harper.lund@redfernbuild.example", "Inbound demo request", "2026-10-03", "Project cost reporting."),
    ("L-036", "Quentin Ashdown", "Finance Director", "Thistlecombe Hotel Group", "quentin.ashdown@thistlecombe.example", "Inbound demo request", "2026-10-04", "RevPAR and labor cost reporting across our hotels."),
    ("L-037", "Yara Haddou", "Head of Broker Analytics", "Stonemere Insurance Brokers", "yara.haddou@stonemerebrokers.example", "Webinar signup", "2026-10-01", "Broker performance dashboards."),
    ("L-038", "Noemi Brandvold", "Director of Customer Analytics", "Everhart Credit Union", "noemi.brandvold@everhartcu.example", "Inbound demo request", "2026-10-02", "Requesting a demo for my wider team."),
    ("L-039", "Pavel Novak", "Head of Analytics", "Corbel Architecture", "pavel.novak@corbelarch.example", "Inbound demo request", "2026-10-05", "Project profitability reporting for the partners."),
    ("L-040", "Wilhelmina Royce", "VP Operations", "Alderton Provisions", "wilhelmina.royce@alderton.example", "Inbound demo request", "2026-10-03", "Warehouse throughput and waste reporting."),
]

# Transcripts: id, account, date, call_type, contact_ids, what the call is about (planted lines come from planted_facts.json)
TRANSCRIPT_SPECS = [
    ("T-0005", "ACC-004", "2026-08-25", "Check-in", ["CON-030"], "Routine, friendly check-in. Front desk teams use the patient scheduling dashboards daily. No issues."),
    ("T-0006", "ACC-005", "2026-04-08", "Pricing call", ["CON-031"], "Final pricing call on a new deal for revenue management dashboards. The prospect liked the demo but declines on budget."),
    ("T-0007", "ACC-006", "2026-09-29", "Check-in", ["CON-032"], "Friendly check-in. The firm's paralegal operations team uses matter reporting dashboards. Small ask about a new report template."),
    ("T-0008", "ACC-007", "2026-09-21", "Check-in", ["CON-034"], "Tense check-in ahead of a December renewal. Weak harvest, fewer people logging in, owners want to cut costs."),
    ("T-0009", "ACC-009", "2026-08-12", "QBR", ["CON-035"], "Upbeat quarterly review. Branch performance dashboards are widely used. Talk of adding a deposits view."),
    ("T-0010", "ACC-011", "2026-07-08", "QBR", ["CON-036", "CON-037"], "Upbeat quarterly review of the finance team's close and budget dashboards. The CFO is pleased with faster month-end."),
    ("T-0011", "ACC-011", "2026-09-16", "Check-in", ["CON-036"], "Friendly check-in. Finance team adoption is strong. Gideon offers to show other teams what they built."),
    ("T-0012", "ACC-014", "2026-06-24", "QBR", ["CON-038", "CON-039"], "Upbeat quarterly review of clinical trial enrollment dashboards."),
    ("T-0013", "ACC-014", "2026-09-09", "Check-in", ["CON-038"], "Friendly check-in after a smooth board review that used the trial dashboards."),
    ("T-0014", "ACC-016", "2026-07-14", "QBR", ["CON-040"], "Upbeat quarterly review of production line and scrap dashboards."),
    ("T-0015", "ACC-016", "2026-09-22", "Check-in", ["CON-040"], "Friendly check-in. Line dashboards are on the shop floor and scrap is down."),
    ("T-0016", "ACC-017", "2026-09-15", "Check-in", ["CON-041"], "Downbeat check-in before a November renewal. The online store team shrank and seats sit unused. The customer hints at cutting seats."),
    ("T-0017", "ACC-019", "2026-06-30", "QBR", ["CON-042"], "Upbeat quarterly review of fleet maintenance dashboards."),
    ("T-0018", "ACC-019", "2026-09-08", "Check-in", ["CON-042"], "Friendly check-in. Maintenance dashboards cut breakdowns. Small ask about parts inventory reporting."),
    ("T-0019", "ACC-021", "2026-07-21", "QBR", ["CON-043"], "Upbeat quarterly review of claims cycle time dashboards."),
    ("T-0020", "ACC-021", "2026-09-28", "Check-in", ["CON-043"], "Friendly check-in. Adjusters want access and the team plans to add seats."),
    ("T-0021", "ACC-023", "2026-07-01", "QBR", ["CON-044"], "Upbeat quarterly review of store sales dashboards."),
    ("T-0022", "ACC-023", "2026-09-17", "Check-in", ["CON-044"], "Friendly check-in. Store managers rely on the weekly sell-through dashboard."),
    ("T-0023", "ACC-025", "2026-06-16", "QBR", ["CON-045"], "Upbeat quarterly review of admissions funnel dashboards."),
    ("T-0024", "ACC-025", "2026-09-14", "Check-in", ["CON-045"], "Friendly check-in after the admissions cycle closed. The yield forecast was accurate."),
    ("T-0025", "ACC-026", "2026-07-09", "QBR", ["CON-046"], "Upbeat quarterly review of donor and campaign dashboards."),
    ("T-0026", "ACC-026", "2026-09-24", "Check-in", ["CON-046"], "Friendly check-in. Gift officers plan their week from the donor dashboards."),
    ("T-0027", "ACC-028", "2026-07-07", "QBR", ["CON-047"], "Upbeat quarterly review of customer health dashboards."),
    ("T-0028", "ACC-028", "2026-09-29", "Check-in", ["CON-047"], "Friendly check-in. Churn risk scoring is part of the managers' morning routine."),
    ("T-0029", "ACC-029", "2026-02-18", "Pricing call", ["CON-048"], "Final pricing call on a new deal for a small plumbing supply house. The owner declines on price."),
    ("T-0030", "ACC-031", "2026-06-18", "QBR", ["CON-049", "CON-050"], "Upbeat quarterly review of promotion and category dashboards. Strong usage. Renewal in November mentioned in passing."),
    ("T-0031", "ACC-031", "2026-09-24", "Check-in", ["CON-049"], "Worried check-in. Naomi is leaving the company soon, nobody is named to own the tool, logins have dropped, and Ralph wants to review the renewal."),
    ("T-0032", "ACC-032", "2026-08-19", "Check-in", ["CON-051"], "Friendly check-in. Clinic scheduling dashboards work well across the clinics."),
    ("T-0033", "ACC-034", "2026-07-22", "QBR", ["CON-052"], "Steady quarterly review of care gap dashboards. Some mention of budget pressure at the hospital system, nothing concrete."),
    ("T-0034", "ACC-034", "2026-09-30", "Check-in", ["CON-052", "CON-053"], "Hard check-in with the CFO. Finance froze software renewals and wants the renewal smaller. Usage has fallen."),
    ("T-0035", "ACC-037", "2026-07-02", "QBR", ["CON-054"], "Steady quarterly review of supplier spend dashboards."),
    ("T-0036", "ACC-037", "2026-09-18", "Check-in", ["CON-054"], "Uneasy check-in. The procurement team is trialing a cheaper tool and wants a comparison before renewal. Fewer people log in."),
    ("T-0037", "ACC-039", "2026-05-20", "QBR", ["CON-056"], "Upbeat quarterly review of network capacity dashboards with Rupert, the champion."),
    ("T-0038", "ACC-039", "2026-08-27", "Check-in", ["CON-056"], "Check-in where Rupert says he is moving to another team and handing the tool to Mina."),
    ("T-0039", "ACC-039", "2026-09-29", "Check-in", ["CON-058"], "First check-in with Mina, the new owner. She is still learning the tool, usage is down, and she doubts the renewal at current seats."),
    ("T-0040", "ACC-042", "2026-07-15", "QBR", ["CON-059"], "Steady quarterly review of claims denial dashboards with Delphine, the champion."),
    ("T-0041", "ACC-042", "2026-09-23", "Check-in", ["CON-061"], "Check-in with Kofi, an analyst. Delphine has left the company, nobody owns the rollout, and usage is falling."),
    ("T-0042", "ACC-043", "2026-04-14", "Discovery", ["CON-062"], "Discovery call. Merchandising team wants store-level sales and margin reporting."),
    ("T-0043", "ACC-043", "2026-05-27", "Pricing call", ["CON-062", "CON-063"], "Final pricing call. The CFO declines on price compared with spreadsheets."),
    ("T-0044", "ACC-044", "2026-05-12", "Discovery", ["CON-064"], "Discovery call. Actuarial team wants faster loss trend reporting."),
    ("T-0045", "ACC-044", "2026-06-25", "Security review", ["CON-064", "CON-065"], "Security review. The CISO requires SAML single sign-on and audit logs, which the rep could not show. The deal stalls."),
    ("T-0046", "ACC-045", "2026-02-10", "Discovery", ["CON-066"], "Discovery call. Operations analytics for grid assets."),
    ("T-0047", "ACC-045", "2026-03-16", "Decision call", ["CON-066", "CON-067"], "Decision call. The customer chose another vendor because of a SCADA historian connector."),
    ("T-0048", "ACC-046", "2026-06-09", "Discovery", ["CON-068"], "Discovery call. Finance wants store and category reporting across the retail group."),
    ("T-0049", "ACC-046", "2026-07-20", "Decision call", ["CON-068"], "Decision call. The group freezes new vendors until a store systems migration finishes."),
    ("T-0050", "ACC-048", "2026-07-01", "Discovery", ["CON-069"], "Discovery call. Fleet planning wants vessel schedule and port reporting."),
    ("T-0051", "ACC-048", "2026-08-12", "Decision call", ["CON-069"], "Decision call. No native connector to the vessel tracking feed, so the customer says no for now."),
    ("T-0052", "ACC-049", "2026-09-02", "Check-in", ["CON-070"], "Friendly check-in at a brewery. Taproom sales dashboards are popular."),
    ("T-0053", "ACC-050", "2024-10-30", "Pricing call", ["CON-072"], "Pricing call on a first deal. The COO declines on per-seat price."),
    ("T-0054", "ACC-050", "2026-05-14", "Discovery", ["CON-071"], "Discovery call for a second attempt, led by Ngozi, an enthusiastic BI director."),
    ("T-0055", "ACC-050", "2026-06-03", "Decision call", ["CON-072"], "Decision call. Ngozi has left, so the COO stops the evaluation."),
    ("T-0056", "ACC-051", "2026-04-22", "QBR", ["CON-073"], "Upbeat quarterly review. Celeste, the analytics director, praises the tool and her team's dashboards."),
    ("T-0057", "ACC-051", "2026-09-10", "Check-in", ["CON-074"], "Check-in with the CFO, who took over as main contact after Celeste left. Usage is steady."),
    ("T-0058", "ACC-052", "2026-06-03", "QBR", ["CON-075"], "Upbeat quarterly review of recruiter pipeline dashboards with Dmitri, the admin."),
    ("T-0059", "ACC-052", "2026-08-26", "Check-in", ["CON-075"], "Check-in where Dmitri says it is his last call because he is leaving for a new job. He names who will take over at a high level only."),
    ("T-0060", "ACC-053", "2026-05-19", "QBR", ["CON-076"], "Upbeat quarterly review of merchandising dashboards with Lorna."),
    ("T-0061", "ACC-053", "2026-08-20", "Check-in", ["CON-091"], "Check-in with Imogen, who took over from Lorna. Usage is steady."),
    ("T-0062", "ACC-054", "2026-09-16", "Check-in", ["CON-077"], "Downbeat check-in at a small dental group before a November renewal. Fewer people log in and they are cutting costs."),
    ("T-0063", "ACC-055", "2026-06-11", "QBR", ["CON-078"], "Upbeat quarterly review of freight cost dashboards with Katherine, who set them up."),
    ("T-0064", "ACC-055", "2026-09-03", "Check-in", ["CON-092"], "Check-in with Rafael, who now runs the finance dashboards after Katherine left. Usage is steady."),
    ("T-0065", "ACC-057", "2026-05-27", "QBR", ["CON-079"], "Upbeat quarterly review of distribution planning dashboards with Samir, who rolled them out."),
    ("T-0066", "ACC-057", "2026-09-09", "Check-in", ["CON-093"], "Check-in with Hana, the new distribution planning manager. Usage is steady."),
    ("T-0067", "ACC-058", "2026-05-20", "QBR", ["CON-080"], "Upbeat quarterly review of water network dashboards with Daniel, the data platform lead."),
    ("T-0068", "ACC-058", "2026-09-02", "Check-in", ["CON-080", "CON-081"], "Check-in where Daniel says he is leaving and hands the account to Priti."),
    ("T-0069", "ACC-059", "2026-09-30", "Check-in", ["CON-082"], "Friendly check-in at a dental lab. Daniel, the long-time lab supervisor, likes the case turnaround dashboard."),
    ("T-0070", "ACC-060", "2026-08-28", "Discovery", ["CON-083"], "Discovery call with Moira about project cost tracking across job sites."),
    ("T-0071", "ACC-060", "2026-09-22", "Demo", ["CON-083"], "Demo follow-up. Moira is positive and commits to a timeline for the proposal."),
    ("T-0072", "ACC-063", "2026-09-15", "Discovery", ["CON-084"], "Discovery call with the resorts revenue director about occupancy forecasting. She hints the hotels side may want it too."),
    ("T-0073", "ACC-063", "2026-10-01", "Follow-up", ["CON-084"], "Follow-up call scheduling a technical session and confirming data sources."),
    ("T-0074", "ACC-064", "2026-08-20", "Discovery", ["CON-085"], "Discovery call with the COO about broker commission and retention reporting."),
    ("T-0075", "ACC-064", "2026-09-25", "Evaluation kickoff", ["CON-085"], "Evaluation kickoff. The COO sets an end date for testing."),
    ("T-0076", "ACC-065", "2026-08-27", "Check-in", ["CON-086"], "Friendly check-in at a garden center chain. Seasonal sales dashboards work well."),
    ("T-0077", "ACC-066", "2026-09-03", "Discovery", ["CON-087"], "Discovery call with Noemi about member churn reporting."),
    ("T-0078", "ACC-066", "2026-09-25", "Proposal review", ["CON-087"], "Proposal review. Noemi plans to take the proposal to the board."),
    ("T-0079", "ACC-067", "2024-09-12", "Intro call", ["CON-088"], "Short intro call with a junior analyst who cannot buy and suggests coming back next year."),
    ("T-0080", "ACC-068", "2024-06-20", "Intro call", ["CON-089"], "Intro call with the operations manager about warehouse reporting, timed for after a new warehouse opens."),
]


# ---- Records ----


def _accounts() -> list[dict]:
    return [
        {
            "account_id": aid, "name": name, "name_variants": variants, "parent_account_id": parent,
            "domain": domain, "industry": industry, "is_customer": customer, "account_owner": owner,
            "arr_usd": arr, "licensed_seats": seats, "renewal_date": renewal, "activity": [],
        }
        for aid, name, variants, parent, domain, industry, customer, owner, arr, seats, renewal in ACCOUNTS
    ]


def _email(name: str, domain: str) -> str:
    return f"{name.lower().replace(' ', '.')}@{domain}"


def _contacts(accounts: dict) -> list[dict]:
    records = []
    for cid, aid, name, title, roles, updated, start, end, email_domain in CONTACTS:
        account = accounts[aid]
        records.append({
            "contact_id": cid, "account_id": aid, "name": name, "title": title,
            "email": _email(name, email_domain or account["domain"]), "role_tags": roles, "last_updated": updated,
            "employment_history": [{"account_id": aid, "company": account["name"], "title": title, "start": start, "end": end}],
        })
    return records


def _opps(contacts: dict) -> list[dict]:
    records = []
    for oid, aid, name, kind, stage, status, owner, amount, close, reason, meddpicc in OPPS:
        fields = {}
        for field, (value, updated) in (meddpicc or {}).items():
            if value in contacts:
                c = contacts[value]
                fields[field] = {"value": f"{c['name']}, {c['title']}", "contact_id": value, "last_updated": updated}
            else:
                fields[field] = {"value": value, "last_updated": updated}
        records.append({
            "opp_id": oid, "account_id": aid, "name": name, "type": kind, "stage": stage, "status": status,
            "owner": owner, "amount_usd": amount, "close_date": close, "closed_lost_reason": reason, "meddpicc": fields,
        })
    return records


def _leads() -> list[dict]:
    keys = ["lead_id", "name", "title", "company", "email", "source", "created_date", "form_note"]
    return [dict(zip(keys, row)) for row in LEADS]


def usage_scorecard(account_id: str, seats: int, declining: bool) -> dict:
    """12 weekly rows, seeded by account ID so reruns give the same numbers."""
    rng = random.Random(account_id)
    if declining:
        # Gentle drift for seven weeks, then the steepest drop in the last five (like L-001's ACC-002).
        start, end = rng.uniform(76, 84), rng.uniform(38, 48)
        utils = [start - i * rng.uniform(0.7, 1.4) for i in range(7)]
        step = (utils[-1] - end) / 5
        utils += [utils[-1] - step * (i + 1) + rng.uniform(-0.8, 0.8) for i in range(5)]
    else:
        base = rng.uniform(80, 90)
        utils = [min(97.0, max(76.0, base + rng.uniform(-3, 3))) for _ in range(12)]
    rates = {
        "dashboards_viewed": rng.uniform(5.5, 7.0),
        "scheduled_reports_active": rng.uniform(0.3, 0.45),
        "data_exports": rng.uniform(0.25, 0.4),
    }
    extra = rng.choice(["forecasts_run", "alerts_configured", "shared_workspaces", None])
    if extra:
        rates[extra] = rng.uniform(0.1, 0.3)
    weeks = []
    for week_ending, util in zip(WEEK_ENDINGS, utils):
        active = round(seats * util / 100)
        pct = round(100 * active / seats, 1)
        health = max(0, min(100, round(1.25 * pct - 19 + rng.uniform(-1.5, 1.5))))
        weeks.append({
            "week_ending": week_ending.isoformat(),
            "licensed_seats": seats,
            "active_seats": active,
            "utilization_pct": pct,
            "features": {name: round(active * rate * rng.uniform(0.95, 1.05)) for name, rate in rates.items()},
            "health_score": health,
            "health_band": "green" if health >= 70 else "yellow" if health >= 50 else "red",
        })
    return {"account_id": account_id, "weeks": weeks}


def _merge(path, generated: list[dict], id_key: str) -> list[dict]:
    """Hand-written records from the existing file, then the generated ones, sorted by ID."""
    kept = [r for r in json.loads(path.read_text(encoding="utf-8")) if r[id_key] in HAND_WRITTEN]
    records = kept + generated
    ids = [r[id_key] for r in records]
    assert len(ids) == len(set(ids)), f"duplicate IDs in {path.name}"
    return sorted(records, key=lambda r: r[id_key])


def _write_json(path, data) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


# ---- Transcripts ----

SYSTEM = """You write short sales call transcripts for a synthetic test dataset. The seller is Larkspur Analytics, a fictional mid-market B2B analytics software company with seat-based licensing. Every company and person is invented.

Rules:
- Output only dialogue: one line per speaker turn, in the form "Full Name: what they say", with a blank line between turns. No title, header, stage directions, or notes.
- 8 to 14 turns. Plain, natural business speech, like the example.
- Only the listed participants speak, and each speaker label is their full name exactly as given.
- Include every required sentence word for word, spoken by its named speaker. Do not paraphrase it.
- Never use em dashes or en dashes. Use commas, periods, or colons.
- Do not name any real company, product, or person, and do not name other vendors. Mention no other company names than the ones given.
- Use only the numbers given. If seat usage comes up, use the figures provided. Do not invent prices, dates, or percentages."""

EXAMPLE_PATH = TRANSCRIPTS / "T-0002.txt"


def _company_label(account: dict) -> str:
    return account["name_variants"][0] if account["name_variants"] else account["name"]


def transcript_header(spec, accounts: dict, contacts: dict) -> str:
    tid, aid, day, call_type, contact_ids, _ = spec
    account = accounts[aid]
    assert account["account_owner"], f"{tid}: account {aid} needs an owner to speak for Larkspur"
    rep = f"{account['account_owner']} (Larkspur Analytics, account owner)"
    people = [f"{contacts[c]['name']} ({contacts[c]['title']}, {_company_label(account)})" for c in contact_ids]
    return "\n".join([
        f"transcript_id: {tid}",
        f"account_id: {aid}",
        f"date: {day}",
        f"call_type: {call_type}",
        f"contact_ids: {', '.join(contact_ids)}",
        f"participants: {'; '.join([rep, *people])}",
    ])


def _usage_note(account: dict, usage: dict, day: str) -> str:
    if not account["is_customer"]:
        return "This company is a prospect, not a customer, so there is no seat usage to discuss."
    weeks = usage[account["account_id"]]["weeks"]
    on_or_before = [w for w in weeks if w["week_ending"] <= day] or weeks[:1]
    w = on_or_before[-1]
    return f"Seat usage around this call: about {w['active_seats']} of {w['licensed_seats']} licensed seats active each week."


def transcript_prompt(spec, accounts: dict, contacts: dict, usage: dict, planted: list[dict]) -> str:
    tid, aid, day, call_type, contact_ids, about = spec
    account = accounts[aid]
    parent = accounts.get(account["parent_account_id"]) if account["parent_account_id"] else None
    company = account["name"] + (f", part of {parent['name']}" if parent else "")
    people = [f"- {account['account_owner']}, the Larkspur account owner"]
    people += [f"- {contacts[c]['name']}, {contacts[c]['title']} at {_company_label(account)}" for c in contact_ids]
    required = [f'- {p["speaker"]} says: "{p["says"]}"' for p in planted] or ["- None."]
    return "\n".join([
        f"Write the transcript of a {call_type} call on {day} with {company} ({account['industry']}).",
        "",
        "Participants:", *people,
        "",
        f"What the call is about: {about}",
        _usage_note(account, usage, day),
        "",
        "Required sentences:", *required,
        "",
        "Example of the style (a different call):",
        EXAMPLE_PATH.read_text(encoding="utf-8").split("\n---\n", 1)[1].strip(),
    ])


def transcript_problems(body: str, speakers: list[str], planted: list[dict]) -> list[str]:
    """Why a transcript body is not acceptable. Empty means it passes."""
    problems = []
    turns = [t for t in body.split("\n\n") if t.strip()]
    if not 6 <= len(turns) <= 18:
        problems.append(f"{len(turns)} turns")
    for turn in turns:
        name = turn.split(":", 1)[0]
        if ":" not in turn or name not in speakers or "\n" in turn.strip():
            problems.append(f"bad turn: {turn[:60]!r}")
    if re.search("[\u2013\u2014]", body):
        problems.append("contains an em or en dash")
    for p in planted:
        if not any(t.startswith(f"{p['speaker']}:") and p["says"] in t for t in turns):
            problems.append(f"missing planted line from {p['speaker']}")
    return problems


def write_transcript(client, spec, accounts, contacts, usage, planted, force: bool) -> str:
    """Keep a valid transcript on disk, or ask the model for a new one (up to three tries)."""
    tid, aid, _, _, contact_ids, _ = spec
    path = TRANSCRIPTS / f"{tid}.txt"
    header = transcript_header(spec, accounts, contacts)
    speakers = [accounts[aid]["account_owner"], *(contacts[c]["name"] for c in contact_ids)]
    if path.exists() and not force:
        old_header, _, old_body = path.read_text(encoding="utf-8").partition("\n---\n")
        if old_header == header and not transcript_problems(old_body.strip(), speakers, planted):
            return f"{tid}: kept"
    if client is None:
        raise SystemExit(f"{tid} needs to be written but --offline was given.")
    prompt = transcript_prompt(spec, accounts, contacts, usage, planted)
    problems = []
    for attempt in range(3):
        response = client.messages.create(
            model=config.TRANSCRIPT_MODEL,
            max_tokens=4000,
            output_config={"effort": config.TRANSCRIPT_EFFORT},
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        body = "".join(b.text for b in response.content if b.type == "text").strip()
        problems = transcript_problems(body, speakers, planted)
        if not problems:
            path.write_text(f"{header}\n---\n{body}\n", encoding="utf-8")
            return f"{tid}: written (attempt {attempt + 1})"
    raise RuntimeError(f"{tid} failed validation three times: {problems}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="never call the API; fail if a transcript is missing")
    parser.add_argument("--force-transcripts", action="store_true", help="rewrite every generated transcript")
    args = parser.parse_args(argv)

    accounts = {a["account_id"]: a for a in _accounts()}
    contacts = {c["contact_id"]: c for c in _contacts(accounts)}
    opps = _opps(contacts)
    _write_json(CRM / "accounts.json", _merge(CRM / "accounts.json", list(accounts.values()), "account_id"))
    _write_json(CRM / "contacts.json", _merge(CRM / "contacts.json", list(contacts.values()), "contact_id"))
    _write_json(CRM / "opportunities.json", _merge(CRM / "opportunities.json", opps, "opp_id"))
    _write_json(CRM / "leads.json", _merge(CRM / "leads.json", _leads(), "lead_id"))

    usage = {}
    for a in accounts.values():
        if a["is_customer"]:
            usage[a["account_id"]] = usage_scorecard(a["account_id"], a["licensed_seats"], a["account_id"] in DECLINING)
            _write_json(USAGE / f"{a['account_id']}.json", usage[a["account_id"]])
    print(f"CRM: {len(accounts)} accounts, {len(contacts)} contacts, {len(opps)} opps, {len(LEADS)} leads; usage: {len(usage)} scorecards")

    facts = json.loads(PLANTED_PATH.read_text(encoding="utf-8"))
    planted_by_tid: dict[str, list[dict]] = {}
    for case_facts in (v for k, v in facts.items() if not k.startswith("_")):
        for fact in case_facts:
            if fact["check"] == "transcript":
                planted_by_tid.setdefault(fact["transcript_id"], []).append(fact)

    client = None
    if not args.offline:
        config.load_env()
        key = config.api_key()
        client = anthropic.Anthropic(api_key=key) if key else None
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = [
            pool.submit(write_transcript, client, spec, accounts, contacts, usage, planted_by_tid.get(spec[0], []), args.force_transcripts)
            for spec in TRANSCRIPT_SPECS
        ]
        for job in jobs:
            print(job.result())
    return 0


if __name__ == "__main__":
    sys.exit(main())
