from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, Response
import os
import uuid
import json
import datetime
import random
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
from database import users_collection, pending_users_collection, bookings_collection, sell_requests_collection, purchase_requests_collection, transactions_collection, fetched_tickets_collection
from utils import generate_otp, send_email_emailjs, send_notification_email_emailjs, predict_flight_time, login_user, hash_password, check_password, get_lowest_price_suggestion
from pdf_utils import generate_ticket_pdf, generate_report_pdf
from external_inventory_client import ExternalInventoryClient
import threading
from external_inventory_app import start_inventory_app

load_dotenv()

# Start External Inventory App in background thread
try:
    threading.Thread(target=start_inventory_app, daemon=True).start()
    print("Started External Inventory GDS Simulator on http://127.0.0.1:5001")
except Exception as e:
    print(f"Error starting background inventory thread: {e}")


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")

# --- Routes ---

def flash_success(message):
    flash(message, "success")


def flash_error(message):
    flash(message, "error")


def password_strength(password):
    score = 0
    score += len(password) >= 8
    score += any(char.isupper() for char in password)
    score += any(char.islower() for char in password)
    score += any(char.isdigit() for char in password)
    score += any(char in "!@#$%^&*" for char in password)

    if score <= 2:
        return "weak"
    if score <= 4:
        return "medium"
    return "strong"


def format_transaction(txn):
    txn["_id"] = str(txn.get("_id", ""))
    created_at = txn.get("created_at")
    if isinstance(created_at, datetime.datetime):
        txn["created_at_display"] = created_at.strftime("%d %b %Y, %I:%M %p")
        txn["_sort_date"] = created_at
    else:
        txn["created_at_display"] = "Not recorded"
        txn["_sort_date"] = datetime.datetime.min
    return txn

@app.route('/')
def index():
    if 'user' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        name = request.form['name']
        
        # Check if user already exists
        if users_collection.find_one({"email": email}):
            flash_error("User already exists")
            return redirect(url_for('register'))
            
        try:
            # Generate OTP
            otp = generate_otp()
            temp_id = str(uuid.uuid4())
            
            # Store temp user data in MongoDB (including OTP)
            pending_users_collection.update_one(
                {'email': email},
                {'$set': {
                    'temp_id': temp_id,
                    'email': email,
                    'password': hash_password(password), # Store hashed password
                    'name': name,
                    'otp': otp,
                    'created_at': datetime.datetime.now()
                }},
                upsert=True
            )
            
            # Send OTP
            if send_email_emailjs(email, otp):
                session['pending_email'] = email
                flash_success("Verification code sent successfully")
                return redirect(url_for('verify_otp'))
            else:
                flash_error("Failed to send OTP")
                return redirect(url_for('register'))
                
        except Exception as e:
            flash_error(f"Error: {e}")
            return redirect(url_for('register'))
            
    return render_template('register.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if 'pending_email' not in session:
        return redirect(url_for('register'))
        
    if request.method == 'POST':
        entered_otp = request.form['otp']
        email = session['pending_email']
        
        # Verify OTP from MongoDB
        data = pending_users_collection.find_one({"email": email})
        
        if data:
            if data['otp'] == entered_otp:
                # OTP Match -> Create User
                user_uid = str(uuid.uuid4())
                users_collection.insert_one({
                    'uid': user_uid,
                    'email': data['email'],
                    'password': data['password'], # Already hashed
                    'name': data['name'],
                    'phone': '',
                    'role': 'user',
                    'is_blocked': False,
                    'created_at': datetime.datetime.now()
                })
                
                # Cleanup
                pending_users_collection.delete_one({"email": email})
                session.pop('pending_email', None)
                
                flash_success("Account created successfully")
                return redirect(url_for('index')) # Login page
            else:
                flash_error("Invalid OTP")
                return redirect(url_for('verify_otp'))
        else:
            flash_error("Session expired")
            return redirect(url_for('register'))

    return render_template('otp.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']
    
    # 1. Admin Login: If password is the master admin password, log in as admin with the entered email
    if password == 'StrongPassword@2026':
        otp = generate_otp()
        session['admin_pending'] = True
        session['admin_email'] = email
        session['admin_otp'] = otp
        session['admin_otp_time'] = datetime.datetime.now().timestamp()
        
        # Check if the user exists in DB to use their name, otherwise default
        existing_user = users_collection.find_one({"email": email})
        admin_name = existing_user.get('name', 'Administrator') if existing_user else 'Administrator'
        
        session['admin_user_data'] = {
            'uid': str(existing_user.get('uid')) if existing_user else 'admin',
            'email': email,
            'name': admin_name,
            'role': 'admin'
        }
        
        print(f"\n========================================\n[ADMIN OTP] Code is: {otp}\n========================================\n")
        
        if send_email_emailjs(email, otp):
            flash_success(f"OTP sent to {email}")
            return redirect(url_for('admin_verify_otp'))
        else:
            flash_success(f"[DEV] OTP sent (logged to terminal): {otp}")
            return redirect(url_for('admin_verify_otp'))
            
    # 2. Regular User Login via MongoDB lookup
    user_data = users_collection.find_one({"email": email})
    if user_data and check_password(user_data['password'], password):
        if user_data.get('is_blocked', False):
            flash_error("Your account is blocked by admin")
            return redirect(url_for('index'))
            
        session_user = {
            'uid': str(user_data.get('uid')),
            'email': user_data['email'],
            'name': user_data['name'],
            'role': user_data.get('role', 'user')
        }
        session['user'] = session_user
        session['role'] = session_user['role']
        return redirect(url_for('dashboard'))
    
    print(f"[LOGIN] Failed for: {email}")
    flash_error("Invalid credentials")
    return redirect(url_for('index'))

@app.route('/admin/verify-otp', methods=['GET', 'POST'])
def admin_verify_otp():
    if not session.get('admin_pending'):
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        entered_otp = request.form['otp']
        stored_otp = session.get('admin_otp')
        otp_time = session.get('admin_otp_time', 0)
        
        # OTP valid for 60 seconds
        if datetime.datetime.now().timestamp() - otp_time > 60:
            session.pop('admin_pending', None)
            session.pop('admin_otp', None)
            session.pop('admin_user_data', None)
            flash_error("OTP expired. Please login again.")
            return redirect(url_for('index'))
            
        if entered_otp == stored_otp:
            user_data = session.get('admin_user_data', {
                'uid': 'admin',
                'email': session.get('admin_email'),
                'name': 'Administrator',
                'role': 'admin'
            })
            session['user'] = user_data
            session['role'] = 'admin'
            session.pop('admin_pending', None)
            session.pop('admin_otp', None)
            session.pop('admin_user_data', None)
            return redirect(url_for('admin_dashboard'))
        else:
            flash_error("Invalid OTP")
            return redirect(url_for('admin_verify_otp'))

    return render_template('otp.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user' not in session:
        return redirect(url_for('index'))
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))
        
    prediction = None
    flights = []
    lowest_flight = None
    origin = ''
    destination = ''
    
    if request.method == 'POST':
        origin = request.form['origin']
        destination = request.form['destination']
        prediction = predict_flight_time(origin, destination)
        
        # Query from fetched published tickets and filter in Python for database cross-compatibility
        all_published = list(fetched_tickets_collection.find({"ticket_status": "Published"}))
        for ticket in all_published:
            t_origin = ticket.get("departure_city", "").strip().lower()
            t_dest = ticket.get("destination_city", "").strip().lower()
            if t_origin == origin.strip().lower() and t_dest == destination.strip().lower():
                price = ticket.get("resale_price", 0) if ticket.get("resale_price", 0) > 0 else ticket.get("original_price", 0)
                flights.append({
                    "ticket_id": ticket.get("ticket_id"),
                    "flight_number": ticket.get("flight_number"),
                    "airline": ticket.get("airline_name"),
                    "origin": ticket.get("departure_city"),
                    "destination": ticket.get("destination_city"),
                    "departure": ticket.get("departure_time"),
                    "arrival": ticket.get("arrival_time"),
                    "duration": prediction.get("flight_time", "N/A") if (prediction and not prediction.get("error")) else "N/A",
                    "status": ticket.get("ticket_status"),
                    "price": price,
                    "seat_number": ticket.get("seat_number"),
                    "travel_class": ticket.get("travel_class"),
                    "departure_date": ticket.get("departure_date")
                })
        lowest_flight = get_lowest_price_suggestion(flights)
        
    return render_template('dashboard.html', user=session['user'], prediction=prediction, flights=flights, lowest_flight=lowest_flight, origin=origin, destination=destination)


