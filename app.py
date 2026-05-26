import os
import json
import sqlite3
from datetime import datetime, date

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash

import google.oauth2.credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

from lunar_utils import lunar_to_solar, generate_solar_dates, LUNAR_MONTHS_VI

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'lunar-calendar-local-dev-key')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'events.db')
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')
TOKEN_FILE = os.path.join(BASE_DIR, 'token.json')
SCOPES = ['https://www.googleapis.com/auth/calendar']


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            lunar_month INTEGER NOT NULL,
            lunar_day INTEGER NOT NULL,
            is_leap INTEGER DEFAULT 0,
            reminder_days INTEGER DEFAULT 7,
            description TEXT DEFAULT '',
            start_year INTEGER NOT NULL,
            end_year INTEGER NOT NULL,
            cc_emails TEXT DEFAULT '',
            synced_to_google INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try:
        c.execute('ALTER TABLE events ADD COLUMN cc_emails TEXT DEFAULT ""')
        conn.commit()
    except sqlite3.OperationalError:
        pass
    c.execute('''
        CREATE TABLE IF NOT EXISTS google_event_ids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            google_event_id TEXT NOT NULL,
            solar_year INTEGER NOT NULL,
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
    ''')
    conn.commit()
    conn.close()


def get_google_creds():
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE) as f:
        data = json.load(f)
    creds = google.oauth2.credentials.Credentials(
        token=data.get('token'),
        refresh_token=data.get('refresh_token'),
        token_uri=data.get('token_uri'),
        client_id=data.get('client_id'),
        client_secret=data.get('client_secret'),
        scopes=data.get('scopes'),
    )
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_google_creds(creds)
        except Exception:
            os.remove(TOKEN_FILE)
            return None
    return creds


def save_google_creds(creds):
    with open(TOKEN_FILE, 'w') as f:
        json.dump({
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': list(creds.scopes),
        }, f)


@app.route('/')
def index():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM events ORDER BY lunar_month, lunar_day')
    rows = c.fetchall()
    conn.close()

    today = date.today()
    events = []
    for row in rows:
        ev = dict(row)
        # Find next upcoming solar date
        next_date = None
        for yr in [today.year, today.year + 1]:
            sd = lunar_to_solar(yr, row['lunar_month'], row['lunar_day'], bool(row['is_leap']))
            if sd and sd >= today:
                next_date = sd
                break
        ev['next_date'] = next_date.strftime('%d/%m/%Y') if next_date else '—'
        ev['next_date_iso'] = next_date.isoformat() if next_date else ''
        ev['month_name'] = LUNAR_MONTHS_VI.get(row['lunar_month'], str(row['lunar_month']))
        events.append(ev)

    is_google_auth = get_google_creds() is not None
    has_credentials_file = os.path.exists(CREDENTIALS_FILE)
    current_year = today.year

    return render_template('index.html',
                           events=events,
                           is_google_auth=is_google_auth,
                           has_credentials_file=has_credentials_file,
                           current_year=current_year,
                           lunar_months=LUNAR_MONTHS_VI)


@app.route('/preview', methods=['POST'])
def preview():
    data = request.json
    try:
        results = generate_solar_dates(
            int(data['lunar_month']),
            int(data['lunar_day']),
            int(data['start_year']),
            int(data['end_year']),
            bool(data.get('is_leap', False)),
            int(data.get('reminder_days', 7)),
        )
        return jsonify({'success': True, 'dates': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/check-duplicate', methods=['POST'])
def check_duplicate():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT id, name FROM events
        WHERE lunar_month = ? AND lunar_day = ? AND is_leap = ?
    ''', (int(data['lunar_month']), int(data['lunar_day']), 1 if data.get('is_leap') else 0))
    existing = c.fetchall()
    conn.close()
    return jsonify({'duplicates': [{'id': r['id'], 'name': r['name']} for r in existing]})


@app.route('/save-event', methods=['POST'])
def save_event():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    cc_emails = ','.join(
        e.strip() for e in data.get('cc_emails', '').split(',') if e.strip()
    )
    c.execute('''
        INSERT INTO events (name, lunar_month, lunar_day, is_leap, reminder_days, description, start_year, end_year, cc_emails)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['name'].strip(),
        int(data['lunar_month']),
        int(data['lunar_day']),
        1 if data.get('is_leap') else 0,
        int(data.get('reminder_days', 7)),
        data.get('description', '').strip(),
        int(data['start_year']),
        int(data['end_year']),
        cc_emails,
    ))
    event_id = c.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'id': event_id})


