#!/usr/bin/env python3
import os
import time
import argparse
from datetime import datetime
import logging
import paho.mqtt.client as mqtt

def parse_args():
    parser = argparse.ArgumentParser(
        description="Measure MQTT delays and save both line-by-line and summary stats"
    )
    parser.add_argument("--name", default="localhost",
                        help="MQTT broker hostname or IP (used in filenames)")
    parser.add_argument("--port", type=int, default=1883,
                        help="MQTT broker port")
    parser.add_argument("--topic", default="test/topic",
                        help="Topic to SUBSCRIBE to for measuring subscription delay")
    parser.add_argument("--duration", type=int, required=True,
                        help="Total test duration in seconds")
    parser.add_argument("--interval", type=float, default=5.0,
                        help="Interval (seconds) between PINGREQs (can be fractional)")
    return parser.parse_args()

def make_ping_log(name):
    """
    Create the per-ping CSV:
      results/broker_pinger_results_<name>.csv
    with header "timestamp,delay"
    """
    path = os.path.join("results", f"broker_pinger_results_{name}.csv")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("timestamp,delay\n")
    return path

def on_connect(client, userdata, flags, rc, properties=None):
    """Fired when CONNECT completes."""
    now   = time.time()
    delay = now - userdata["conn_start"]
    userdata["conn_delays"].append(delay)
    print(f"[CONNECT] Delay: {delay:.4f}s")
    # immediately SUBSCRIBE and time it
    userdata["sub_start"] = time.time()
    client.subscribe(userdata["topic"])

def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    """Fired when SUBSCRIBE is acknowledged."""
    now   = time.time()
    delay = now - userdata["sub_start"]
    userdata["sub_delays"].append(delay)
    print(f"[SUBSCRIBE] Delay: {delay:.4f}s")

def on_log(client, userdata, level, buf):
    """
    All Paho log messages flow here.  We watch for PINGRESP
    so we can compute RTT and append it to the per-ping CSV.
    """
    if "PINGRESP" in buf:
        now = time.time()
        rtt = now - userdata["ping_start"]
        userdata["ping_rtts"].append(rtt)
        userdata["total_ping_received"] += 1
        print(f"[PINGRESP] RTT: {rtt:.4f}s")

        # append line-by-line to CSV
        with open(userdata["ping_log"], "a") as f:
            f.write(f"{now:.6f},{rtt:.6f}\n")

def summarize(data):
    """Compute min, max, avg, count over a list of floats."""
    if not data:
        return None, None, None, 0
    mn  = min(data)
    mx  = max(data)
    avg = sum(data)/len(data)
    return mn, mx, avg, len(data)

def main():
    args = parse_args()

    # enable DEBUG logging so on_log events fire
    logging.basicConfig(level=logging.DEBUG)

    # in-memory metrics store
    metrics = {
        "conn_start":          None,
        "sub_start":           None,
        "ping_start":          None,
        "topic":               args.topic,
        "conn_delays":         [],
        "sub_delays":          [],
        "ping_rtts":           [],
        "total_ping_sent":     0,
        "total_ping_received": 0
    }

    # prepare the per-ping CSV
    metrics["ping_log"] = make_ping_log(args.name)

    # force MQTT v3.1.1 so our callback signatures match
    client = mqtt.Client(userdata=metrics, protocol=mqtt.MQTTv311)
    client.enable_logger()

    client.on_connect   = on_connect
    client.on_subscribe = on_subscribe
    client.on_log       = on_log

    # asynchronously connect
    metrics["conn_start"] = time.time()
    client.connect_async("localhost", args.port, keepalive=int(args.interval))
    client.loop_start()

    # give one full interval before first ping
    time.sleep(args.interval)

    # ping loop
    start = time.time()
    while time.time() - start < args.duration:
        metrics["total_ping_sent"] += 1
        metrics["ping_start"] = time.time()
        # Paho’s public .ping() may be missing—fall back to private API
        if hasattr(client, "ping"):
            client.ping()
        else:
            client._send_pingreq()
        time.sleep(args.interval)

    # tear down
    client.loop_stop()
    client.disconnect()

    # compute summaries
    conn_stats = summarize(metrics["conn_delays"])
    sub_stats  = summarize(metrics["sub_delays"])
    ping_stats = summarize(metrics["ping_rtts"])

    # print console summary
    print("\n=== Summary ===")
    print(f"PINGREQ sent: {metrics['total_ping_sent']}, "
          f"PINGRESP recv: {metrics['total_ping_received']}")
    for label, stats in [
        ("Connection Setup", conn_stats),
        ("Subscription",     sub_stats),
        ("Ping RTT",         ping_stats)
    ]:
        mn, mx, avg, cnt = stats
        if cnt:
            print(f"{label:18s} | min: {mn:.4f}s  max: {mx:.4f}s  "
                  f"avg: {avg:.4f}s  count: {cnt}")
        else:
            print(f"{label:18s} | no data")

    # write the 3-line summary CSV
    os.makedirs("results", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_file = os.path.join(
        "results",
        f"mqtt_stats_{args.name}_{args.port}_{ts}.csv"
    )
    with open(summary_file, "w") as f:
        f.write("Metric,Min_s,Max_s,Avg_s,Count\n")
        f.write(f"ConnectionSetup,{conn_stats[0] or ''},"
                f"{conn_stats[1] or ''},{conn_stats[2] or ''},"
                f"{conn_stats[3]}\n")
        f.write(f"Subscription,{sub_stats[0] or ''},"
                f"{sub_stats[1] or ''},{sub_stats[2] or ''},"
                f"{sub_stats[3]}\n")
        f.write(f"PingRTT,{ping_stats[0] or ''},"
                f"{ping_stats[1] or ''},{ping_stats[2] or ''},"
                f"{ping_stats[3]}\n")
        f.write(f"PingREQ_Sent,,,,{metrics['total_ping_sent']}\n")
        f.write(f"PingRESP_Recv,,,,{metrics['total_ping_received']}\n")

    print(f"\nStats saved to {summary_file}")

if __name__ == "__main__":
    main()