@app.route('/book-flight', methods=['POST'])
def book_flight():

    if 'user' not in session:
        return redirect(url_for('index'))

    import json

    flight_data = json.loads(
        request.form['flight_data']
    )

    return render_template(
        'payment.html',
        flight=flight_data
    )

    booking_id = str(uuid.uuid4())

    booking = {
        "booking_id": booking_id,
        "user_uid": session['user']['uid'],
        "user_email": session['user']['email'],
        "flight_number": flight_data['flight_number'],
        "airline": flight_data['airline'],
        "origin": flight_data['origin'],
        "destination": flight_data['destination'],
        "departure": flight_data['departure'],
        "arrival": flight_data['arrival'],
        "departure_date": (datetime.datetime.now() + datetime.timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d"),
        "seat_number": f"{random.randint(1, 30)}{random.choice(['A', 'B', 'C', 'D', 'E', 'F'])}",
        "travel_class": random.choice(["Economy", "Business"]),
        "price": flight_data['price'],
        "status": "Confirmed",
        "created_at": datetime.datetime.now()
    }

    bookings_collection.insert_one(booking)

    transaction = {
        "transaction_id": str(uuid.uuid4()),
        "type": "Flight Purchase",
        "buyer_email": session['user']['email'],
        "seller_email": "Airline",
        "flight_number": flight_data['flight_number'],
        "airline": flight_data['airline'],
        "amount": flight_data['price'],
        "bank_name": request.form['bank_name'],
        "card_holder": request.form['card_holder'],
        "status": "Completed",
        "created_at": datetime.datetime.now()
    }

    transactions_collection.insert_one(transaction)

    return redirect(url_for('my_bookings'))
@app.route('/confirm-payment', methods=['POST'])
def confirm_payment():

    if 'user' not in session:
        return redirect(url_for('index'))

    import json

    flight_data = json.loads(
        request.form['flight_data']
    )

    ticket_id = flight_data.get('ticket_id')
    ticket = fetched_tickets_collection.find_one({"ticket_id": ticket_id})
    if not ticket or ticket.get("ticket_status") != "Published":
        flash_error("Ticket is no longer available.")
        return redirect(url_for('dashboard'))

    booking = {
        "booking_id": ticket_id,
        "user_uid": session['user']['uid'],
        "user_email": session['user']['email'],
        "flight_number": ticket['flight_number'],
        "airline": ticket['airline_name'],
        "origin": ticket['departure_city'],
        "destination": ticket['destination_city'],
        "departure": ticket['departure_time'],
        "arrival": ticket['arrival_time'],
        "departure_date": ticket['departure_date'],
        "seat_number": ticket['seat_number'],
        "travel_class": ticket['travel_class'],
        "price": flight_data['price'],
        "status": "Confirmed",
        "created_at": datetime.datetime.now()
    }

    bookings_collection.insert_one(booking)

    transaction = {
        "transaction_id": str(uuid.uuid4()),
        "type": "Direct Flight Purchase",
        "source": "direct",
        "buyer_uid": session['user']['uid'],
        "buyer_email": session['user']['email'],
        "seller_email": ticket.get('seller_email', 'Airline'),
        "booking_id": ticket_id,
        "flight_number": ticket['flight_number'],
        "airline": ticket['airline_name'],
        "origin": ticket['departure_city'],
        "destination": ticket['destination_city'],
        "amount": flight_data['price'],
        "bank_name": request.form.get('bank_name', ''),
        "card_holder": request.form.get('card_holder', ''),
        "status": "Completed",
        "created_at": datetime.datetime.now(),
        "completed_at": datetime.datetime.now(),
        "flow_steps": ["Payment received", "Ticket issued", "Booking confirmed"]
    }

    transactions_collection.insert_one(transaction)

    # Update ticket status locally in the website database
    fetched_tickets_collection.update_one(
        {"ticket_id": ticket_id},
        {"$set": {"ticket_status": "Sold", "availability_status": "Unavailable"}}
    )

    # Sync back to external inventory
    ExternalInventoryClient.update_status(ticket_id, "Sold")

    flash_success("Ticket purchased successfully")

    return redirect(url_for('my_bookings'))


@app.route('/my-bookings')
def my_bookings():
    if 'user' not in session:
        return redirect(url_for('index'))
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    bookings = list(bookings_collection.find({"user_uid": session['user']['uid']}))
    for b in bookings:
        b['_id'] = str(b['_id'])
        
    return render_template('my_bookings.html', user=session['user'], bookings=bookings)

@app.route('/sky-swap') # Ticket Exchange
def sky_swap():
    if 'user' not in session:
        return redirect(url_for('index'))
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    # Get all sell requests
    sell_requests = list(sell_requests_collection.find({"status": "Verified / Approved"}))
    for req in sell_requests:
        req['_id'] = str(req['_id'])
        
    return render_template('sky_swap.html', user=session['user'], sell_requests=sell_requests)

@app.route('/sell-ticket', methods=['POST'])
def sell_ticket():
    if 'user' not in session:
        return jsonify({"success": False, "message": "Not logged in"}), 401
    
    booking_id = request.form['booking_id']
    try:
        price = int(request.form['price'])
    except ValueError:
        flash_error("Please enter a valid resale price")
        return redirect(url_for('my_bookings'))

    if price <= 0:
        flash_error("Resale price must be greater than zero")
        return redirect(url_for('my_bookings'))
    
    # Validate ownership
    booking = bookings_collection.find_one({
        "booking_id": booking_id,
        "user_uid": session['user']['uid']
    })
    
    if not booking:
        flash_error("Ticket not found or ownership invalid")
        return redirect(url_for('my_bookings'))

    if booking.get("status") not in {"Confirmed", "Confirmed (Transferred)"}:
        flash_error("Only confirmed tickets can be listed for resale")
        return redirect(url_for('my_bookings'))
    
    # Create sell request
    request_id = str(uuid.uuid4())
    sell_req = {
        "request_id": request_id,
        "booking_id": booking_id,
        "seller_uid": session['user']['uid'],
        "seller_email": session['user']['email'],
        "flight_number": booking['flight_number'],
        "origin": booking['origin'],
        "destination": booking['destination'],
        "asking_price": price,
        "status": "Pending Verification",
        "created_at": datetime.datetime.now()
    }
    
    sell_requests_collection.insert_one(sell_req)
    
    # Update booking status to 'On Sale'
    bookings_collection.update_one({"booking_id": booking_id}, {"$set": {"status": "On Sale"}})
    
    # Get user profile information to sync seller details
    user_db = users_collection.find_one({"uid": session['user']['uid']})
    seller_name = user_db.get("name", session['user']['name'])
    seller_phone = user_db.get("phone", "")
    seller_email = user_db.get("email", session['user']['email'])

    # Update local fetched ticket details
    fetched_tickets_collection.update_one(
        {"ticket_id": booking_id},
        {
            "$set": {
                "ticket_status": "Unpublished",  # Hide from search until verified/approved
                "resale_price": price,
                "seller_name": seller_name,
                "seller_phone": seller_phone,
                "seller_email": seller_email
            }
        }
    )

    # Sync to external inventory
    ExternalInventoryClient.update_status(
        ticket_id=booking_id,
        status="Unpublished",
        resale_price=price,
        seller_name=seller_name,
        seller_phone=seller_phone,
        seller_email=seller_email
    )
    
    flash_success("Action completed successfully")
    return redirect(url_for('my_bookings'))


@app.route('/purchase-ticket', methods=['POST'])
def purchase_ticket():
    if 'user' not in session:
        return jsonify({"success": False, "message": "Not logged in"}), 401
    
    request_id = request.form['request_id']
    sell_req = sell_requests_collection.find_one({"request_id": request_id, "status": "Verified / Approved"})
    
    if not sell_req:
        flash_error("Sell request not found or already pending")
        return redirect(url_for('sky_swap'))

    # if sell_req.get("seller_uid") == session['user']['uid']:
    #     flash_error("You cannot buy your own resale ticket")
    #     return redirect(url_for('sky_swap'))
        
    seller_email = sell_req['seller_email']
    buyer_email = session['user']['email']
    booking_id = sell_req['booking_id']
    
    update_result = sell_requests_collection.update_one(
        {"request_id": request_id, "status": "Verified / Approved"},
        {
            "$set": {
                "buyer_uid": session['user']['uid'],
                "buyer_email": buyer_email,
                "status": "Pending Admin Approval",
                "requested_at": datetime.datetime.now()
            }
        }
    )

    if update_result.matched_count == 0:
        flash_error("This ticket is no longer available")
        return redirect(url_for('sky_swap'))

    bookings_collection.update_one(
        {"booking_id": booking_id, "user_uid": sell_req["seller_uid"]},
        {"$set": {"status": "Transfer Pending"}}
    )

    transaction = {
        "transaction_id": str(uuid.uuid4()),
        "type": "Resale Ticket Purchase",
        "source": "resale",
        "request_id": request_id,
        "buyer_uid": session['user']['uid'],
        "buyer_email": buyer_email,
        "seller_email": seller_email,
        "booking_id": booking_id,
        "flight_number": sell_req.get('flight_number', ''),
        "origin": sell_req.get('origin', ''),
        "destination": sell_req.get('destination', ''),
        "amount": sell_req['asking_price'],
        "status": "Pending Admin Approval",
        "created_at": datetime.datetime.now(),
        "flow_steps": ["Buyer request submitted", "Waiting for admin approval", "Ownership transfer pending"]
    }

    transactions_collection.insert_one(transaction)
    
    # 3. NOTIFY 
    print(f"NOTIFICATION: Ticket {booking_id} transferred from {seller_email} to {buyer_email}")
       # Notify Seller
    send_notification_email_emailjs(
        email=seller_email,
        subject="Ticket Purchase Request - SkySwap",
        message=f"A buyer ({buyer_email}) has requested to purchase your ticket (Booking ID: {booking_id}). Waiting for admin approval."
    )

    # Notify Buyer
    send_notification_email_emailjs(
        email=buyer_email,
        subject="Purchase Request Submitted - SkySwap",
        message=f"Your purchase request for ticket (Booking ID: {booking_id}) has been submitted. Waiting for admin approval."
    )

    flash_success("Resale ticket request sent and is pending admin approval")
    return redirect(url_for('transactions'))
@app.route('/profile', methods=['GET', 'POST'])
def profile():

    if 'user' not in session:
        return redirect(url_for('index'))
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))

    email = session['user']['email']
    user_db = users_collection.find_one({'email': email})

    if not user_db:
        session.clear()
        flash_error("Please log in again")
        return redirect(url_for('index'))

    if request.method == 'POST':

        name = request.form['name'].strip()
        phone = request.form.get('phone', '')
        current_password = request.form.get('current_password')
        new_pass = request.form.get('password')

        if not name:
            flash_error("Name is required")
            return redirect(url_for('profile'))

        update_data = {
            'name': name,
            'phone': phone
        }

        # Only change password if user entered a new password
        if new_pass:

            # Require current password
            if not current_password:
                flash_error("Please enter your current password")
                return redirect(url_for('profile'))

            # Verify current password
            if not check_password(
                user_db['password'],
                current_password
            ):
                flash_error("Current password is incorrect")
                return redirect(url_for('profile'))

            if password_strength(new_pass) == "weak":
                flash_error("Please choose a stronger password")
                return redirect(url_for('profile'))

            # Save new password
            update_data['password'] = hash_password(new_pass)

        users_collection.update_one(
            {'email': email},
            {'$set': update_data}
        )

        # Update session
        session['user']['name'] = name
        session['user']['phone'] = phone
        session.modified = True

        if new_pass:
            flash_success("Password changed successfully")
        else:
            flash_success("Username / Profile updated successfully")

        return redirect(url_for('profile'))

    profile_user = {
        'uid': str(user_db.get('uid')),
        'email': user_db.get('email', email),
        'name': user_db.get('name', session['user'].get('name', '')),
        'phone': user_db.get('phone', ''),
        'role': user_db.get('role', session['user'].get('role', 'user'))
    }

    return render_template(
        'profile.html',
        user=profile_user
    )

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user' not in session:
        return redirect(url_for('index'))
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    
    # Get users from MongoDB
    users = list(users_collection.find({"role": "user"}))

    pending_transfers = list(
        sell_requests_collection.find(
            {"status": "Pending Admin Approval"}
        )
    )
    for user in users:
        user['_id'] = str(user['_id']) # Convert ObjectId to string for JSON/Template

    for transfer in pending_transfers:
        transfer['_id'] = str(transfer.get('_id', ''))
    
    return render_template(
        'admin_dashboard.html',
        users=users,
        pending_transfers=pending_transfers
    )