@app.route('/delete-event/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Lấy danh sách Google Calendar event IDs nếu đã sync
    c.execute('SELECT google_event_id FROM google_event_ids WHERE event_id = ?', (event_id,))
    gcal_ids = [r['google_event_id'] for r in c.fetchall()]

    c.execute('DELETE FROM google_event_ids WHERE event_id = ?', (event_id,))
    c.execute('DELETE FROM events WHERE id = ?', (event_id,))
    conn.commit()
    conn.close()

    # Xóa trên Google Calendar nếu có
    gcal_deleted = 0
    gcal_errors = []
    if gcal_ids:
        creds = get_google_creds()
        if creds:
            service = build('calendar', 'v3', credentials=creds)
            for gid in gcal_ids:
                try:
                    service.events().delete(calendarId='primary', eventId=gid).execute()
                    gcal_deleted += 1
                except Exception as e:
                    gcal_errors.append(str(e))

    return jsonify({'success': True, 'gcal_deleted': gcal_deleted, 'gcal_errors': gcal_errors})


@app.route('/gcal-search-delete/<int:event_id>', methods=['POST'])
def gcal_search_delete(event_id):
    """Tìm kiếm và xóa toàn bộ events trên Google Calendar theo tên — dùng khi chưa có event IDs."""
    creds = get_google_creds()
    if not creds:
        return jsonify({'error': 'Chưa đăng nhập Google'}), 401

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM events WHERE id = ?', (event_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Không tìm thấy sự kiện'}), 404

    leap_str = ' (nhuận)' if row['is_leap'] else ''
    search_query = f"{row['name']} ({row['lunar_day']}/{row['lunar_month']}{leap_str} ÂL)"

    service = build('calendar', 'v3', credentials=creds)
    deleted = 0
    errors = []
    page_token = None

    while True:
        resp = service.events().list(
            calendarId='primary',
            q=search_query,
            maxResults=250,
            pageToken=page_token,
            fields='items(id,summary),nextPageToken',
        ).execute()

        for ev in resp.get('items', []):
            if ev.get('summary', '').strip() == search_query:
                try:
                    service.events().delete(calendarId='primary', eventId=ev['id']).execute()
                    deleted += 1
                except Exception as e:
                    errors.append(str(e))

        page_token = resp.get('nextPageToken')
        if not page_token:
            break

    save_google_creds(creds)
    return jsonify({'success': True, 'deleted': deleted, 'errors': errors})


@app.route('/sync-to-google/<int:event_id>', methods=['POST'])
def sync_to_google(event_id):
    creds = get_google_creds()
    if not creds:
        return jsonify({'error': 'Chưa đăng nhập Google'}), 401

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM events WHERE id = ?', (event_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'Không tìm thấy sự kiện'}), 404

    solar_dates = generate_solar_dates(
        row['lunar_month'], row['lunar_day'],
        row['start_year'], row['end_year'],
        bool(row['is_leap']), row['reminder_days'],
    )

    service = build('calendar', 'v3', credentials=creds)
    leap_str = ' (nhuận)' if row['is_leap'] else ''
    cc_list = [e.strip() for e in (row['cc_emails'] or '').split(',') if e.strip()]
    attendees = [{'email': e} for e in cc_list]
    created = 0
    errors = []
    first_link = ''
    google_event_ids = []

    for entry in solar_dates:
        description_parts = [
            f"Ngày âm lịch: {entry['lunar_str']} năm {entry['can_chi']}",
            f"Nhắc nhở trước: {row['reminder_days']} ngày",
        ]
        if row['description']:
            description_parts.append(row['description'])
        if cc_list:
            description_parts.append(f"Thông báo đến: {', '.join(cc_list)}")

        event_body = {
            'summary': f"{row['name']} ({row['lunar_day']}/{row['lunar_month']}{leap_str} ÂL)",
            'description': '\n'.join(description_parts),
            'start': {'date': entry['solar_date']},
            'end': {'date': entry['solar_date']},
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': row['reminder_days'] * 24 * 60},
                    {'method': 'popup', 'minutes': 0},
                    {'method': 'email', 'minutes': row['reminder_days'] * 24 * 60},
                ],
            },
        }
        if attendees:
            event_body['attendees'] = attendees

        try:
            result = service.events().insert(
                calendarId='primary',
                body=event_body,
                sendUpdates='all' if attendees else 'none',
            ).execute()
            created += 1
            if created == 1:
                first_link = result.get('htmlLink', '')
            google_event_ids.append((event_id, result['id'], entry['lunar_year']))
        except Exception as e:
            errors.append(str(e))

    save_google_creds(creds)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE events SET synced_to_google = 1 WHERE id = ?', (event_id,))
    if google_event_ids:
        c.execute('DELETE FROM google_event_ids WHERE event_id = ?', (event_id,))
        c.executemany(
            'INSERT INTO google_event_ids (event_id, google_event_id, solar_year) VALUES (?, ?, ?)',
            google_event_ids,
        )
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'created': created, 'errors': errors, 'first_link': first_link})


@app.route('/auth/google')
def auth_google():
    if not os.path.exists(CREDENTIALS_FILE):
        return redirect(url_for('index') + '?error=no_credentials')

    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
        redirect_uri=url_for('auth_callback', _external=True),
    )
    auth_url, state = flow.authorization_url(access_type='offline', prompt='consent')
    session['oauth_state'] = state
    session['code_verifier'] = flow.code_verifier
    return redirect(auth_url)


@app.route('/auth/callback')
def auth_callback():
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
        state=session.get('oauth_state'),
        redirect_uri=url_for('auth_callback', _external=True),
    )
    flow.code_verifier = session.pop('code_verifier', None)
    flow.fetch_token(authorization_response=request.url)
    save_google_creds(flow.credentials)
    return redirect(url_for('index') + '?msg=google_connected')


@app.route('/auth/logout')
def auth_logout():
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
    return redirect(url_for('index'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001, host='0.0.0.0')
