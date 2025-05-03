import csv
import os
import sys
import glob
import json
import uuid
import threading
import subprocess
import requests

from flask import (
    Flask, render_template, request,
    send_from_directory, jsonify
)

app = Flask(__name__)

# # Node-RED Admin API URL
NODE_RED_URL     = 'http://localhost:1880'
# BROKER_CONFIG_ID = '783325a25ca126cc'

# where our scripts dump CSVs
RESULTS_DIR = os.path.join(app.root_path, 'results')
LOGS_DIR    = os.path.join(app.root_path, 'logs')
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# In-memory job status store
job_status = {}  # job_id -> {'step1':..., 'step2':..., 'step3':...}

def new_id():
    return uuid.uuid4().hex[:8]


@app.route('/deploy_simulation', methods=['POST'])
def deploy_simulation():
    spec = request.get_json()

    broker_host = spec.get('broker_name', 'localhost')
    broker_port = str(spec.get('broker_port', 1883))
    broker_config_id = new_id()  # Generate new ID for each deployment

    # 1) Fetch all existing flows
    all_nodes = requests.get(f'{NODE_RED_URL}/flows').json()

    # 2) Identify components to remove
    sim_tabs = {
        n['id'] for n in all_nodes
        if n.get('type') == 'tab' and n.get('label','').startswith('Sim-')
    }

    # Remove ALL existing MQTT brokers regardless of origin
    flows = [
        n for n in all_nodes
        if not (n.get('type') == 'mqtt-broker' 
        and n.get('name') in {'nanomq', 'mosquitto', 'emqx', 'rabbitmq', 'activemq', 'vernemq'})  # Add other broker names
    ]

    # 3) Build new flows list:
    flows = []
    for n in all_nodes:
        if n.get('type') == 'tab' and n['id'] in sim_tabs:
            continue
        if n.get('z') in sim_tabs:
            continue
        if n.get('type') == 'mqtt-broker':
            continue  # Remove ALL existing brokers
        flows.append(n)

    # 4) Add new broker configuration
    flows.append({
        "id":             broker_config_id,
        "type":           "mqtt-broker",
        "name":           broker_host,
        "broker":         broker_host,
        "port":           broker_port,
        "clientid":       "",
        "autoConnect":    True,
        "usetls":         False,
        "protocolVersion": 4,
        "keepalive":      60,
        "cleansession":   True,
        "sim_generated":  True  # Mark for future cleanup
    })

    # Create Publisher Tab
    pub_tab_id = new_id()
    flows.append({
        "id":       pub_tab_id,
        "type":     "tab",
        "label":    f"Sim-pub-{pub_tab_id[:6]}",
        "disabled": False,
        "info":     ""
    })

    pubs = spec.get('publishers', [])
    interval = spec.get('interval', 1)

    # Inject node
    inject_id = new_id()
    inject = {
        "id":       inject_id,
        "type":     "inject",
        "z":        pub_tab_id,
        "name":     "⏱ timestamp",
        "props":    [{"p":"payload"}],
        "repeat":   str(interval),
        "once":     True,
        "onceDelay":0.1,
        "outputs":  1,
        "wires":    []
    }
    flows.append(inject)

    # Splitter node
    splitter_id = new_id()
    splitter_node = {
        "id":       splitter_id,
        "type":     "function",
        "z":        pub_tab_id,
        "name":     "Splitter",
        "func":     (
            "var outputs = [];\n"
            f"for(var i=0;i<{len(pubs)};i++){{ outputs.push({{payload:Date.now()}}); }}\n"
            "return outputs;"
        ),
        "outputs":  len(pubs),
        "noerr":    0,
        "initialize":"",
        "finalize": "",
        "libs":     [],
        "x":        200,
        "y":        100,
        "wires":    [[] for _ in pubs]
    }
    flows.append(splitter_node)

    # Wire inject → splitter
    inject['wires'] = [[splitter_id]]

    # Publisher chains
    y = 200
    for idx, p in enumerate(pubs):
        fn_id = new_id()
        js_id = new_id()
        mout_id = new_id()

        func_code = (
            f"msg.payload = Math.random()*({p['max']}-{p['min']})+{p['min']};\n"
            "return msg;" if p.get('random') else 
            f"msg.payload = {p['min']}; return msg;"
        )

        # Function node
        flows.append({
            "id":      fn_id,
            "type":    "function",
            "z":       pub_tab_id,
            "name":    p['name'],
            "func":    func_code,
            "outputs": 1,
            "x":       320,
            "y":       y,
            "wires":   [[js_id]]
        })

        # JSON node
        flows.append({
            "id":       js_id,
            "type":     "json",
            "z":        pub_tab_id,
            "name":     "to JSON",
            "property": "payload",
            "action":   "str",
            "pretty":   False,
            "x":        480,
            "y":        y,
            "wires":    [[mout_id]]
        })

        # MQTT Out node
        flows.append({
            "id":       mout_id,
            "type":     "mqtt out",
            "z":        pub_tab_id,
            "name":     f"{p['name']} → {p['topic']}",
            "topic":    p['topic'],
            "qos":      str(p.get('qos',1)),
            "retain":   False,
            "broker":   broker_config_id,  # Use dynamic ID
            "x":        650,
            "y":        y,
            "wires":    []
        })

        splitter_node['wires'][idx] = [fn_id]
        y += 80

    # Create Subscriber Tab + Dashboard
    sub_tab_id = new_id()
    ui_tab_id = new_id()
    ui_grp_id = new_id()

    flows.append({
        "id":       sub_tab_id,
        "type":     "tab",
        "label":    f"Sim-sub-{sub_tab_id[:6]}",
        "disabled": False,
        "info":     ""
    })
    flows.append({
        "id":       ui_tab_id,
        "type":     "ui_tab",
        "z":        "",
        "name":     "Metrics",
        "icon":     "dashboard",
        "order":    1,
        "disabled": False,
        "hidden":   False
    })
    flows.append({
        "id":      ui_grp_id,
        "type":    "ui_group",
        "z":       "",
        "name":    "Values",
        "tab":     ui_tab_id,
        "order":   1,
        "disp":    True,
        "width":   "24",
        "collapse":False
    })

    subs = spec.get('subscribers', [])
    y = 80
    for s in subs:
        in_id = new_id()
        func_id = new_id()
        gauge_id = new_id()
        text_id = new_id()

        # MQTT In node
        flows.append({
            "id":      in_id,
            "type":    "mqtt in",
            "z":       sub_tab_id,
            "name":    f"{s['name']} ◀ {s['topic']}",
            "topic":   s['topic'],
            "qos":     str(s.get('qos',1)),
            "datatype":"json",
            "broker":  broker_config_id,  # Use dynamic ID
            "x":       300,
            "y":       y,
            "wires":   [[func_id]]
        })

        # Function node
        flows.append({
            "id":      func_id,
            "type":    "function",
            "z":       sub_tab_id,
            "name":    f"{s['name']} Check",
            "func":    "msg.payload = parseFloat(msg.payload).toFixed(2); return msg;",
            "outputs": 1,
            "x":       450,
            "y":       y,
            "wires":   [[gauge_id,text_id]]
        })

        # UI Gauge
        flows.append({
            "id":      gauge_id,
            "type":    "ui_gauge",
            "z":       sub_tab_id,
            "name":    s['name'],
            "group":   ui_grp_id,
            "order":   1,
            "width":   6,
            "height":  5,
            "gtype":   s.get('gtype','gage'),
            "title":   s['name'],
            "label":   s.get('unit',''),
            "format":  "{{value}}",
            "min":     0,
            "max":     100,
            "colors":  ["#00b500","#e6e600","#ca3838"],
            "x":       620,
            "y":       y,
            "wires":   []
        })

        # UI Text
        flows.append({
            "id":      text_id,
            "type":    "ui_text",
            "z":       sub_tab_id,
            "group":   ui_grp_id,
            "order":   2,
            "width":   0,
            "height":  0,
            "name":    f"{s['name']} Text",
            "label":   s['name'],
            "format":  "{{msg.payload}}",
            "layout":  "row-spread",
            "x":       800,
            "y":       y,
            "wires":   []
        })

        y += 80

    # Deploy flows to Node-RED
    resp = requests.post(
        f'{NODE_RED_URL}/flows',
        headers={'Content-Type':'application/json'},
        json=flows
    )
    if resp.status_code != 204:
        return resp.text, 500

    return jsonify(ok=True)