@app.route('/admin/toggle-block/<uid>')
def toggle_block(uid):
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('index'))
            
    user_data = users_collection.find_one({"uid": uid})
    if user_data:
        new_status = not user_data.get('is_blocked', False)
        users_collection.update_one({"uid": uid}, {"$set": {"is_blocked": new_status}})
        flash_success("Action completed successfully")
            
    return redirect(url_for('admin_dashboard'))
@app.route('/admin/approve-transfer/<request_id>')
def approve_transfer(request_id):

    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('index'))

    sell_req = sell_requests_collection.find_one({
        "request_id": request_id,
        "status": "Pending Admin Approval"
    })

    if not sell_req:
        flash_error("Pending resale transaction not found")
        return redirect(url_for('admin_dashboard'))

    # Transfer ticket ownership
    bookings_collection.update_one(
        {"booking_id": sell_req['booking_id']},
        {
            "$set": {
                "user_uid": sell_req['buyer_uid'],
                "user_email": sell_req['buyer_email'],
                "status": "Confirmed (Transferred)"
            }
        }
    )

    # Mark sell request completed
    sell_requests_collection.update_one(
        {"request_id": request_id},
        {
            "$set": {
                "status": "Sold",
                "approved_at": datetime.datetime.now(),
                "approved_by": session['user']['email']
            }
        }
    )

    # Mark transaction completed
    transactions_collection.update_one(
        {
            "request_id": request_id,
            "booking_id": sell_req['booking_id'],
            "status": "Pending Admin Approval"
        },
        {
            "$set": {
                "status": "Completed",
                "completed_at": datetime.datetime.now(),
                "flow_steps": ["Buyer request submitted", "Admin approved", "Ownership transferred"]
            }
        }
    )

    # Update fetched_tickets and external inventory status to Sold with buyer as the new owner/seller
    ticket_id = sell_req['booking_id']
    buyer = users_collection.find_one({"uid": sell_req['buyer_uid']})
    buyer_name = buyer.get("name", "Buyer") if buyer else "Buyer"
    buyer_phone = buyer.get("phone", "") if buyer else ""
    buyer_email = buyer.get("email", sell_req['buyer_email']) if buyer else sell_req['buyer_email']

    fetched_tickets_collection.update_one(
        {"ticket_id": ticket_id},
        {
            "$set": {
                "ticket_status": "Sold",
                "seller_name": buyer_name,
                "seller_phone": buyer_phone,
                "seller_email": buyer_email
            }
        }
    )

    ExternalInventoryClient.update_status(
        ticket_id=ticket_id,
        status="Sold",
        seller_name=buyer_name,
        seller_phone=buyer_phone,
        seller_email=buyer_email
    )

    # Notify Seller
    send_notification_email_emailjs(
        email=sell_req['seller_email'],
        subject="Ticket Sold Successfully",
        message=f"Your ticket has been sold and approved by admin."
    )

    # Notify Buyer
    send_notification_email_emailjs(
        email=sell_req['buyer_email'],
        subject="Ticket Transfer Approved",
        message=f"Your ticket purchase has been approved and ownership transferred."
    )

    flash_success("Resale transaction approved by admin")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject-transfer/<request_id>')
