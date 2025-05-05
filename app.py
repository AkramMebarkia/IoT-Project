import csv
import os
import sys
import glob
import json
import uuid
import threading
import subprocess
import requests
import docker
import time
from datetime import datetime

from flask import (
    Flask, render_template, request,
    send_from_directory, jsonify
)

app = Flask(__name__)

# Node-RED Admin API URL
NODE_RED_URL = 'http://localhost:1880'

# Broker container IDs
BROKER_IDS = {
    'mosquitto': 'f9d12cd8dcabc8fcad6f5ab68c9a9b8e9a5ed018e18385d55c3dd941109a3690',
    'activemq': 'cf0a288b8762ffc521693e234a2507e93ecd7ccaea17e5e5a0faa89ff80227a4',
    'nanomq': '7c1c0838010b887742305d6a8a73ba3c5ad435d951f1a8ceb07e1edc5e9c1f1b',
    'hivemq': 'c2cd7bbef9eb24857933a08830afdc7544fd3001839d0ac1f7af5a36b7c9b8b6',
    'emqx': 'd51a342d9f098ce4452d64b11373c896a7ada477ec7d2ef446f51db1624f01e4',
    'rabbitmq': 'b9eae0064bf3aaabd8438e6a4269db4bdf9c7970eec384b8f824111c6e7fd22a',
    'vernemq': '637ccaec617e7b403f984ec4f8c6961aebb995f024db451a1de94eb94c3723ea'
}

# Directories
RESULTS_DIR = os.path.join(app.root_path, 'results')
LOGS_DIR = os.path.join(app.root_path, 'logs')
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# Job tracking
job_status = {}  # job_id -> {'step1':..., 'step2':..., 'step3':..., 'monitoring':...}

def new_id():
    return uuid.uuid4().hex[:8]

def monitor_container_stats(container_id, csv_path, stop_event):
    """Monitor Docker container stats and write to CSV until stop_event is set"""
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['timestamp', 'cpu_percent', 'mem_usage', 'mem_limit',
                           'net_rx', 'net_tx', 'block_read', 'block_write'])
            
            stats_gen = container.stats(stream=True, decode=True)
            
            while not stop_event.is_set():
                try:
                    stats = next(stats_gen)
                    
                    # Calculate CPU percentage with error handling
                    cpu_stats = stats.get('cpu_stats', {})
                    precpu_stats = stats.get('precpu_stats', {})
                    
                    cpu_delta = cpu_stats.get('cpu_usage', {}).get('total_usage', 0) - \
                              precpu_stats.get('cpu_usage', {}).get('total_usage', 0)
                    system_delta = cpu_stats.get('system_cpu_usage', 0) - \
                                 precpu_stats.get('system_cpu_usage', 0)
                    
                    cpu_percent = (cpu_delta / system_delta) * 100 if system_delta != 0 else 0
                    
                    # Memory metrics with error handling
                    memory_stats = stats.get('memory_stats', {})
                    mem_usage = memory_stats.get('usage', 0)
                    mem_limit = memory_stats.get('limit', 0)
                    
                    # Network metrics with error handling
                    networks = stats.get('networks', {})
                    net_rx = sum(net.get('rx_bytes', 0) for net in networks.values())
                    net_tx = sum(net.get('tx_bytes', 0) for net in networks.values())
                    
                    # Block I/O metrics with error handling
                    blkio_stats = stats.get('blkio_stats', {}).get('io_service_bytes_recursive', [])
                    block_read = sum(blk.get('value', 0) for blk in blkio_stats if blk.get('op') == 'Read')
                    block_write = sum(blk.get('value', 0) for blk in blkio_stats if blk.get('op') == 'Write')
                    
                    # Write metrics
                    timestamp = datetime.now().isoformat()
                    writer.writerow([
                        timestamp,
                        round(cpu_percent, 2),
                        mem_usage,
                        mem_limit,
                        net_rx,
                        net_tx,
                        block_read,
                        block_write
                    ])
                    csvfile.flush()
                except (StopIteration, KeyError, ZeroDivisionError) as e:
                    print(f"Error processing stats: {str(e)}")
                    time.sleep(1)
                    continue
                except Exception as e:
                    print(f"Critical error: {str(e)}")
                    break
    except Exception as e:
        print(f"Monitoring setup failed: {str(e)}")
    finally:
        stop_event.set()

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
  
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'

    # Get container ID from broker name
    broker_name = args['broker_name'].lower()
    container_id = BROKER_IDS.get(broker_name)
    if not container_id:
        job_status[job_id] = {'error': 'Invalid broker name'}
        return

    # Setup resource monitoring
    resource_csv = os.path.join(RESULTS_DIR, f'resource_usage_{broker_name}_{job_id}.csv')
    stop_event = threading.Event()
    monitor_thread = threading.Thread(
        target=monitor_container_stats,
        args=(container_id, resource_csv, stop_event),
        daemon=True
    )
    
    job_status[job_id] = {
        'step1': 'pending',
        'step2': 'pending',
        'step3': 'pending',
        'monitoring': 'running'
    }
    
    monitor_thread.start()

    try:
        # Test steps
        steps = [
            ('broker_pinger.py', 'step1', ['--duration', args['duration']]),
            ('broker_availability.py', 'step2', ['--duration', args['duration']]),
            ('max_clients_test.py', 'step3', 
             ['--clients', args['max_clients'], '--payload_size', args['payload_size']]),
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
                     os.path.join(app.root_path, 'evaluation_scripts', script),
                     *base_args,
                     *extra
                    ],
                    check=True, env=env, capture_output=True
                )
                job_status[job_id][key] = 'done'
            except subprocess.CalledProcessError as e:
                print(f"Error in {script}: {e.stderr.decode()}")
                job_status[job_id][key] = 'error'
    finally:
        # Stop monitoring when tests complete or error occurs
        stop_event.set()
        monitor_thread.join()
        job_status[job_id]['monitoring'] = 'completed'

@app.route('/run_tests', methods=['POST'])
def run_tests():
    args = request.get_json()
    job_id = uuid.uuid4().hex
    threading.Thread(
        target=run_tests_in_background,
        args=(job_id, args),
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
    job_id = request.args.get('job_id')
    duration = request.args.get('duration', '60')
    max_clients = request.args.get('max_clients', '100')
    payload = request.args.get('payload_size', '256')
    broker_port = request.args.get('broker_port', '1883')

    # Load resource data
    resource_data = []
    resource_csv = os.path.join(RESULTS_DIR, f'resource_usage_{broker_name}_{job_id}.csv')
    if os.path.exists(resource_csv):
        with open(resource_csv) as f:
            reader = csv.DictReader(f)
            resource_data = list(reader)

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
        broker_name=broker_name,
        ping_timestamps=ping_ts,
        ping_delays=ping_d,
        mtbf=mtbf,
        mttr=mttr,
        client_ids=c_ids,
        client_times=c_times,
        avg_metrics_json=avg_metrics_json,
        resource_data=json.dumps(resource_data),
        job_id=job_id
    )

@app.route('/download/<path:filename>')
def download_file(filename):
    full = os.path.join(app.root_path, filename)
    return send_from_directory(os.path.dirname(full), os.path.basename(full), as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)