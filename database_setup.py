# database_setup.py
# FINAL version: Creates schema safely ONCE and adds base jobs ONLY IF MISSING.
# This script is designed to be run safely at any time to ensure the database structure is correct.

import sqlite3
import os

# --- Find the project directory and DB path ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'jobs.db')

# --- Connect to DB (creates if not exists) ---
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("Ensuring database schema is up-to-date...")

# --- Create tables IF NOT EXISTS ---
# We use IF NOT EXISTS to prevent overwriting existing tables and data.
# The 'exam_name' is set to UNIQUE to prevent duplicate entries for the same exam.

cursor.execute('''
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_name TEXT,
    exam_name TEXT UNIQUE NOT NULL,
    conducting_body TEXT, "group" TEXT, gazetted_status TEXT,
    pay_level INTEGER, salary TEXT, eligibility TEXT, age_limit TEXT, pet_status TEXT,
    application_start TEXT, application_end TEXT, exam_date TEXT,
    official_website TEXT, application_fee TEXT,
    vacancies TEXT,          -- Column for vacancy details
    vacancies_year TEXT,   -- Column for the year of vacancy data
    last_updated TEXT
)''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS job_specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER UNIQUE NOT NULL,
    nationality TEXT, age_limits TEXT, age_relax TEXT, edu_qual TEXT,
    attempts TEXT, physical_std TEXT, last_updated TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
)''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS exam_pattern (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER UNIQUE NOT NULL,
    stages TEXT, num_papers TEXT, q_type TEXT, duration TEXT,
    marking_scheme TEXT, last_updated TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
)''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS job_cutoffs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER, category TEXT, score TEXT, year TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
)''')

print("   Tables verified/created with correct schema.")

# --- Insert base jobs (using INSERT OR IGNORE) ---
# This list contains the initial 12 jobs. They will only be added if they don't already exist.
jobs_data = [('IAS Officer','UPSC CSE','UPSC','A','Gazetted',10,'₹56,100+','Any Graduation','21-32','No PET'), ('IPS Officer','UPSC CSE','UPSC','A','Gazetted',10,'₹56,100+','Any Graduation','21-32','PET Required'), ('IFS Officer','UPSC CSE','UPSC','A','Gazetted',10,'₹60,000+','Any Graduation','21-32','No PET'), ('RBI Grade B','RBI Grade B Exam','RBI','A','Gazetted',10,'₹70,000+','Graduation (50%+)','21-30','No PET'), ('SBI PO','SBI PO Exam','SBI','A','Gazetted',7,'₹40,000+','Any Graduation','21-30','No PET'), ('IBPS PO','IBPS PO Exam','IBPS','A','Gazetted',7,'₹35,000+','Any Graduation','20-30','No PET'), ('SSC CGL (AAO)','SSC CGL','SSC','B','Non-Gazetted',8,'₹45,000+','Any Graduation','18-32','No PET'), ('NDA Officer','NDA Exam','UPSC','A','Gazetted',10,'₹56,100+','10+2 (PCM)','16.5-19.5','PET Required'), ('ISRO Scientist','ISRO ICRB','ISRO','A','Gazetted',10,'₹60,000+','B.Tech/B.E (60%+)','21-35','No PET'), ('DRDO Scientist','DRDO Entry Test','DRDO','A','Gazetted',10,'₹60,000+','B.Tech/B.E (First Class)','21-28','No PET'), ('Railway Group A','UPSC ESE','UPSC','A','Gazetted',10,'₹56,100+','B.Tech/B.E','21-30','No PET'), ('LIC AAO','LIC AAO Exam','LIC','B','Non-Gazetted',8,'₹40,000+','Any Graduation','21-30','No PET')]

inserted_count = 0
for job in jobs_data:
    try:
        # Use INSERT OR IGNORE based on the UNIQUE exam_name
        cursor.execute(
            '''INSERT OR IGNORE INTO jobs (post_name, exam_name, conducting_body, "group", gazetted_status, pay_level, salary, eligibility, age_limit, pet_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', job
        )
        if cursor.rowcount > 0:
            inserted_count += 1
            new_job_id = cursor.lastrowid
            # Add empty rows to related tables only for brand new jobs so the scout knows to fill them later
            cursor.execute("INSERT OR IGNORE INTO job_specs (job_id) VALUES (?)", (new_job_id,))
            cursor.execute("INSERT OR IGNORE INTO exam_pattern (job_id) VALUES (?)", (new_job_id,))
    except sqlite3.Error as e: print(f"DB Error inserting {job[1]}: {e}")

if inserted_count > 0: print(f"Inserted {inserted_count} new base jobs.")
else: print("Base jobs already exist.")

conn.commit()
conn.close()
print("✅ Database setup complete. Schema verified/updated.")