def reject_transfer(request_id):

    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('index'))

    sell_req = sell_requests_collection.find_one({
        "request_id": request_id,
        "status": "Pending Admin Approval"
    })

    if not sell_req:
        flash_error("Pending resale transaction not found")
        return redirect(url_for('admin_dashboard'))

    sell_requests_collection.update_one(
        {"request_id": request_id},
        {
            "$set": {
                "status": "Rejected",
                "rejected_at": datetime.datetime.now(),
                "rejected_by": session['user']['email']
            }
        }
    )

    bookings_collection.update_one(
        {"booking_id": sell_req['booking_id'], "user_uid": sell_req['seller_uid']},
        {"$set": {"status": "Confirmed"}}
    )

    transactions_collection.update_one(
        {
            "request_id": request_id,
            "booking_id": sell_req['booking_id'],
            "status": "Pending Admin Approval"
        },
        {
            "$set": {
                "status": "Rejected",
                "rejected_at": datetime.datetime.now(),
                "flow_steps": ["Buyer request submitted", "Admin rejected", "Ticket returned to seller"]
            }
        }
    )

    # Update fetched_tickets and external inventory status back to Sold (no resale price) since ticket returns to original seller
    ticket_id = sell_req['booking_id']
    fetched_tickets_collection.update_one(
        {"ticket_id": ticket_id},
        {
            "$set": {
                "ticket_status": "Sold",
                "resale_price": 0
            }
        }
    )

    ExternalInventoryClient.update_status(
        ticket_id=ticket_id,
        status="Sold",
        resale_price=0
    )

    send_notification_email_emailjs(
        email=sell_req['seller_email'],
        subject="Ticket Resale Request Rejected",
        message="The resale request for your ticket was rejected by admin. Your ticket remains yours."
    )

    send_notification_email_emailjs(
        email=sell_req['buyer_email'],
        subject="Ticket Transfer Rejected",
        message="Your resale ticket purchase request was rejected by admin."
    )


    flash_success("Action completed successfully")
    return redirect(url_for('admin_dashboard'))

