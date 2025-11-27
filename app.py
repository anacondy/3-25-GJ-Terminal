# app.py
# --- FINAL version: Robust Flask Server for GJ Terminal ---

from flask import Flask, render_template, jsonify
import sqlite3
import os

# --- Find project files ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'jobs.db')
STATUS_FLAG_FILE = os.path.join(BASE_DIR, 'update_in_progress.flag')

app = Flask(__name__)
# Disable caching for development to ensure updates are seen immediately
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True

# --- Database Connection ---
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # Access columns by name
    return conn

# --- Main Page Route ---
@app.route('/')
def index():
    # Check if the data scout is currently running
    is_updating = os.path.exists(STATUS_FLAG_FILE)
    
    conn = get_db_connection()
    # Fetch summary data for the main table
    jobs = conn.execute('SELECT id, post_name, exam_name, conducting_body, "group", gazetted_status, pay_level, salary, eligibility, age_limit, pet_status FROM jobs ORDER BY id').fetchall()
    conn.close()
    
    return render_template('index.html', jobs=jobs, is_updating=is_updating)

# --- Details Page Route ---
@app.route('/details/<int:job_id>')
def details(job_id):
    conn = get_db_connection()
    
    # Fetch main job details
    job = conn.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
    if not job: 
        conn.close()
        return "Job not found", 404
    
    # Fetch related data from other tables
    job_spec = conn.execute('SELECT * FROM job_specs WHERE job_id = ?', (job_id,)).fetchone()
    exam_pattern = conn.execute('SELECT * FROM exam_pattern WHERE job_id = ?', (job_id,)).fetchone()
    
    # Fetch and sort cutoffs logically
    job_cutoffs = conn.execute('''
        SELECT category, score, year FROM job_cutoffs WHERE job_id = ?
        ORDER BY CASE 
            WHEN category LIKE '%UR%' OR category LIKE '%General%' THEN 1 
            WHEN category LIKE '%EWS%' THEN 2 
            WHEN category LIKE '%OBC%' THEN 3 
            WHEN category LIKE '%SC%' THEN 4 
            WHEN category LIKE '%ST%' THEN 5 
            ELSE 6 
        END
    ''', (job_id,)).fetchall()
    
    conn.close()
    
    return render_template('details.html', job=job, job_spec=job_spec, exam_pattern=exam_pattern, cutoffs=job_cutoffs)

# --- Status Endpoint for the Green Dot ---
@app.route('/update_status')
def update_status():
    """API endpoint for the frontend to check if an update is running."""
    is_updating = os.path.exists(STATUS_FLAG_FILE)
    return jsonify({'updating': is_updating})

# --- Start the Server ---
if __name__ == '__main__':
    app.run(debug=True)
