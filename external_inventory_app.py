import os
import json
import uuid
from flask import Flask, request, jsonify, render_template_string, redirect, url_for

app = Flask(__name__)
app.secret_key = "external-inventory-secret"

DB_FILE = "/tmp/external_inventory_db.json" if os.getenv("VERCEL") else os.path.join(os.path.dirname(__file__), "external_inventory_db.json")

# Helper to load tickets
def load_tickets():
    if not os.path.exists(DB_FILE):
        seed_tickets()
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

# Helper to save tickets
def save_tickets(tickets):
    with open(DB_FILE, "w") as f:
        json.dump(tickets, f, indent=4)

# Seed initial tickets
def seed_tickets():
    tickets = [
        {
            "ticket_id": "TKT-1001",
            "flight_number": "EK-622",
            "airline_name": "Emirates",
            "departure_city": "Lahore",
            "destination_city": "Dubai",
            "departure_date": "2026-07-20",
            "departure_time": "10:30",
            "arrival_time": "13:20",
            "seat_number": "12A",
            "travel_class": "Economy",
            "ticket_status": "Available",
            "original_price": 55000,
            "resale_price": 0,
            "availability_status": "Available",
            "seller_name": "Emirates Airlines",
            "seller_phone": "+923001234567",
            "seller_email": "inventory@emirates.com"
        },
        {
            "ticket_id": "TKT-1002",
            "flight_number": "EK-623",
            "airline_name": "Emirates",
            "departure_city": "Dubai",
            "destination_city": "Lahore",
            "departure_date": "2026-07-25",
            "departure_time": "15:45",
            "arrival_time": "19:15",
            "seat_number": "14C",
            "travel_class": "Economy",
            "ticket_status": "Available",
            "original_price": 58000,
            "resale_price": 0,
            "availability_status": "Available",
            "seller_name": "Emirates Airlines",
            "seller_phone": "+923001234567",
            "seller_email": "inventory@emirates.com"
        },
        {
            "ticket_id": "TKT-1003",
            "flight_number": "PK-302",
            "airline_name": "PIA",
            "departure_city": "Karachi",
            "destination_city": "Islamabad",
            "departure_date": "2026-07-15",
            "departure_time": "08:00",
            "arrival_time": "10:00",
            "seat_number": "22D",
            "travel_class": "Economy",
            "ticket_status": "Available",
            "original_price": 28000,
            "resale_price": 0,
            "availability_status": "Available",
            "seller_name": "PIA",
            "seller_phone": "+923219876543",
            "seller_email": "inventory@pia.com.pk"
        },
        {
            "ticket_id": "TKT-1004",
            "flight_number": "PK-303",
            "airline_name": "PIA",
            "departure_city": "Islamabad",
            "destination_city": "Karachi",
            "departure_date": "2026-07-18",
            "departure_time": "18:30",
            "arrival_time": "20:30",
            "seat_number": "10B",
            "travel_class": "Business",
            "ticket_status": "Available",
            "original_price": 45000,
            "resale_price": 0,
            "availability_status": "Available",
            "seller_name": "PIA",
            "seller_phone": "+923219876543",
            "seller_email": "inventory@pia.com.pk"
        },
        {
            "ticket_id": "TKT-1005",
            "flight_number": "QR-240",
            "airline_name": "Qatar Airways",
            "departure_city": "London",
            "destination_city": "New York",
            "departure_date": "2026-08-05",
            "departure_time": "14:00",
            "arrival_time": "16:45",
            "seat_number": "04F",
            "travel_class": "Business",
            "ticket_status": "Available",
            "original_price": 140000,
            "resale_price": 0,
            "availability_status": "Available",
            "seller_name": "Qatar Airways",
            "seller_phone": "+97444444444",
            "seller_email": "inventory@qatarairways.com"
        },
        {
            "ticket_id": "TKT-1006",
            "flight_number": "TK-715",
            "airline_name": "Turkish Airlines",
            "departure_city": "Lahore",
            "destination_city": "Istanbul",
            "departure_date": "2026-07-28",
            "departure_time": "06:15",
            "arrival_time": "10:30",
            "seat_number": "31A",
            "travel_class": "Economy",
            "ticket_status": "Available",
            "original_price": 75000,
            "resale_price": 0,
            "availability_status": "Available",
            "seller_name": "Turkish Airlines",
            "seller_phone": "+902124636363",
            "seller_email": "inventory@thy.com"
        },
        {
            "ticket_id": "TKT-1007",
            "flight_number": "EY-231",
            "airline_name": "Etihad Airways",
            "departure_city": "Abu Dhabi",
            "destination_city": "London",
            "departure_date": "2026-08-12",
            "departure_time": "09:00",
            "arrival_time": "13:30",
            "seat_number": "15C",
            "travel_class": "Economy",
            "ticket_status": "Available",
            "original_price": 95000,
            "resale_price": 0,
            "availability_status": "Available",
            "seller_name": "Etihad Airways",
            "seller_phone": "+97125990000",
            "seller_email": "inventory@etihad.com"
        }
    ]
    save_tickets(tickets)