@app.route('/transactions')
def transactions():

    if 'user' not in session:
        return redirect(url_for('index'))
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))

    email = session['user']['email']
    transactions_by_id = {}

    for txn in transactions_collection.find({"buyer_email": email}):
        transactions_by_id[txn.get("transaction_id", str(txn.get("_id")))] = format_transaction(txn)

    for txn in transactions_collection.find({"seller_email": email}):
        transactions_by_id[txn.get("transaction_id", str(txn.get("_id")))] = format_transaction(txn)

    user_transactions = sorted(
        transactions_by_id.values(),
        key=lambda txn: txn.get("_sort_date", datetime.datetime.min),
        reverse=True
    )

    return render_template(
        'transactions.html',
        user=session['user'],
        transactions=user_transactions
    )
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']

        print("Entered Email:", email)

        user = users_collection.find_one({"email": email})

        print("Found User:", user)

        if user:
            otp = generate_otp()
            session['reset_email'] = email
            session['reset_otp'] = otp

            if send_email_emailjs(email, otp):
                flash_success("Password reset code sent successfully")
                return redirect(url_for('reset_password_verify'))

            flash_error("Unable to send reset code right now")
            return redirect(url_for('forgot_password'))

        flash_error("User not found")
        return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html')

@app.route('/reset-password-verify', methods=['GET', 'POST'])
def reset_password_verify():

    if 'reset_email' not in session:
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':

        entered_otp = request.form['otp']

        if entered_otp == session.get('reset_otp'):
            return redirect(url_for('reset_new_password'))

        flash_error("Invalid OTP")
        return redirect(url_for('reset_password_verify'))

    return render_template('otp.html')
