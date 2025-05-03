#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import time
import argparse
from datetime import datetime
import os

# Setup command-line arguments
parser = argparse.ArgumentParser(
    description="MQTT Broker Maximum Client Connection and Payload Size Evaluation"
)
parser.add_argument("--name", required=True, help="Broker name (used for output file naming)")
parser.add_argument("--port", required=True, type=int, help="Broker port number")
parser.add_argument("--clients", required=True, type=int, help="Maximum number of clients to attempt to connect")
parser.add_argument("--payload_size", required=True, type=int, help="Size of the payload to publish (in bytes)")
args = parser.parse_args()

broker_name = args.name
PORT = args.port
MAX_CLIENTS = args.clients
PAYLOAD_SIZE = args.payload_size

# For simplicity, we assume the broker is running on localhost.
BROKER = "localhost"
TOPIC = "test"

# Generate a dummy payload of the given size (the actual content does not matter)
PAYLOAD = "X" * PAYLOAD_SIZE

# Compute the payload size in bytes (should match the provided payload_size when using UTF-8 encoding)
computed_payload_size = len(PAYLOAD.encode("utf-8"))
print(f"Using payload of size: {computed_payload_size} bytes")

# Prepare output file logging
os.makedirs("results", exist_ok=True)
PAYLOAD_SIZE = args.payload_size
log_file = f"results/max_clients_results_{broker_name}_{MAX_CLIENTS}_P_{PAYLOAD_SIZE}.csv"

connection_times = []
successful_clients = 0

print("Starting maximum clients evaluation...")

for i in range(1, MAX_CLIENTS + 1):
    client_id = f"client{i}"
    # Instantiate the client with all parameters passed explicitly as keywords.
    client = mqtt.Client(
        client_id=client_id,
        clean_session=True,
        userdata=None,
        protocol=mqtt.MQTTv311,
        transport="tcp",
        callback_api_version=1  # Force legacy callback API.
    )
    start_time = time.time()
    try:
        client.connect(BROKER, PORT, keepalive=5)
        # Publish the dummy payload to the test topic.
        client.publish(TOPIC, PAYLOAD)
        client.disconnect()
        connection_time = time.time() - start_time
        connection_times.append(connection_time)
        successful_clients += 1
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Client {i} connected, connection time: {connection_time:.4f} s")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Client {i} failed to connect. Error: {e}")
        # Stop testing further clients if a connection failure occurs.
        break

if connection_times:
    total_clients = len(connection_times)
    avg_time = sum(connection_times) / total_clients
    max_time = max(connection_times)
    min_time = min(connection_times)
    # Compute average jitter as the average absolute difference between consecutive connection times.
    jitters = [abs(connection_times[i] - connection_times[i - 1]) for i in range(1, total_clients)]
    avg_jitter = sum(jitters) / len(jitters) if jitters else 0

    print("\n--- Maximum Clients Evaluation Results ---")
    print(f"Total Clients Connected: {total_clients}")
    print(f"Average Connection Time: {avg_time:.4f} s")
    print(f"Maximum Connection Time: {max_time:.4f} s")
    print(f"Minimum Connection Time: {min_time:.4f} s")
    print(f"Average Jitter: {avg_jitter:.4f} s")
else:
    print("No clients were able to connect.")

# Write detailed results, including the payload size, to a CSV file.
with open(log_file, "w") as f:
    f.write("Client,Connection_Time(s)\n")
    for idx, ct in enumerate(connection_times, start=1):
        f.write(f"{idx},{ct:.4f}\n")
    f.write("\n")
    f.write("Metric,Value\n")
    f.write(f"Total_Clients,{len(connection_times)}\n")
    f.write(f"Average_Connection_Time,{avg_time:.4f}\n")
    f.write(f"Maximum_Connection_Time,{max_time:.4f}\n")
    f.write(f"Minimum_Connection_Time,{min_time:.4f}\n")
    f.write(f"Average_Jitter,{avg_jitter:.4f}\n")
    f.write(f"Payload_Size_Bytes,{computed_payload_size}\n")
