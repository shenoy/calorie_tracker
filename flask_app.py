from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from authlib.integrations.flask_client import OAuth

import os

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'

# 1. Database Config
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://rajeshtshenoy:Dogcatbunny123!@rajeshtshenoy.mysql.pythonanywhere-services.com/rajeshtshenoy$compoundeffectcalories'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_recycle': 280}
db = SQLAlchemy(app)

# 2. Database Models
class CalorieEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    food_item = db.Column(db.String(100), nullable=False)
    user_email = db.Column(db.String(120), nullable=False)
    calories = db.Column(db.Integer, nullable=False)
    protein = db.Column(db.Float, default=0.0) # <--- Added Protein
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

class FoodLibrary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    calories_per_100g = db.Column(db.Integer, nullable=False)
    protein_per_100g = db.Column(db.Float, default=0.0) # <--- Added Protein
    user_email = db.Column(db.String(120), nullable=False)

class QuickAddFood(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    calories = db.Column(db.Integer, nullable=False)
    protein = db.Column(db.Float, default=0.0) # <--- Added Protein
    user_email = db.Column(db.String(120), nullable=False)

class QuickFoodStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    food_name = db.Column(db.String(100), unique=True)
    click_count = db.Column(db.Integer, default=0)
    user_email = db.Column(db.String(120), nullable=False)

class WeightEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    weight = db.Column(db.Float, nullable=False)
    date_recorded = db.Column(db.Date, default=date.today)
    user_email = db.Column(db.String(120), nullable=False)


# 3. Routes
@app.route('/', methods=['GET', 'POST'])
def index():
    # 1. AUTH CHECK: Redirect to login if not authenticated
    if 'user' not in session:
        return redirect(url_for('login'))

    # Get the unique identifier for the logged-in user
    user_email = session['user']['email']

    DAILY_GOAL = 1700
    today = date.today()

    # Handle Food Logging (Quick Add or Custom Add)
    if request.method == 'POST':
        food = request.form.get('food')
        cals = request.form.get('calories')
        # Use 0.0 as default for protein if not provided
        prot = request.form.get('protein', 0)

        if food and cals:
            # Update Click Stats for reordering Quick Add buttons
            stat = QuickFoodStats.query.filter_by(food_name=food,user_email=user_email).first()
            if not stat:
                stat = QuickFoodStats(food_name=food, click_count=1, user_email=user_email)
                db.session.add(stat)
            else:
                stat.click_count += 1

            # Ensure data types are correct for the DB
            new_entry = CalorieEntry(
                food_item=food,
                calories=int(float(cals)),
                protein=float(prot),
                user_email=user_email
            )
            db.session.add(new_entry)
            db.session.commit()
        return redirect('/')

    # --- UPDATED DATA FETCHING ---
    try:
        library_items = FoodLibrary.query.filter_by(user_email=user_email).order_by(FoodLibrary.name.asc()).all()
        # FIX: Structure the dict to hold [Calories, Protein]
        food_db = {item.name: [item.calories_per_100g, item.protein_per_100g] for item in library_items}
    except:
        food_db = {}

    dynamic_quick_foods = QuickAddFood.query.filter_by(user_email=user_email).all()
    stats_query = QuickFoodStats.query.filter_by(user_email=user_email).all()
    stats = {s.food_name: s.click_count for s in stats_query}
    sorted_foods = sorted(dynamic_quick_foods, key=lambda x: stats.get(x.name, 0), reverse=True)

    # Current Day's Data
    entries = CalorieEntry.query.filter(
        db.func.date(CalorieEntry.date_created) == today,
        CalorieEntry.user_email == user_email
    ).all()
    total_calories = sum(entry.calories for entry in entries)
    total_protein = round(sum(entry.protein for entry in entries), 1) # Rounded for clean UI
    remaining = DAILY_GOAL - total_calories

    weight_entry = WeightEntry.query.filter_by(date_recorded=today, user_email=user_email).first()
    current_weight = weight_entry.weight if weight_entry else "Not set"

    return render_template('index.html',
                           entries=entries,
                           total=total_calories,
                           total_protein=total_protein,
                           goal=DAILY_GOAL,
                           remaining=remaining,
                           quick_foods=sorted_foods,
                           all_quick_add_items=dynamic_quick_foods,
                           library_items_list=library_items,
                           current_weight=current_weight,
                           food_db=food_db)

@app.route('/add_quick_add', methods=['POST'])
def add_quick_add():
    if 'user' not in session:
        return redirect(url_for('login'))

    user_email = session['user']['email']
    name = request.form.get('name')
    cals = request.form.get('calories')
    prot = request.form.get('protein', 0)

    if name and cals:
        existing_item = QuickAddFood.query.filter_by(name=name, user_email=user_email).first()
        if existing_item:
            existing_item.calories = int(cals)
            existing_item.protein = float(prot)
        else:
            # ADDED user_email=user_email HERE
            new_item = QuickAddFood(name=name, calories=int(cals),
                                    protein=float(prot), user_email=user_email)
            db.session.add(new_item)

        db.session.commit()
    return redirect('/manage_quick_add')

@app.route('/delete_quick_add/<int:item_id>')
def delete_quick_add(item_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    user_email = session['user']['email']
    item = QuickAddFood.query.filter_by(id=item_id, user_email=user_email).first_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return redirect('/')


@app.route('/delete/<int:id>')
def delete(id):
    if 'user' not in session:
        return redirect(url_for('login'))

    user_email = session['user']['email']
    entry_to_delete = CalorieEntry.query.filter_by(id=id, user_email=user_email).first_or_404(id)
    try:
        db.session.delete(entry_to_delete)
        db.session.commit()
        return redirect('/')
    except:
        return "There was a problem deleting that entry."

@app.route('/history')
def history():
    # 1. AUTH CHECK: Redirect to login if not authenticated
    if 'user' not in session:
        return redirect(url_for('login'))

    user_email = session['user']['email']
    search_query = request.args.get('search')

    # 2. FILTER BY USER: Only fetch logs belonging to THIS user
    if search_query:
        all_entries = CalorieEntry.query.filter(
            CalorieEntry.user_email == user_email, # <--- Added this
            CalorieEntry.food_item.contains(search_query)
        ).order_by(CalorieEntry.date_created.desc()).all()
    else:
        all_entries = CalorieEntry.query.filter_by(
            user_email=user_email # <--- Added this
        ).order_by(CalorieEntry.date_created.desc()).all()

    history_data = {}
    for entry in all_entries:
        day = entry.date_created.date()
        if day not in history_data:
            history_data[day] = []
        history_data[day].append(entry)

    # sorted_days = sorted(history_data.keys())
    # cal_labels = [d.strftime('%m-%d') for d in sorted_days]
    # cal_values = [sum(e.calories for e in history_data[d]) for d in sorted_days]
    # prot_values = [round(sum(e.protein for e in history_data[d]), 1) for d in sorted_days]

    # # 3. FILTER WEIGHT BY USER: Secure the weight chart too
    # weights = WeightEntry.query.filter_by(
    #     user_email=user_email # <--- Added this
    # ).order_by(WeightEntry.date_recorded.asc()).all()

    # weight_labels = [w.date_recorded.strftime('%m-%d') for w in weights]
    # weight_values = [w.weight for w in weights]
    # return render_template('history.html',
    #                   history_data=history_data,
    #                   labels=weight_labels,
    #                   values=weight_values,
    #                   cal_labels=cal_labels,
    #                   cal_values=cal_values,
    #                   prot_values=prot_values,
    #                   search_query=search_query,
    #                   today=date.today().isoformat())
    sorted_days = sorted(history_data.keys())
    cal_labels = [d.strftime('%m-%d') for d in sorted_days]
    cal_dates_iso = [d.isoformat() for d in sorted_days]          # <-- add this
    cal_values = [sum(e.calories for e in history_data[d]) for d in sorted_days]
    prot_values = [round(sum(e.protein for e in history_data[d]), 1) for d in sorted_days]

    # 3. FILTER WEIGHT BY USER: Secure the weight chart too
    weights = WeightEntry.query.filter_by(
        user_email=user_email
    ).order_by(WeightEntry.date_recorded.asc()).all()

    weight_labels = [w.date_recorded.strftime('%m-%d') for w in weights]
    weight_dates_iso = [w.date_recorded.isoformat() for w in weights]   # <-- add this
    weight_values = [w.weight for w in weights]

    return render_template('history.html',
                       history_data=history_data,
                       labels=weight_labels,
                       weight_dates_iso=weight_dates_iso,        # <-- add this
                       values=weight_values,
                       cal_labels=cal_labels,
                       cal_dates_iso=cal_dates_iso,               # <-- add this
                       cal_values=cal_values,
                       prot_values=prot_values,
                       search_query=search_query,
                       today=date.today().isoformat())

@app.route('/update_weight', methods=['POST'])
def update_weight():
    if 'user' not in session:
        return redirect(url_for('login'))

    user_email = session['user']['email']
    new_weight = request.form.get('weight')
    if new_weight:
        entry = WeightEntry.query.filter_by(date_recorded=date.today(), user_email=user_email).first()
        if entry:
            entry.weight = float(new_weight)
        else:
            # ADDED user_email=user_email HERE
            entry = WeightEntry(weight=float(new_weight), user_email=user_email)
            db.session.add(entry)
        db.session.commit()
    return redirect('/')


@app.route('/add_to_library', methods=['POST'])
def add_to_library():
    if 'user' not in session:
        return redirect(url_for('login'))

    user_email = session['user']['email']
    name = request.form.get('library_name')
    cals = request.form.get('library_cals')
    prot = request.form.get('library_protein')

    if name and cals:
        existing_food = FoodLibrary.query.filter_by(name=name, user_email=user_email).first()
        if existing_food:
            existing_food.calories_per_100g = int(cals)
            existing_food.protein_per_100g = float(prot)
        else:
            # ADDED user_email=user_email HERE
            new_food = FoodLibrary(name=name, calories_per_100g=int(cals),
                                   protein_per_100g=float(prot), user_email=user_email)
            db.session.add(new_food)

        db.session.commit()
    return redirect('/manage_library')

@app.route('/delete_library_item/<int:item_id>')
def delete_library_item(item_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    user_email = session['user']['email']
    item_to_delete = FoodLibrary.query.filter_by(id=item_id, user_email=user_email).first_or_404()
    try:
        db.session.delete(item_to_delete)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return f"Error: {str(e)}"
    return redirect('/')

@app.route('/manage_quick_add')
def manage_quick_add():
    if 'user' not in session:
        return redirect(url_for('login'))

    user_email = session['user']['email']
    dynamic_quick_foods = QuickAddFood.query.filter_by(user_email=user_email).all()
    # We pass all_habits so the navigation bar still works
    # all_habits = Habit.query.all()
    return render_template('manage_quick_add.html',
                           all_quick_add_items=dynamic_quick_foods)

@app.route('/manage_library')
def manage_library():
    if 'user' not in session:
        return redirect(url_for('login'))

    user_email = session['user']['email']
    library_items = FoodLibrary.query.filter_by(user_email=user_email).order_by(FoodLibrary.name.asc()).all()
    # all_habits = Habit.query.all()
    return render_template('manage_library.html',
                           library_items_list=library_items)

@app.route('/sync_history_fuzzy')
def sync_history_fuzzy():
    # Find all history logs that currently have 0 protein
    entries_to_fix = CalorieEntry.query.filter_by(protein=0.0).all()
    updated_count = 0

    # Get all your library items
    all_library = FoodLibrary.query.all()

    for entry in entries_to_fix:
        for lib_item in all_library:
            # Check if "Sardines" is inside "Sardines (240g)"
            # We use .lower() just in case capitalization is different
            if lib_item.name.lower() in entry.food_item.lower():

                if lib_item.calories_per_100g > 0:
                    # Reverse-engineer the weight based on calories logged
                    ratio = entry.calories / lib_item.calories_per_100g
                    entry.protein = round(ratio * lib_item.protein_per_100g, 1)
                    updated_count += 1
                    break # Stop looking for this specific entry once matched

    db.session.commit()
    return f"Success! Updated {updated_count} entries using fuzzy matching."

@app.route('/privacy')
def privacy_policy():
    # This renders the html file we will create in the next step
    return render_template('privacy.html')

# 1. Initialize OAuth
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# 2. Create the Login Route
@app.route('/login')
def login():
    redirect_uri = url_for('auth', _external=True)
    return google.authorize_redirect(redirect_uri)

# 3. Create the Callback Route
@app.route('/authorize')
def auth():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    if user_info:
        # This is the line that prevents the loop!
        session['user'] = user_info
        # Optional: session.permanent = True
    return redirect(url_for('index'))

@app.route('/add_historical', methods=['POST'])
def add_historical():
    if 'user' not in session:
        return redirect(url_for('login'))

    user_email = session['user']['email']
    food = request.form.get('food')
    cals = request.form.get('calories')
    prot = request.form.get('protein', 0)
    entry_date = request.form.get('entry_date')  # expects 'YYYY-MM-DD' from <input type="date">

    if food and cals and entry_date:
        try:
            parsed_date = datetime.strptime(entry_date, '%Y-%m-%d')
        except ValueError:
            return redirect(url_for('history'))

        # Keep a real time-of-day on the record (rather than midnight)
        # so it still sorts/displays sensibly if you ever show times.
        now = datetime.utcnow()
        entry_datetime = parsed_date.replace(hour=now.hour, minute=now.minute, second=now.second)

        new_entry = CalorieEntry(
            food_item=food,
            calories=int(float(cals)),
            protein=float(prot),
            user_email=user_email,
            date_created=entry_datetime
        )
        db.session.add(new_entry)
        db.session.commit()

    return redirect(url_for('history'))


if __name__ == "__main__":
    app.run(debug=True)