@app.route('/reset-new-password', methods=['GET', 'POST'])
def reset_new_password():

    if 'reset_email' not in session:
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':

        password = request.form['password']
        email = session['reset_email']

        if password_strength(password) == "weak":
            flash_error("Please choose a stronger password")
            return redirect(url_for('reset_new_password'))

        users_collection.update_one(
            {'email': email},
            {
                '$set': {
                    'password': hash_password(password)
                }
            }
        )

        session.pop('reset_email', None)
        session.pop('reset_otp', None)

        flash_success("Password reset successfully")
        return redirect(url_for('index'))

    return render_template('reset_new_password.html')

@app.route('/admin/tickets')
def admin_tickets():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('index'))
    
    search = request.args.get('search', '').lower()
    status_filter = request.args.get('status', '')
    
    query = {}
    if status_filter:
        query['status'] = status_filter
        
    sell_requests = list(sell_requests_collection.find(query))
    filtered_requests = []
    
    for req in sell_requests:
        req['_id'] = str(req.get('_id', ''))
        
        booking = bookings_collection.find_one({"booking_id": req['booking_id']})
        if booking:
            req['airline'] = booking.get('airline', 'N/A')
            req['departure_date'] = booking.get('departure_date', 'N/A')
            req['departure_time'] = booking.get('departure', 'N/A')
            req['destination'] = booking.get('destination', 'N/A')
        else:
            req['airline'] = 'N/A'
            req['departure_date'] = 'N/A'
            req['departure_time'] = 'N/A'
            req['destination'] = 'N/A'

        if search:
            if search not in str(req.get('request_id', '')).lower() and                search not in str(req.get('flight_number', '')).lower() and                search not in str(req.get('seller_email', '')).lower() and                search not in str(req.get('airline', '')).lower():
                continue
            
        filtered_requests.append(req)
        
    return render_template('admin_tickets.html', tickets=filtered_requests)

@app.route('/admin/ticket/<request_id>')
def admin_ticket_detail(request_id):
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('index'))
        
    sell_req = sell_requests_collection.find_one({"request_id": request_id})
    if not sell_req:
        flash_error("Ticket request not found")
        return redirect(url_for('admin_tickets'))
        
    booking = bookings_collection.find_one({"booking_id": sell_req['booking_id']})
    seller = users_collection.find_one({"uid": sell_req['seller_uid']})
    
    return render_template('admin_ticket_detail.html', ticket=sell_req, booking=booking, seller=seller)