# --- Web Interface (External Inventory Control Panel) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>External Dummy Ticket Inventory Panel</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Outfit', sans-serif; background-color: #0f172a; color: #f8fafc; }
        .glass-panel { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.05); }
    </style>
</head>
<body class="min-h-screen p-8">
    <div class="max-w-6xl mx-auto space-y-8">
        
        <!-- Header -->
        <div class="glass-panel rounded-3xl p-6 shadow-2xl flex flex-col md:flex-row md:items-center md:justify-between border-l-4 border-indigo-500">
            <div>
                <span class="text-xs font-bold text-indigo-400 uppercase tracking-widest">Global Distribution System (GDS) Simulator</span>
                <h1 class="text-3xl font-extrabold tracking-tight">Dummy Ticket Inventory</h1>
                <p class="text-slate-400 mt-1">Manage flight tickets at the source. Any changes here represent updates in the external airline database.</p>
            </div>
            <div class="mt-4 md:mt-0 flex items-center space-x-3 bg-slate-800 px-4 py-2 rounded-full border border-slate-700">
                <span class="relative flex h-3 w-3">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                </span>
                <span class="text-sm font-semibold">Simulator Active (Port 5001)</span>
            </div>
        </div>

        <!-- Add/Edit Ticket Card -->
        <div class="glass-panel rounded-3xl p-6 shadow-2xl">
            <h2 class="text-xl font-bold mb-4 flex items-center gap-2 text-indigo-300">
                <i class="fas fa-edit"></i>
                <span>Add / Edit Ticket in Inventory</span>
            </h2>
            <form action="{{ url_for('web_save_ticket') }}" method="POST" class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <input type="hidden" name="action_type" id="form-action" value="create">
                
                <div>
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Ticket ID</label>
                    <input type="text" name="ticket_id" id="form-ticket-id" required placeholder="e.g. TKT-1008" class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-white transition-all">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Flight Number</label>
                    <input type="text" name="flight_number" id="form-flight-number" required placeholder="e.g. EK-624" class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-white transition-all">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Airline Name</label>
                    <input type="text" name="airline_name" id="form-airline-name" required placeholder="e.g. Emirates" class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-white transition-all">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Travel Class</label>
                    <select name="travel_class" id="form-travel-class" required class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-white transition-all">
                        <option value="Economy">Economy</option>
                        <option value="Business">Business</option>
                    </select>
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Departure City</label>
                    <input type="text" name="departure_city" id="form-departure-city" required placeholder="e.g. Lahore" class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-white transition-all">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Destination City</label>
                    <input type="text" name="destination_city" id="form-destination-city" required placeholder="e.g. Dubai" class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-white transition-all">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Departure Date</label>
                    <input type="date" name="departure_date" id="form-departure-date" required class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-white transition-all">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Seat Number</label>
                    <input type="text" name="seat_number" id="form-seat-number" required placeholder="e.g. 12A" class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-white transition-all">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Departure Time</label>
                    <input type="text" name="departure_time" id="form-departure-time" required placeholder="e.g. 10:30" class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-white transition-all">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Arrival Time</label>
                    <input type="text" name="arrival_time" id="form-arrival-time" required placeholder="e.g. 13:20" class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-white transition-all">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Original Price (PKR)</label>
                    <input type="number" name="original_price" id="form-original-price" required placeholder="55000" class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-white transition-all">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Resale Price (PKR)</label>
                    <input type="number" name="resale_price" id="form-resale-price" value="0" placeholder="0" class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-white transition-all">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Seller Name</label>
                    <input type="text" name="seller_name" id="form-seller-name" required placeholder="Emirates Airlines" class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-white transition-all">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Seller Phone</label>
                    <input type="text" name="seller_phone" id="form-seller-phone" required placeholder="+923001234567" class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-white transition-all">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Seller Email</label>
                    <input type="email" name="seller_email" id="form-seller-email" required placeholder="inventory@airline.com" class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-white transition-all">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Status</label>
                    <select name="ticket_status" id="form-ticket-status" class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-white transition-all">
                        <option value="Available">Available</option>
                        <option value="Published">Published</option>
                        <option value="Unpublished">Unpublished</option>
                        <option value="Sold">Sold</option>
                        <option value="Reserved">Reserved</option>
                        <option value="Expired">Expired</option>
                    </select>
                </div>
                
                <div class="md:col-span-4 flex justify-end gap-3 mt-2">
                    <button type="button" onclick="resetForm()" class="px-6 py-2 rounded-xl bg-slate-750 border border-slate-700 hover:bg-slate-700 font-semibold text-sm transition-all">
                        Reset
                    </button>
                    <button type="submit" class="px-6 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 font-bold text-sm shadow-lg shadow-indigo-600/30 transition-all">
                        Save Inventory Ticket
                    </button>
                </div>
            </form>
        </div>

        <!-- Inventory List -->
        <div class="glass-panel rounded-3xl p-6 shadow-2xl overflow-hidden">
            <div class="flex items-center justify-between mb-6">
                <h2 class="text-xl font-bold flex items-center gap-2 text-indigo-300">
                    <i class="fas fa-list"></i>
                    <span>All Inventory Tickets ({{ tickets|length }})</span>
                </h2>
                <a href="{{ url_for('web_seed') }}" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl text-sm font-semibold transition-all">
                    <i class="fas fa-sync mr-1"></i> Re-Seed Default Tickets
                </a>
            </div>

            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-slate-800 text-left">
                    <thead class="bg-slate-800/50">
                        <tr>
                            <th class="px-4 py-3 text-xs font-bold text-slate-400 uppercase">ID</th>
                            <th class="px-4 py-3 text-xs font-bold text-slate-400 uppercase">Flight</th>
                            <th class="px-4 py-3 text-xs font-bold text-slate-400 uppercase">Route</th>
                            <th class="px-4 py-3 text-xs font-bold text-slate-400 uppercase">Seat & Class</th>
                            <th class="px-4 py-3 text-xs font-bold text-slate-400 uppercase">Price (Original / Resale)</th>
                            <th class="px-4 py-3 text-xs font-bold text-slate-400 uppercase">Seller Info</th>
                            <th class="px-4 py-3 text-xs font-bold text-slate-400 uppercase">Status</th>
                            <th class="px-4 py-3 text-xs font-bold text-slate-400 uppercase">Actions</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-800 bg-slate-900/20">
                        {% for ticket in tickets %}
                        <tr class="hover:bg-slate-800/40 transition-colors">
                            <td class="px-4 py-4 whitespace-nowrap text-sm font-mono font-bold text-indigo-400">{{ ticket.ticket_id }}</td>
                            <td class="px-4 py-4 whitespace-nowrap">
                                <span class="font-bold text-sm text-slate-200">{{ ticket.flight_number }}</span><br>
                                <span class="text-xs text-slate-400">{{ ticket.airline_name }}</span>
                            </td>
                            <td class="px-4 py-4 whitespace-nowrap text-sm text-slate-200">
                                <div>{{ ticket.departure_city }} &rarr; {{ ticket.destination_city }}</div>
                                <div class="text-xs text-slate-400">{{ ticket.departure_date }} at {{ ticket.departure_time }}</div>
                            </td>
                            <td class="px-4 py-4 whitespace-nowrap text-sm text-slate-200">
                                <span class="px-2 py-0.5 rounded bg-slate-800 text-xs font-bold font-mono text-slate-300">{{ ticket.seat_number }}</span><br>
                                <span class="text-xs text-slate-400">{{ ticket.travel_class }}</span>
                            </td>
                            <td class="px-4 py-4 whitespace-nowrap text-sm text-slate-200">
                                <span class="font-semibold text-slate-300">{{ ticket.original_price }} PKR</span><br>
                                {% if ticket.resale_price > 0 %}
                                <span class="text-xs text-indigo-400">Resale: {{ ticket.resale_price }} PKR</span>
                                {% else %}
                                <span class="text-xs text-slate-500">No resale</span>
                                {% endif %}
                            </td>
                            <td class="px-4 py-4 whitespace-nowrap text-xs text-slate-400">
                                <span class="font-bold text-slate-300">{{ ticket.seller_name }}</span><br>
                                <span>{{ ticket.seller_email }}</span><br>
                                <span>{{ ticket.seller_phone }}</span>
                            </td>
                            <td class="px-4 py-4 whitespace-nowrap text-sm">
                                <span class="px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider
                                    {% if ticket.ticket_status == 'Available' or ticket.ticket_status == 'Published' %}
                                        bg-emerald-500/10 text-emerald-400 border border-emerald-500/20
                                    {% elif ticket.ticket_status == 'Sold' %}
                                        bg-blue-500/10 text-blue-400 border border-blue-500/20
                                    {% elif ticket.ticket_status == 'Reserved' %}
                                        bg-amber-500/10 text-amber-400 border border-amber-500/20
                                    {% else %}
                                        bg-slate-700/30 text-slate-400 border border-slate-600/20
                                    {% endif %}">
                                    {{ ticket.ticket_status }}
                                </span>
                            </td>
                            <td class="px-4 py-4 whitespace-nowrap text-xs font-bold space-x-2">
                                <button onclick="editTicket({{ ticket|tojson|safe }})" class="px-2 py-1 rounded bg-indigo-600/20 text-indigo-400 hover:bg-indigo-600/30">
                                    Edit
                                </button>
                                <a href="{{ url_for('web_delete_ticket', ticket_id=ticket.ticket_id) }}" onclick="return confirm('Are you sure you want to delete this ticket?')" class="px-2 py-1 rounded bg-red-500/15 text-red-400 hover:bg-red-500/25">
                                    Delete
                                </a>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="8" class="px-4 py-8 text-center text-slate-500">No tickets inside the inventory. Seed or add some.</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function editTicket(t) {
            document.getElementById('form-action').value = 'update';
            
            document.getElementById('form-ticket-id').value = t.ticket_id;
            document.getElementById('form-ticket-id').readOnly = true;
            document.getElementById('form-ticket-id').classList.add('opacity-50');
            
            document.getElementById('form-flight-number').value = t.flight_number;
            document.getElementById('form-airline-name').value = t.airline_name;
            document.getElementById('form-travel-class').value = t.travel_class;
            document.getElementById('form-departure-city').value = t.departure_city;
            document.getElementById('form-destination-city').value = t.destination_city;
            document.getElementById('form-departure-date').value = t.departure_date;
            document.getElementById('form-seat-number').value = t.seat_number;
            document.getElementById('form-departure-time').value = t.departure_time;
            document.getElementById('form-arrival-time').value = t.arrival_time;
            document.getElementById('form-original-price').value = t.original_price;
            document.getElementById('form-resale-price').value = t.resale_price;
            document.getElementById('form-seller-name').value = t.seller_name;
            document.getElementById('form-seller-phone').value = t.seller_phone;
            document.getElementById('form-seller-email').value = t.seller_email;
            document.getElementById('form-ticket-status').value = t.ticket_status;
        }

        function resetForm() {
            document.getElementById('form-action').value = 'create';
            
            document.getElementById('form-ticket-id').value = '';
            document.getElementById('form-ticket-id').readOnly = false;
            document.getElementById('form-ticket-id').classList.remove('opacity-50');
            
            document.getElementById('form-flight-number').value = '';
            document.getElementById('form-airline-name').value = '';
            document.getElementById('form-travel-class').value = 'Economy';
            document.getElementById('form-departure-city').value = '';
            document.getElementById('form-destination-city').value = '';
            document.getElementById('form-departure-date').value = '';
            document.getElementById('form-seat-number').value = '';
            document.getElementById('form-departure-time').value = '';
            document.getElementById('form-arrival-time').value = '';
            document.getElementById('form-original-price').value = '';
            document.getElementById('form-resale-price').value = '0';
            document.getElementById('form-seller-name').value = '';
            document.getElementById('form-seller-phone').value = '';
            document.getElementById('form-seller-email').value = '';
            document.getElementById('form-ticket-status').value = 'Available';
        }
    </script>