def run_tests_in_background(job_id, args):
    python_cmd = sys.executable
    env        = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8']       = '1'

    # Step definitions: note that broker_pinger.py now only gets --duration,
    # and uses its own defaults for --interval and --topic.
    steps = [
        ('broker_pinger.py',       'step1', ['--duration', args['duration']]),
        ('broker_availability.py', 'step2', ['--duration', args['duration']]),
        ('max_clients_test.py',    'step3', ['--clients', args['max_clients'], '--payload_size', args['payload_size']]),
    ]

    base_args = [
        '--name', args['broker_name'],
        '--port', args['broker_port']
    ]

    for script, key, extra in steps:
        job_status[job_id][key] = 'running'
        try:
            subprocess.run(
                [python_cmd,
                 os.path.join(app.root_path,'evaluation_scripts', script),
                 *base_args,
                 *extra
                ],
                check=True, env=env, capture_output=True
            )
            job_status[job_id][key] = 'done'
        except Exception as e:
            print(f"Error in {script}:", e)
            job_status[job_id][key] = 'error'


@app.route('/run_tests', methods=['POST'])
def run_tests():
    args   = request.get_json()
    job_id = uuid.uuid4().hex
    job_status[job_id] = {'step1':'pending','step2':'pending','step3':'pending'}
    threading.Thread(
        target=run_tests_in_background,
        args=(job_id,args),
        daemon=True
    ).start()
    return jsonify(job_id=job_id)