@app.route('/admin/verify-ticket/<request_id>')
def verify_ticket(request_id):
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('index'))
        
    status = request.args.get('status', '')
    if status not in ['Verified / Approved', 'Rejected']:
        flash_error("Invalid status")
        return redirect(url_for('admin_ticket_detail', request_id=request_id))
        
    sell_requests_collection.update_one(
        {"request_id": request_id},
        {
            "$set": {
                "status": status,
                "verification_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "verified_by": session['user']['name']
            }
        }
    )
    
    # Sync with local fetched tickets and external inventory
    sell_req = sell_requests_collection.find_one({"request_id": request_id})
    if sell_req:
        ticket_id = sell_req['booking_id']
        if status == 'Verified / Approved':
            fetched_tickets_collection.update_one(
                {"ticket_id": ticket_id},
                {"$set": {"ticket_status": "Published"}}
            )
            ExternalInventoryClient.update_status(ticket_id, "Published")
        elif status == 'Rejected':
            fetched_tickets_collection.update_one(
                {"ticket_id": ticket_id},
                {"$set": {"ticket_status": "Sold", "resale_price": 0}}
            )
            bookings_collection.update_one(
                {"booking_id": ticket_id},
                {"$set": {"status": "Confirmed"}}
            )
            ExternalInventoryClient.update_status(ticket_id, "Sold", resale_price=0)
    
    flash_success(f"Ticket has been {status.lower()}")
    return redirect(url_for('admin_ticket_detail', request_id=request_id))


@app.route('/admin/ticket/<request_id>/pdf')
def admin_ticket_pdf(request_id):
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('index'))
        
    sell_req = sell_requests_collection.find_one({"request_id": request_id})
    if not sell_req:
        return "Not found", 404
        
    booking = bookings_collection.find_one({"booking_id": sell_req['booking_id']})
    seller = users_collection.find_one({"uid": sell_req['seller_uid']})
    
    data = {
        'ticket_id': request_id,
        'flight_number': sell_req.get('flight_number'),
        'airline': booking.get('airline', 'N/A') if booking else 'N/A',
        'origin': sell_req.get('origin'),
        'destination': sell_req.get('destination'),
        'departure_date': booking.get('departure_date', 'N/A') if booking else 'N/A',
        'departure_time': booking.get('departure', 'N/A') if booking else 'N/A',
        'arrival_time': booking.get('arrival', 'N/A') if booking else 'N/A',
        'duration': predict_flight_time(sell_req.get('origin', ''), sell_req.get('destination', '')).get('flight_time', 'N/A'),
        'seat_number': booking.get('seat_number', 'N/A') if booking else 'N/A',
        'travel_class': booking.get('travel_class', 'N/A') if booking else 'N/A',
        
        'seller_name': seller.get('name', 'N/A') if seller else 'N/A',
        'seller_uid': sell_req.get('seller_uid'),
        'seller_phone': seller.get('phone', 'N/A') if seller else 'N/A',
        'seller_email': sell_req.get('seller_email'),
        
        'original_price': booking.get('price', 0) if booking else 0,
        'resale_price': sell_req.get('asking_price', 0),
        'resale_reason': sell_req.get('resale_reason', 'N/A'),
        
        'verification_status': sell_req.get('status', 'Pending Verification'),
        'verified_by': sell_req.get('verified_by', 'N/A'),
        'verification_date': sell_req.get('verification_date', 'N/A')
    }
    
    pdf_bytes = generate_ticket_pdf(data)
    
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-disposition": f"attachment; filename=ticket_{request_id}.pdf"}
    )

@app.route('/admin/reports')
def admin_reports():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('index'))
        
    sell_requests = list(sell_requests_collection.find({}))
    reports_data = []
    
    for req in sell_requests:
        booking = bookings_collection.find_one({"booking_id": req['booking_id']})
        reports_data.append({
            'departure_date': booking.get('departure_date', 'N/A') if booking else 'N/A',
            'flight_number': req.get('flight_number', ''),
            'origin': req.get('origin', ''),
            'destination': req.get('destination', ''),
            'departure_time': booking.get('departure', '') if booking else '',
            'arrival_time': booking.get('arrival', '') if booking else '',
            'seller_email': req.get('seller_email', ''),
            'status': req.get('status', 'Unknown')
        })
        
    pdf_bytes = generate_report_pdf(reports_data)
    
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-disposition": "attachment; filename=tickets_report.pdf"}
    )

@app.route('/admin/inventory')
def admin_inventory():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('index'))

    # Load local tickets from database
    search = request.args.get('search', '').strip().lower()
    status_filter = request.args.get('status', '')
    sort_by = request.args.get('sort', '')

    query = {}
    if status_filter:
        query['ticket_status'] = status_filter

    tickets = list(fetched_tickets_collection.find(query))
    
    # Custom filtering & sorting in python for cross-db compatibility
    filtered_tickets = []
    for t in tickets:
        t['_id'] = str(t.get('_id', ''))
        
        # Search check
        if search:
            match_fields = [
                t.get('ticket_id', ''),
                t.get('flight_number', ''),
                t.get('airline_name', ''),
                t.get('departure_city', ''),
                t.get('destination_city', ''),
                t.get('seller_email', '')
            ]
            if not any(search in str(field).lower() for field in match_fields):
                continue
        
        filtered_tickets.append(t)

    # Sort
    if sort_by == 'price_asc':
        filtered_tickets.sort(key=lambda x: x.get('resale_price', 0) if x.get('resale_price', 0) > 0 else x.get('original_price', 0))
    elif sort_by == 'price_desc':
        filtered_tickets.sort(key=lambda x: x.get('resale_price', 0) if x.get('resale_price', 0) > 0 else x.get('original_price', 0), reverse=True)
    elif sort_by == 'date_asc':
        filtered_tickets.sort(key=lambda x: x.get('departure_date', ''))
    elif sort_by == 'date_desc':
        filtered_tickets.sort(key=lambda x: x.get('departure_date', ''), reverse=True)

    return render_template('admin_inventory.html', tickets=filtered_tickets)