</body>
</html>
"""

@app.route("/")
def web_index():
    tickets = load_tickets()
    return render_template_string(HTML_TEMPLATE, tickets=tickets)

@app.route("/web/seed")
def web_seed():
    seed_tickets()
    return redirect(url_for('web_index'))

@app.route("/web/save", methods=["POST"])
def web_save_ticket():
    tickets = load_tickets()
    ticket_id = request.form["ticket_id"].strip()
    action = request.form["action_type"]

    ticket_data = {
        "ticket_id": ticket_id,
        "flight_number": request.form["flight_number"].strip(),
        "airline_name": request.form["airline_name"].strip(),
        "travel_class": request.form["travel_class"].strip(),
        "departure_city": request.form["departure_city"].strip(),
        "destination_city": request.form["destination_city"].strip(),
        "departure_date": request.form["departure_date"].strip(),
        "seat_number": request.form["seat_number"].strip(),
        "departure_time": request.form["departure_time"].strip(),
        "arrival_time": request.form["arrival_time"].strip(),
        "original_price": int(request.form["original_price"]),
        "resale_price": int(request.form.get("resale_price", 0) or 0),
        "seller_name": request.form["seller_name"].strip(),
        "seller_phone": request.form["seller_phone"].strip(),
        "seller_email": request.form["seller_email"].strip(),
        "ticket_status": request.form["ticket_status"].strip(),
        "availability_status": "Unavailable" if request.form["ticket_status"].strip() in ["Sold", "Reserved", "Expired"] else "Available"
    }

    if action == "create":
        # Check duplicate
        if any(t["ticket_id"] == ticket_id for t in tickets):
            # Already exists
            return "Error: Ticket ID already exists", 400
        tickets.append(ticket_data)
    else:
        # Update
        for i, t in enumerate(tickets):
            if t["ticket_id"] == ticket_id:
                tickets[i] = ticket_data
                break
    save_tickets(tickets)
    return redirect(url_for('web_index'))

@app.route("/web/delete/<ticket_id>")
def web_delete_ticket(ticket_id):
    tickets = load_tickets()
    tickets = [t for t in tickets if t["ticket_id"] != ticket_id]
    save_tickets(tickets)
    return redirect(url_for('web_index'))

# --- API Endpoints ---
@app.route("/api/tickets", methods=["GET"])
def api_get_tickets():
    return jsonify(load_tickets())

@app.route("/api/tickets/<ticket_id>", methods=["PUT"])
def api_update_ticket(ticket_id):
    tickets = load_tickets()
    req_data = request.json
    for i, t in enumerate(tickets):
        if t["ticket_id"] == ticket_id:
            tickets[i].update(req_data)
            # Make sure availability status matches status
            if "ticket_status" in req_data:
                status = req_data["ticket_status"]
                tickets[i]["availability_status"] = "Unavailable" if status in ["Sold", "Reserved", "Expired", "Unpublished"] else "Available"
            save_tickets(tickets)
            return jsonify({"success": True, "ticket": tickets[i]})
    return jsonify({"success": False, "message": "Ticket not found"}), 404

@app.route("/api/tickets/<ticket_id>/status", methods=["POST"])
def api_update_status(ticket_id):
    tickets = load_tickets()
    req_data = request.json or {}
    status = req_data.get("ticket_status")
    
    if not status:
        return jsonify({"success": False, "message": "Status not provided"}), 400

    for i, t in enumerate(tickets):
        if t["ticket_id"] == ticket_id:
            tickets[i]["ticket_status"] = status
            tickets[i]["availability_status"] = "Unavailable" if status in ["Sold", "Reserved", "Expired", "Unpublished"] else "Available"
            
            # If resale_price is sent, sync it
            if "resale_price" in req_data:
                tickets[i]["resale_price"] = req_data["resale_price"]
            # If seller info is sent, sync it
            if "seller_name" in req_data:
                tickets[i]["seller_name"] = req_data["seller_name"]
            if "seller_phone" in req_data:
                tickets[i]["seller_phone"] = req_data["seller_phone"]
            if "seller_email" in req_data:
                tickets[i]["seller_email"] = req_data["seller_email"]
                
            save_tickets(tickets)
            return jsonify({"success": True, "ticket": tickets[i]})
            
    return jsonify({"success": False, "message": "Ticket not found"}), 404

def start_inventory_app():
    # Run on port 5001
    app.run(port=5001, debug=False, use_reloader=False)

if __name__ == "__main__":
    app.run(port=5001, debug=True)
