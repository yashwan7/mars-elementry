#!/usr/bin/env python3
"""
AlgoX Mars Colony Emergency Response — Web Interface
Upload CSV → Solve → View Score + Gantt Chart → Download JSON
"""

from flask import Flask, render_template, request, jsonify
import os, json, tempfile
from solver import load_incidents, solve

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/solve', methods=['POST'])
def solve_endpoint():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '' or not file.filename.endswith('.csv'):
        return jsonify({'error': 'Please upload a .csv file'}), 400

    tmp = tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False)
    try:
        file.save(tmp.name)
        tmp.close()

        sa_time = float(request.form.get('sa_time', 15))
        seed = int(request.form.get('seed', 42))

        incidents = load_incidents(tmp.name)
        score, schedule, submission, stats = solve(incidents, sa_seconds=sa_time, seed=seed)

        return jsonify({
            'score': score,
            'schedule': schedule,
            'submission': {'schedule': submission},
            'stats': stats,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        os.unlink(tmp.name)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)