@app.route('/admin/inventory/fetch', methods=['POST'])
def admin_fetch_inventory():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('index'))

    # Fetch from external inventory
    external_tickets = ExternalInventoryClient.get_all_tickets()
    if external_tickets is None:
        flash_error("Failed to fetch tickets from the external inventory service. Please ensure the simulator is running.")
        return redirect(url_for('admin_inventory'))

    imported_count = 0
    updated_count = 0
    invalid_count = 0
    duplicate_count = 0

    fetched_ids = set()

    for ticket_data in external_tickets:
        ticket_id = ticket_data.get('ticket_id')
        
        # Basic validation checks
        if not ticket_id or not ticket_data.get('flight_number') or not ticket_data.get('departure_city') or not ticket_data.get('destination_city'):
            invalid_count += 1
            continue
            
        original_price = ticket_data.get('original_price', 0)
        resale_price = ticket_data.get('resale_price', 0)
        if original_price < 0 or resale_price < 0:
            invalid_count += 1
            continue

        # Prevent duplicate handling inside the same imported batch
        if ticket_id in fetched_ids:
            duplicate_count += 1
            continue
        fetched_ids.add(ticket_id)

        # Check if already exists in website's database
        existing = fetched_tickets_collection.find_one({"ticket_id": ticket_id})
        
        if existing:
            # Update fields. BUT preserve local ticket visibility (ticket_status) if it's already Published or Sold,
            # UNLESS the external inventory says it is Sold/Reserved/Expired.
            local_status = existing.get('ticket_status', 'Unpublished')
            ext_status = ticket_data.get('ticket_status', 'Available')
            
            # If external is Sold/Reserved/Expired, that takes precedence
            if ext_status in ['Sold', 'Reserved', 'Expired']:
                new_status = ext_status
            else:
                # Keep current local status (e.g. Published or Unpublished)
                new_status = local_status

            fetched_tickets_collection.update_one(
                {"ticket_id": ticket_id},
                {
                    "$set": {
                        "flight_number": ticket_data.get('flight_number'),
                        "airline_name": ticket_data.get('airline_name'),
                        "departure_city": ticket_data.get('departure_city'),
                        "destination_city": ticket_data.get('destination_city'),
                        "departure_date": ticket_data.get('departure_date'),
                        "departure_time": ticket_data.get('departure_time'),
                        "arrival_time": ticket_data.get('arrival_time'),
                        "seat_number": ticket_data.get('seat_number'),
                        "travel_class": ticket_data.get('travel_class'),
                        "ticket_status": new_status,
                        "original_price": original_price,
                        "resale_price": resale_price,
                        "availability_status": ticket_data.get('availability_status', 'Available'),
                        "seller_name": ticket_data.get('seller_name'),
                        "seller_phone": ticket_data.get('seller_phone'),
                        "seller_email": ticket_data.get('seller_email')
                    }
                }
            )
            updated_count += 1
        else:
            # Create new record. "No automatic publishing should occur unless specifically enabled by the admin."
            # So new fetched tickets default to 'Unpublished' locally.
            ticket_data['ticket_status'] = 'Unpublished'
            fetched_tickets_collection.insert_one(ticket_data)
            imported_count += 1

    # Delete synchronization:
    # Remove from local database any fetched tickets that were deleted from the external inventory
    local_tickets = list(fetched_tickets_collection.find({}))
    deleted_count = 0
    for local_t in local_tickets:
        loc_id = local_t.get('ticket_id')
        if loc_id not in fetched_ids:
            # Ticket was deleted in external inventory -> delete it locally to not show it publicly
            fetched_tickets_collection.delete_one({"ticket_id": loc_id})
            deleted_count += 1

    flash_success(f"Sync complete. Imported: {imported_count}, Updated: {updated_count}, Removed: {deleted_count}. (Skipped {invalid_count} invalid, {duplicate_count} duplicates).")
    return redirect(url_for('admin_inventory'))

@app.route('/admin/inventory/update-status/<ticket_id>')
def admin_inventory_update_status(ticket_id):
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('index'))

    action = request.args.get('action')
    ticket = fetched_tickets_collection.find_one({"ticket_id": ticket_id})
    if not ticket:
        flash_error("Ticket not found")
        return redirect(url_for('admin_inventory'))

    new_status = ticket.get('ticket_status', 'Unpublished')
    if action == 'publish':
        new_status = 'Published'
    elif action == 'unpublish':
        new_status = 'Unpublished'
    elif action == 'sold':
        new_status = 'Sold'
    elif action == 'unavailable':
        new_status = 'Expired'

    # Update locally
    fetched_tickets_collection.update_one(
        {"ticket_id": ticket_id},
        {"$set": {"ticket_status": new_status, "availability_status": "Unavailable" if new_status in ["Sold", "Reserved", "Expired", "Unpublished"] else "Available"}}
    )

    # Sync back to external inventory GDS Simulator
    ExternalInventoryClient.update_status(ticket_id, new_status)

    flash_success(f"Ticket status successfully updated to {new_status}")
    return redirect(url_for('admin_inventory'))

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)

