import paho.mqtt.client as mqtt
import time
from datetime import datetime
import os
import argparse

# Setup command-line arguments
parser = argparse.ArgumentParser(description="MQTT Broker Pinger")
parser.add_argument("--name", required=True, help="Broker name (used for output file naming)")
parser.add_argument("--port", required=True, help="Broker port number ")
parser.add_argument("--duration", required=True, help="Duration in seconds")
args = parser.parse_args()

# Parameters from CLI
broker_name = args.name
BROKER = "localhost"
PORT = int(args.port) 
INTERVAL = 5  # seconds
DURATION = int(args.duration)  # seconds
LOG_FILE = f"logs/availability_log__{broker_name}.txt"

# Output file setup
os.makedirs("logs", exist_ok=True)
file_path = f"logs/broker_availability_results_{broker_name}_{DURATION}.csv"

def check_broker():
    client = mqtt.Client()
    try:
        start = time.time()
        client.connect(BROKER, PORT, 3)
        client.disconnect()
        return "UP", time.time() - start
    except:
        return "DOWN", None

# Tracking UP and DOWN durations
up_times = []
down_times = []
last_state = None
last_change_time = time.time()

start_time = time.time()

while time.time() - start_time < DURATION:
    status, response_time = check_broker()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current_time = time.time()

    # Transition tracking
    if last_state and last_state != status:
        duration = current_time - last_change_time
        if last_state == "UP":
            up_times.append(duration)
        elif last_state == "DOWN":
            down_times.append(duration)
        last_change_time = current_time

    # Handle case where the first state is recorded
    if last_state is None:
        last_change_time = current_time
    last_state = status

    with open(file_path, "a") as f:
        if status == "UP":
            f.write(f"{now} - {status} - {response_time:.4f} s\n")
        else:
            f.write(f"{now} - {status}\n")
    print(f"{now} - {status}")
    time.sleep(INTERVAL)

# After loop ends, capture last interval
final_duration = time.time() - last_change_time
if last_state == "UP":
    up_times.append(final_duration)
else:
    down_times.append(final_duration)

# MTBF and MTTR Calculations
MTBF = sum(up_times) / len(up_times) if up_times else 0
MTTR = sum(down_times) / len(down_times) if down_times else 0
availability = MTBF / (MTBF + MTTR) if (MTBF + MTTR) != 0 else 0
failure_rate = 1 / MTBF if MTBF != 0 else 0

# Output to log
print("\n--- Availability Analysis ---")
print(f"MTBF: {MTBF:.2f} s")
print(f"MTTR: {MTTR:.2f} s")
print(f"Availability: {availability:.4f}")
print(f"Failure Rate (λ): {failure_rate:.6f}")

# Optionally write to file
with open(file_path, "w") as f:
    f.write("Metric,Value\n")
    f.write(f"MTBF,{MTBF:.2f}\n")
    f.write(f"MTTR,{MTTR:.2f}\n")
    f.write(f"Availability,{availability:.4f}\n")
    f.write(f"Failure Rate,{failure_rate:.6f}\n")
