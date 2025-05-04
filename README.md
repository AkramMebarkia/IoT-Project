# IoT Broker Evaluation Framework

A complete end-to-end solution to **design**, **deploy**, and **evaluate** MQTT simulations against any broker (ActiveMQ, Mosquitto, HiveMQ, NanoMQ, EMQX, RabbitMQ) using:

* **Node-RED** for flow orchestration & real-time dashboards
* **Flask** web UI for simulation design & result visualization
* Automated **performance tests**: ping RTT, availability (MTBF/MTTR), max-clients scalability

---

## 🚀 Features

1. **Simulation Designer**

   * Define any number of **Publishers** (name, topic, interval, random range, QoS)
   * Define any number of **Subscribers** (name, topic, QoS, widget type & units)
   * One-click deploy into Node-RED flows

2. **Broker Settings**

   * Select from 6 popular MQTT brokers by name (Docker network)
   * Configure port, availability duration, max-clients, payload size

3. **Automated Evaluation**

   * **Ping RTT** series
   * **Availability** (Mean Time Between Failures & Mean Time To Repair)
   * **Max-Clients** connection time & jitter
   * Background thread + progress modal

4. **Results Dashboard**

   * Interactive Chart.js plots
   * CSV download for all metrics

---

## 🏦 Prerequisites

* **Docker** & **Docker Compose** (to spin up your broker & Node-RED)
* **Python 3.8+**
* **Node-RED** (with `node-red-dashboard` & `node-red-node-mqtt`)
* Python packages: `flask`, `requests`

---

## 🛠️ Installation

1. **Clone the repo**

   ```bash
   git clone https://github.com/yourusername/iot-broker-eval.git
   cd iot-broker-eval
   ```

2. **Install Python deps**

   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Bring up Docker services**

   ```bash
   docker-compose up -d
   ```

   This starts:

   * Your chosen MQTT broker(s)
   * A Node-RED instance at `http://localhost:1880`

---

## ⚙️ Configuration

* **`app.py`**:

  * `NODE_RED_URL` → your Node-RED URL
  * `BROKER_CONFIG_ID` → your Node-RED MQTT-broker config node ID
* **`docker-compose.yml`**:

  * Add/remove broker services
  * Expose ports & Docker network

---

## 🎯 Usage

1. **Run the Flask app**

   ```bash
   flask run
   # → http://localhost:5000
   ```

2. **Design Simulation**

   * Add **Publishers** & **Subscribers**, choose QoS & widget UI
   * Select **Broker** from dropdown
   * Click **Deploy Simulation**
   * Node-RED will auto-generate two “Sim-pub” & “Sim-sub” tabs

3. **Run Evaluation**

   * Configure availability duration, max-clients, payload size
   * Click **Run Evaluation**
   * Watch the **progress modal**
   * After completion, you’ll be redirected to `/results/<broker>`

4. **View & Download Results**

   * Interactive plots for RTT, MTBF/MTTR, connection times
   * Download CSVs via “Download” links

---

## 🏗️ Architecture

```
[Flask UI] ← JSON → [Node-RED Admin API] → [Node-RED Flows]
       │
       ↓
 background tests
       ↓
[broker_pinger.py] → ping CSV
[broker_availability.py] → logs CSV
[max_clients_test.py]  → clients CSV
```
![Untitled-2025-01-17-1805](https://github.com/user-attachments/assets/729e3e48-3d8e-496e-a645-e3e42e946f61)

* **Node-RED**

  * **Inject** → **Splitter** → N × **Function → JSON → MQTT Out**
  * **MQTT In** → **Function** → **Gauge/Text** dashboard

* **Evaluation Scripts**

  * Pure-Python, run in background thread with `subprocess`
  * Output CSVs to `results/` & `logs/`

---

## 🔧 Customization

* **Add new broker**:

  * In `index.html`, add a `<option>`
  * In `app.py`’s `/deploy_simulation`, ensure you map `broker_name` → `broker` & `port`

* **QoS support**:

  * QoS dropdown for Pubs & Subs
  * Passed into Node-RED config: `"qos": "<value>"`

---

## 🤝 Contributing

1. Fork & clone
2. Create a feature branch
3. Write tests & update README
4. Open a PR

---

## 📄 License

MIT © \[Your Name]
Feel free to reuse & adapt!

---

> **Questions?**
> Open an issue or drop me an email at `akremmeb577@gmail.com`
