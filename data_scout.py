# data_scout.py
# --- FINAL version with corrected indentation and robust error handling ---

import sqlite3
import google.generativeai as genai
import os
import json
import time
import datetime
import difflib
from typing import List, Dict, Any, Optional

# --- Configuration ---
# REPLACE WITH YOUR ACTUAL API KEY
API_KEY = "PASTE_YOUR_GEMINI_API_KEY_HERE"
genai.configure(api_key=API_KEY)

# Using the stable endpoint for the Pro model as discussed
model = genai.GenerativeModel(
    'gemini-1.5-pro-latest',
    generation_config={"response_mime_type": "application/json"}
)
BATCH_SIZE = 5
UPDATE_THRESHOLD_DAYS = 7

# --- Find the database and define the status flag file ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'jobs.db')
STATUS_FLAG_FILE = os.path.join(BASE_DIR, 'update_in_progress.flag')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- Helper Functions ---

def find_best_match(exam_name_db: str, results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Finds the best matching result from the API response list."""
    if not results: return None
    names_in_api = [item.get('exam_name', '') for item in results]
    
    # 1. Exact match (case-insensitive)
    for item in results:
        if exam_name_db.lower() == item.get('exam_name', '').lower(): return item
        
    # 2. Fuzzy match
    match = difflib.get_close_matches(exam_name_db, names_in_api, n=1, cutoff=0.8)
    if match:
        for item in results:
            if item.get('exam_name', '') == match[0]:
                print(f"   (Fuzzy matched '{exam_name_db}' -> '{match[0]}')")
                return item
                
    # 3. Substring match
    possible_matches = []
    for item in results:
        api_name_lower = item.get('exam_name', '').lower()
        db_name_lower = exam_name_db.lower()
        if db_name_lower in api_name_lower: possible_matches.append(item)
        
    if len(possible_matches) == 1:
         print(f"   (Unique substring match: '{exam_name_db}' -> '{possible_matches[0].get('exam_name', '')}')")
         return possible_matches[0]
         
    print(f"   No reliable match found for '{exam_name_db}' in API results.")
    return None

def ask_gemini_batch(exam_names: List[str], find_new=False) -> Optional[List[Dict[str, Any]]]:
    """Sends a batch prompt to Gemini, expects JSON list."""
    print("   Sending request to Gemini...")
    if find_new:
        prompt = f"""
        Act as a government job notification expert. Search reliable sources for RECENTLY announced or upcoming major Indian government job exams that are LIKELY NOT in this list: {', '.join(exam_names)}.
        For each NEW exam you find (up to 5), provide the core details. Return ONLY a single, valid JSON array. Each object MUST contain keys: post_name, exam_name, conducting_body, group, gazetted_status, pay_level, salary, eligibility, age_limit, pet_status.
        Example: [{{"post_name": "Stenographer Grade C", "exam_name": "SSC Stenographer Exam", ...}}]
        If no new relevant exams are found, return an empty array [].
        """
    else:
        prompt = f"""
        For EACH of these Indian government exams: {', '.join(exam_names)}
        Provide complete, accurate details (nationality, age_limits, age_relax, edu_qual, attempts, physical_std, stages, num_papers, q_type, duration, marking_scheme, application_start, application_end, exam_date, application_fee, official_website,
        vacancies (string, e.g., "Approx 1050" or "To be announced"),
        vacancies_year (string, e.g., "2025"),
        cutoffs array with category/score, year).
        Prioritize official sources. Return ONLY a single, valid JSON array. Each object MUST contain the key "exam_name" matching the input exactly. Use "Information not available" for missing fields.
        Example: {{"exam_name": "UPSC CSE", ..., "vacancies": "Approx 1100", "vacancies_year": "2024", "cutoffs": [{{"category": "UR", "score": "95.5"}}], "year": "2023"}}
        """
    try:
        response = model.generate_content(prompt)
        print(f"   Raw Snippet: {response.text[:200]}...")
        if not response.text or not response.text.strip().startswith('['):
             print(f"   ❌ ERROR: Received non-JSON or empty response: {response.text[:100]}")
             return None
        data = json.loads(response.text)
        if isinstance(data, list):
            print(f"   Received valid JSON list ({len(data)} items).")
            return data
        else:
            print(f"   ❌ ERROR: Expected JSON list, got {type(data)}")
            return None
    except json.JSONDecodeError as e:
        print(f"   ❌ JSON Parsing Error: {e}.")
        return None
    except Exception as e:
        print(f"   ❌ Gemini API Error: {e}")
        return None

def is_valid_data(value: Optional[str]) -> bool:
    """Helper to check if a string is not empty, None, or a placeholder."""
    return value is not None and value.strip().lower() not in ['', 'n/a', 'not available', 'information not available', 'tba', 'none']

def check_update_needs(cursor, job_id: int, threshold_date: str) -> Dict[str, bool]:
    """Checks which specific sections/fields need updating for a job."""
    needs = {'main': False, 'specs': False, 'pattern': False, 'cutoffs': False}
    reason = []
    
    # Check main job table
    job_row = cursor.execute("SELECT official_website, application_fee, application_start, application_end, exam_date, vacancies, vacancies_year, last_updated FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job_row: return {'main': True, 'specs': True, 'pattern': True, 'cutoffs': True}

    job_ts_old = not job_row['last_updated'] or job_row['last_updated'] < threshold_date
    if job_ts_old: needs['main'] = True; reason.append("main ts old")
    if not is_valid_data(job_row['official_website']): needs['main'] = True; reason.append("website")
    if not is_valid_data(job_row['application_fee']): needs['main'] = True; reason.append("fee")
    if not is_valid_data(job_row['application_start']) or not is_valid_data(job_row['application_end']) or not is_valid_data(job_row['exam_date']): needs['main'] = True; reason.append("dates")
    if not is_valid_data(job_row['vacancies']) or not is_valid_data(job_row['vacancies_year']): needs['main'] = True; reason.append("vacancies")

    # Check specs
    spec_row = cursor.execute("SELECT nationality, attempts, last_updated, id FROM job_specs WHERE job_id = ?", (job_id,)).fetchone()
    spec_ts_old = not spec_row or not spec_row['last_updated'] or spec_row['last_updated'] < threshold_date
    if spec_ts_old: needs['specs'] = True; reason.append("specs ts old")
    if not spec_row or not is_valid_data(spec_row['nationality']) or not is_valid_data(spec_row['attempts']): needs['specs'] = True; reason.append("specs fields")

    # Check pattern
    pattern_row = cursor.execute("SELECT stages, marking_scheme, last_updated, id FROM exam_pattern WHERE job_id = ?", (job_id,)).fetchone()
    pattern_ts_old = not pattern_row or not pattern_row['last_updated'] or pattern_row['last_updated'] < threshold_date
    if pattern_ts_old: needs['pattern'] = True; reason.append("pattern ts old")
    if not pattern_row or not is_valid_data(pattern_row['stages']) or not is_valid_data(pattern_row['marking_scheme']):
        needs['pattern'] = True
        reason.append("pattern fields")

    # Check cutoffs
    cutoff_count = cursor.execute("SELECT COUNT(*) as cnt FROM job_cutoffs WHERE job_id = ?", (job_id,)).fetchone()['cnt']
    if cutoff_count == 0: needs['cutoffs'] = True; reason.append("cutoffs")
    elif needs['main'] or needs['specs'] or needs['pattern']: needs['cutoffs'] = True; reason.append("re-check cutoffs")

    if any(needs.values()): print(f"   Job ID {job_id} needs update. Reasons: {', '.join(reason)}")
    return needs

# --- Phase 1: Update Existing Jobs ---
def update_existing_jobs(conn: sqlite3.Connection):
    cursor = conn.cursor()
    threshold_date = (datetime.datetime.now() - datetime.timedelta(days=UPDATE_THRESHOLD_DAYS)).isoformat()
    all_jobs = cursor.execute("SELECT id, exam_name, last_updated FROM jobs").fetchall()
    
    print("--- Phase 1: Checking existing jobs for updates ---")
    jobs_update_needs = {job['id']: check_update_needs(cursor, job['id'], threshold_date) for job in all_jobs}
    jobs_to_fetch_for = [job for job in all_jobs if any(jobs_update_needs[job['id']].values())]
    
    print(f"\nFound {len(jobs_to_fetch_for)} existing jobs requiring updates.\n")
    if not jobs_to_fetch_for: print("All existing jobs up-to-date!"); return True
    
    consecutive_errors = 0
    for i in range(0, len(jobs_to_fetch_for), BATCH_SIZE):
        batch = jobs_to_fetch_for[i:i + BATCH_SIZE]
        exam_names_in_batch = [job['exam_name'] for job in batch]
        print(f"📦 Processing update batch {i//BATCH_SIZE + 1}: {', '.join(exam_names_in_batch)}")
        
        batch_results = ask_gemini_batch(exam_names_in_batch, find_new=False)
        if not batch_results:
            print("   ❌ No valid data for batch. Skipping.\n"); consecutive_errors += 1
            if consecutive_errors >= 2: print("🛑 Stopping..."); return False
            time.sleep(30); continue
            
        batch_success = False
        for job_row in batch:
            job_id = job_row['id']; exam_name_db = job_row['exam_name']
            update_needs = jobs_update_needs[job_id]
            exam_data = find_best_match(exam_name_db, batch_results)
            
            if not exam_data: print(f"   ⚠️ No match for {exam_name_db}."); continue
            print(f"\n   ✏️ Selectively Updating: {exam_name_db} (ID: {job_id})")
            now_timestamp = datetime.datetime.now().isoformat(); updated_sections = []
            
            try:
                if update_needs['main']:
                    updates = {}; current_job_data = conn.execute("SELECT application_start, application_end, exam_date, official_website, application_fee, vacancies, vacancies_year, last_updated FROM jobs WHERE id = ?", (job_id,)).fetchone()
                    # Check all fields
                    if not is_valid_data(current_job_data['application_start']): updates['application_start'] = exam_data.get('application_start', 'TBA')
                    if not is_valid_data(current_job_data['application_end']): updates['application_end'] = exam_data.get('application_end', 'TBA')
                    if not is_valid_data(current_job_data['exam_date']): updates['exam_date'] = exam_data.get('exam_date', 'TBA')
                    if not is_valid_data(current_job_data['official_website']): updates['official_website'] = exam_data.get('official_website', 'N/A')
                    if not is_valid_data(current_job_data['application_fee']): updates['application_fee'] = exam_data.get('application_fee', 'N/A')
                    if not is_valid_data(current_job_data['vacancies']): updates['vacancies'] = exam_data.get('vacancies', 'N/A')
                    if not is_valid_data(current_job_data['vacancies_year']): updates['vacancies_year'] = exam_data.get('vacancies_year', exam_data.get('year', 'N/A'))
                    
                    if updates: 
                        update_query = "UPDATE jobs SET " + ", ".join([f"{key} = ?" for key in updates.keys()]) + ", last_updated = ? WHERE id = ?"
                        params = list(updates.values()) + [now_timestamp, job_id]
                        cursor.execute(update_query, params); updated_sections.append("main")
                    elif not current_job_data['last_updated'] or current_job_data['last_updated'] < threshold_date: 
                        cursor.execute("UPDATE jobs SET last_updated = ? WHERE id = ?", (now_timestamp, job_id)); updated_sections.append("main_ts")
                        
                if update_needs['specs']:
                    specs = exam_data.get('job_specs', {});
                    if isinstance(specs, dict): cursor.execute("REPLACE INTO job_specs VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?)", (job_id, specs.get('nationality', 'N/A'), specs.get('age_limits', 'N/A'), specs.get('age_relax', 'N/A'), specs.get('edu_qual', 'N/A'), specs.get('attempts', 'N/A'), specs.get('physical_std', 'N/A'), now_timestamp)); updated_sections.append("specs")
                    
                if update_needs['pattern']:
                    pattern = exam_data.get('exam_pattern', {});
                    if isinstance(pattern, dict): cursor.execute("REPLACE INTO exam_pattern VALUES (NULL, ?, ?, ?, ?, ?, ?, ?)", (job_id, pattern.get('stages', 'N/A'), pattern.get('num_papers', 'N/A'), pattern.get('q_type', 'N/A'), pattern.get('duration', 'N/A'), pattern.get('marking_scheme', 'N/A'), now_timestamp)); updated_sections.append("pattern")
                    
                if update_needs['cutoffs']:
                    cutoffs = exam_data.get('cutoffs', [])
                    if isinstance(cutoffs, list):
                        cursor.execute("DELETE FROM job_cutoffs WHERE job_id = ?", (job_id,)); year = exam_data.get('year', 'N/A')
                        for cutoff in cutoffs:
                            if isinstance(cutoff, dict): cursor.execute("INSERT INTO job_cutoffs VALUES (NULL, ?, ?, ?, ?)", (job_id, cutoff.get('category', 'N/A'), cutoff.get('score', 'N/A'), year))
                        updated_sections.append("cutoffs")
                        
                if updated_sections: print(f"      ✅ Updated sections: {', '.join(updated_sections)}"); batch_success = True
                else: print(f"      No fields needed updating.")
            except sqlite3.Error as e: print(f"      ❌ DB Error: {e}"); conn.rollback(); continue
            
        conn.commit()
        if batch_success: consecutive_errors = 0
        else: consecutive_errors += 1
        if consecutive_errors >= 2: print("🛑 Stopping..."); return False
        if i + BATCH_SIZE < len(jobs_to_fetch_for): print(f"\n...Pausing for 30 seconds..."); time.sleep(30)
    print("\n--- Phase 1 Finished ---")
    return True

# --- Phase 2: Find and Add New Jobs ---
def find_and_add_new_jobs(conn: sqlite3.Connection):
    # (Same logical flow as before)
    cursor = conn.cursor()
    print("\n--- Phase 2: Searching for new job postings ---")
    existing_exams = [row['exam_name'] for row in cursor.execute("SELECT DISTINCT exam_name FROM jobs").fetchall()]
    new_jobs_results = ask_gemini_batch(existing_exams, find_new=True)
    
    if not new_jobs_results: print("   No new job postings found."); return
    added_count = 0
    for new_job_data in new_jobs_results:
        if not isinstance(new_job_data, dict) or not new_job_data.get('exam_name'): continue
        new_exam_name = new_job_data['exam_name']; is_truly_new = True
        for existing in existing_exams:
             if new_exam_name.lower() == existing.lower(): is_truly_new = False; break
        if is_truly_new:
            print(f"   ✨ Found: {new_job_data.get('post_name')} ({new_exam_name})")
            try:
                cursor.execute(
                    '''INSERT OR IGNORE INTO jobs (post_name, exam_name, conducting_body, "group", gazetted_status, pay_level, salary, eligibility, age_limit, pet_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (new_job_data.get('post_name', 'N/A'), new_exam_name, new_job_data.get('conducting_body', 'N/A'), new_job_data.get('group', 'N/A'), new_job_data.get('gazetted_status', 'N/A'), new_job_data.get('pay_level', 0), new_job_data.get('salary', 'N/A'), new_job_data.get('eligibility', 'N/A'), new_job_data.get('age_limit', 'N/A'), new_job_data.get('pet_status', 'N/A'))
                )
                if cursor.rowcount > 0:
                     added_count += 1; new_job_id = cursor.lastrowid
                     cursor.execute("INSERT OR IGNORE INTO job_specs (job_id) VALUES (?)", (new_job_id,))
                     cursor.execute("INSERT OR IGNORE INTO exam_pattern (job_id) VALUES (?)", (new_job_id,))
                else: print(f"      (Skipped {new_exam_name})")
            except sqlite3.Error as e: print(f"      ❌ DB Error adding {new_exam_name}: {e}"); conn.rollback()
    conn.commit()
    if added_count > 0: print(f"\n   Added {added_count} new jobs!")
    else: print("   No new jobs added.")
    print("\n--- Phase 2 Finished ---")

# --- Main Execution Logic ---
if __name__ == '__main__':
    open(STATUS_FLAG_FILE, 'w').close()
    print("🚀 Starting Smart Data Scout...\n")
    conn_main = get_db_connection()
    try:
        update_success = update_existing_jobs(conn_main)
        if update_success:
            find_and_add_new_jobs(conn_main)
    except Exception as e:
         print(f"🚨 An unexpected error occurred: {e}")
    finally:
        conn_main.close()
        if os.path.exists(STATUS_FLAG_FILE): os.remove(STATUS_FLAG_FILE)
        print("\nMission Complete! 'update_in_progress.flag' removed. ✅")