@app.route('/status/<job_id>')
def status(job_id):
    return jsonify(job_status.get(job_id, {}))


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/results/<broker_name>')
def results(broker_name):
    # pull in the same query-string params you already have:
    duration    = request.args.get('duration','60')
    max_clients = request.args.get('max_clients','100')
    payload     = request.args.get('payload_size','256')
    broker_port = request.args.get('broker_port','1883')

    # 1) ping times (for your line graph)
    ping_ts, ping_d = [], []
    ping_f = os.path.join(RESULTS_DIR, f'broker_pinger_results_{broker_name}.csv')
    if os.path.exists(ping_f):
        with open(ping_f) as f:
            for row in csv.reader(f):
                if len(row)>=2:
                    ping_ts.append(row[0])
                    try:
                        ping_d.append(float(row[1]))
                    except:
                        ping_d.append(0.0)

    # 2) availability (MTBF / MTTR)
    mtbf, mttr = 0.0, 0.0
    avail_f = os.path.join(LOGS_DIR, f'broker_availability_results_{broker_name}_{duration}.csv')
    if os.path.exists(avail_f):
        with open(avail_f) as f:
            r = csv.reader(f)
            next(r,None)
            for row in r:
                if len(row)>=2:
                    key, val = row[0].strip().upper(), row[1]
                    try:
                        if key=='MTBF': mtbf = float(val)
                        if key=='MTTR': mttr = float(val)
                    except:
                        pass

    # 3) max-clients curve
    c_ids, c_times = [], []
    max_f = os.path.join(
        RESULTS_DIR,
        f'max_clients_results_{broker_name}_{max_clients}_P_{payload}.csv'
    )
    if os.path.exists(max_f):
        with open(max_f) as f:
            r = csv.reader(f)
            next(r,None)
            for row in r:
                if len(row)>=2:
                    try:
                        c_ids.append(int(row[0]))
                        c_times.append(float(row[1]))
                    except:
                        pass

    # 4) Load the latest step-1 summary (ConnectionSetup, Subscription, PingRTT)
    pattern = os.path.join(
        RESULTS_DIR,
        f'mqtt_stats_{broker_name}_{broker_port}_*.csv'
    )
    files = sorted(glob.glob(pattern))
    avg_metrics = {}
    if files:
        latest = files[-1]
        with open(latest) as f:
            reader = csv.DictReader(f)
            for row in reader:
                metric = row['Metric']
                try:
                    avg_metrics[metric] = float(row['Avg_s'])
                except:
                    avg_metrics[metric] = None

    # JSON‐encode for Chart.js in your template
    avg_metrics_json = json.dumps(avg_metrics)

    return render_template('results.html',
        broker_name       = broker_name,
        ping_timestamps   = ping_ts,
        ping_delays       = ping_d,
        mtbf              = mtbf,
        mttr              = mttr,
        client_ids        = c_ids,
        client_times      = c_times,
        avg_metrics_json  = avg_metrics_json
    )


@app.route('/download/<path:filename>')
def download_file(filename):
    full = os.path.join(app.root_path, filename)
    return send_from_directory(os.path.dirname(full), os.path.basename(full), as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True)
