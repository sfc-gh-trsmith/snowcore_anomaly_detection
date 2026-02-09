"""
Synthetic Data Generator for Snowcore Anomaly Detection Demo
Generates realistic sensor data with embedded humidity-scrap correlation pattern.

Key Insight: Batches processed when Layup Room humidity > 65% show 3x higher scrap rates
6 hours later during autoclave cure cycle.
"""

import random
import csv
import os
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42
random.seed(SEED)

OUTPUT_DIR = Path(__file__).parent / "generated"
OUTPUT_DIR.mkdir(exist_ok=True)

NUM_DAYS = 90
SAMPLES_PER_DAY = 1440
BATCHES_PER_DAY = 8

ASSETS = {
    'LAYUP_ROOM': {
        'metrics': ['Humidity', 'Temperature', 'Particulates'],
        'ranges': [(40, 70), (20, 25), (0, 100)],
        'asset_type': 'ENVIRONMENT'
    },
    'LAYUP_BOT_01': {
        'metrics': ['TensionForce', 'FeedRate', 'MaterialTemp'],
        'ranges': [(100, 150), (0.5, 2.0), (20, 30)],
        'asset_type': 'ROBOT'
    },
    'LAYUP_BOT_02': {
        'metrics': ['TensionForce', 'FeedRate', 'MaterialTemp'],
        'ranges': [(100, 150), (0.5, 2.0), (20, 30)],
        'asset_type': 'ROBOT'
    },
    'AUTOCLAVE_01': {
        'metrics': ['Temperature', 'Pressure', 'VacuumLevel'],
        'ranges': [(150, 200), (80, 120), (-1.0, -0.8)],
        'asset_type': 'AUTOCLAVE'
    },
    'AUTOCLAVE_02': {
        'metrics': ['Temperature', 'Pressure', 'VacuumLevel'],
        'ranges': [(150, 200), (80, 120), (-1.0, -0.8)],
        'asset_type': 'AUTOCLAVE'
    },
    'CNC_MILL_01': {
        'metrics': ['SpindleSpeed', 'Vibration', 'CoolantTemp'],
        'ranges': [(8000, 12000), (0.1, 0.5), (15, 25)],
        'asset_type': 'CNC'
    },
    'CNC_MILL_02': {
        'metrics': ['SpindleSpeed', 'Vibration', 'CoolantTemp'],
        'ranges': [(8000, 12000), (0.1, 0.5), (15, 25)],
        'asset_type': 'CNC'
    },
    'QC_STATION_01': {
        'metrics': ['ScanTime', 'DefectCount', 'MeasurementDev'],
        'ranges': [(30, 60), (0, 5), (0.01, 0.1)],
        'asset_type': 'QC'
    },
    'QC_STATION_02': {
        'metrics': ['ScanTime', 'DefectCount', 'MeasurementDev'],
        'ranges': [(30, 60), (0, 5), (0.01, 0.1)],
        'asset_type': 'QC'
    }
}

def generate_sensor_value(base_low, base_high, drift=0, noise=0.05):
    base = random.uniform(base_low, base_high)
    noisy = base * (1 + random.gauss(0, noise)) + drift
    return round(noisy, 2)

def generate_iot_streaming():
    """Generate IOT_STREAMING table data (Sparkplug B format)"""
    print("Generating IOT streaming data...")
    
    records = []
    start_date = datetime.now() - timedelta(days=NUM_DAYS)
    
    for day in range(NUM_DAYS):
        current_date = start_date + timedelta(days=day)
        
        is_high_humidity_day = random.random() < 0.20
        
        for minute in range(0, SAMPLES_PER_DAY, 5):
            timestamp = current_date + timedelta(minutes=minute)
            ts_epoch = int(timestamp.timestamp() * 1000)
            
            for asset_id, config in ASSETS.items():
                topic = f"spBv1.0/SNOWCORE/DDATA/LINE_01/{asset_id}"
                
                metrics = []
                for i, (metric, (low, high)) in enumerate(zip(config['metrics'], config['ranges'])):
                    drift = 0
                    if asset_id == 'LAYUP_ROOM' and metric == 'Humidity' and is_high_humidity_day:
                        if 6 <= (minute // 60) < 12:
                            drift = 15
                    
                    value = generate_sensor_value(low, high, drift=drift)
                    
                    metrics.append({
                        'name': metric,
                        'alias': i + 1,
                        'timestamp': ts_epoch,
                        'dataType': 'Float',
                        'value': value
                    })
                
                import json
                records.append({
                    'RECORD_METADATA': json.dumps({"topic": topic, "partition": 0, "offset": len(records)}),
                    'RECORD_CONTENT': json.dumps({"timestamp": ts_epoch, "metrics": metrics, "seq": minute % 256}),
                    'INGESTION_TIME': timestamp.isoformat()
                })
    
    with open(OUTPUT_DIR / 'iot_streaming.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['RECORD_METADATA', 'RECORD_CONTENT', 'INGESTION_TIME'])
        writer.writeheader()
        writer.writerows(records[:100000])
    
    print(f"  Generated {len(records[:100000])} IOT streaming records")
    return records

def generate_production_batches():
    """Generate production batches with humidity-scrap correlation"""
    print("Generating production batches...")
    
    batches = []
    start_date = datetime.now() - timedelta(days=NUM_DAYS)
    
    for day in range(NUM_DAYS):
        current_date = start_date + timedelta(days=day)
        is_high_humidity_day = random.random() < 0.20
        
        for batch_num in range(BATCHES_PER_DAY):
            batch_id = f"BATCH-{current_date.strftime('%Y%m%d')}-{batch_num+1:02d}"
            
            layup_start = current_date + timedelta(hours=batch_num * 3)
            layup_end = layup_start + timedelta(hours=2)
            cure_start = layup_end + timedelta(minutes=30)
            cure_end = cure_start + timedelta(hours=4)
            trim_start = cure_end + timedelta(minutes=15)
            trim_end = trim_start + timedelta(hours=1)
            qc_timestamp = trim_end + timedelta(minutes=30)
            
            high_humidity_batch = is_high_humidity_day and 2 <= batch_num <= 4
            
            if high_humidity_batch:
                scrap_prob = 0.16
                delamination_base = 40
            else:
                scrap_prob = 0.05
                delamination_base = 10
            
            scrap_flag = random.random() < scrap_prob
            delamination_score = generate_sensor_value(delamination_base, delamination_base + 30)
            
            if scrap_flag:
                qc_result = 'REJECT'
                delamination_score = min(100, delamination_score + 30)
            else:
                qc_result = 'PASS'
            
            batches.append({
                'BATCH_ID': batch_id,
                'PRODUCT_LINE': 'AVALANCHE_X1',
                'LAYUP_START': layup_start.isoformat(),
                'LAYUP_END': layup_end.isoformat(),
                'CURE_START': cure_start.isoformat(),
                'CURE_END': cure_end.isoformat(),
                'TRIM_START': trim_start.isoformat(),
                'TRIM_END': trim_end.isoformat(),
                'QC_TIMESTAMP': qc_timestamp.isoformat(),
                'QC_RESULT': qc_result,
                'SCRAP_FLAG': scrap_flag,
                'DELAMINATION_SCORE': round(delamination_score, 1)
            })
    
    with open(OUTPUT_DIR / 'production_batches.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=batches[0].keys())
        writer.writeheader()
        writer.writerows(batches)
    
    print(f"  Generated {len(batches)} production batches")
    
    normal_batches = sum(1 for b in batches if not b['SCRAP_FLAG'] and b['DELAMINATION_SCORE'] < 40)
    high_humidity_batches = sum(1 for b in batches if b['DELAMINATION_SCORE'] >= 40)
    normal_scrap = sum(1 for b in batches if b['SCRAP_FLAG'] and b['DELAMINATION_SCORE'] < 40)
    high_humidity_scrap = sum(1 for b in batches if b['SCRAP_FLAG'] and b['DELAMINATION_SCORE'] >= 40)
    
    print(f"  Scrap rates - Normal: {normal_scrap}/{len(batches) - high_humidity_batches} = {100*normal_scrap/(len(batches) - high_humidity_batches):.1f}%")
    print(f"  Scrap rates - High Humidity: {high_humidity_scrap}/{high_humidity_batches} = {100*high_humidity_scrap/max(1, high_humidity_batches):.1f}%")
    
    return batches

def generate_cure_results(batches):
    """Generate cure results with humidity correlation"""
    print("Generating cure results...")
    
    results = []
    for batch in batches:
        high_humidity = batch['DELAMINATION_SCORE'] >= 40
        
        if high_humidity:
            humidity_avg = generate_sensor_value(65, 72)
            humidity_peak = generate_sensor_value(68, 78)
        else:
            humidity_avg = generate_sensor_value(45, 60)
            humidity_peak = generate_sensor_value(50, 64)
        
        results.append({
            'BATCH_ID': batch['BATCH_ID'],
            'AUTOCLAVE_ID': random.choice(['AUTOCLAVE_01', 'AUTOCLAVE_02']),
            'CURE_TIMESTAMP': batch['CURE_END'],
            'LAYUP_HUMIDITY_AVG': humidity_avg,
            'LAYUP_HUMIDITY_PEAK': humidity_peak,
            'SCRAP_FLAG': batch['SCRAP_FLAG'],
            'DELAMINATION_SCORE': batch['DELAMINATION_SCORE'],
            'FAILURE_MODE': 'MOISTURE_DELAMINATION' if batch['SCRAP_FLAG'] and high_humidity else (
                'CURE_DEFECT' if batch['SCRAP_FLAG'] else None
            )
        })
    
    with open(OUTPUT_DIR / 'cure_results.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    
    print(f"  Generated {len(results)} cure results")
    return results

def generate_maintenance_logs():
    """Generate historical maintenance logs"""
    print("Generating maintenance logs...")
    
    failure_reasons = [
        ('Vacuum Leak', 120, 'Replaced vacuum seal B'),
        ('Temperature Excursion', 60, 'Recalibrated thermocouple'),
        ('Pressure Drop', 90, 'Replaced pressure relief valve'),
        ('Vibration Alert', 45, 'Balanced spindle assembly'),
        ('Coolant Flow', 30, 'Cleaned coolant filter'),
        ('Humidity Alarm', 15, 'Adjusted HVAC settings'),
    ]
    
    technicians = ['T001', 'T002', 'T003', 'T004']
    
    logs = []
    start_date = datetime.now() - timedelta(days=NUM_DAYS * 2)
    
    for i in range(200):
        timestamp = start_date + timedelta(
            days=random.randint(0, NUM_DAYS * 2),
            hours=random.randint(6, 22),
            minutes=random.randint(0, 59)
        )
        
        failure = random.choice(failure_reasons)
        asset = random.choice(list(ASSETS.keys()))
        
        logs.append({
            'LOG_ID': f'LOG-{i+1:05d}',
            'ASSET_ID': asset,
            'TIMESTAMP': timestamp.isoformat(),
            'FAILURE_REASON': failure[0],
            'DOWNTIME_MINUTES': failure[1] + random.randint(-15, 30),
            'TECHNICIAN_ID': random.choice(technicians),
            'WORK_ORDER_ID': f'WO-{timestamp.strftime("%Y%m%d")}-{i+1:03d}',
            'RESOLUTION_NOTES': failure[2]
        })
    
    with open(OUTPUT_DIR / 'maintenance_logs.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=logs[0].keys())
        writer.writeheader()
        writer.writerows(logs)
    
    print(f"  Generated {len(logs)} maintenance logs")
    return logs

def generate_anomaly_events():
    """Generate historical anomaly events"""
    print("Generating anomaly events...")
    
    anomaly_types = [
        ('VACUUM_LEAK', 'HIGH', 'Vacuum seal degradation'),
        ('TEMP_EXCURSION', 'MEDIUM', 'Heater element drift'),
        ('PRESSURE_DROP', 'HIGH', 'Pressure relief valve leak'),
        ('VIBRATION_SPIKE', 'LOW', 'Spindle imbalance'),
        ('HUMIDITY_ALERT', 'MEDIUM', 'HVAC capacity issue'),
    ]
    
    events = []
    start_date = datetime.now() - timedelta(days=NUM_DAYS)
    
    for i in range(50):
        timestamp = start_date + timedelta(
            days=random.randint(0, NUM_DAYS),
            hours=random.randint(6, 22)
        )
        
        anomaly = random.choice(anomaly_types)
        asset = random.choice([a for a in ASSETS.keys() if a != 'LAYUP_ROOM'])
        
        events.append({
            'EVENT_ID': f'ANO-{i+1:05d}',
            'ASSET_ID': asset,
            'TIMESTAMP': timestamp.isoformat(),
            'ANOMALY_TYPE': anomaly[0],
            'ANOMALY_SCORE': round(random.uniform(0.6, 0.99), 2),
            'SEVERITY': anomaly[1],
            'ROOT_CAUSE': anomaly[2],
            'SUGGESTED_FIX': f'Review {anomaly[0].lower().replace("_", " ")} procedure',
            'RESOLVED': random.random() < 0.8
        })
    
    with open(OUTPUT_DIR / 'anomaly_events.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=events[0].keys())
        writer.writeheader()
        writer.writerows(events)
    
    print(f"  Generated {len(events)} anomaly events")
    return events

def generate_financial_summary():
    """Generate financial summary for before/after comparison"""
    print("Generating financial summary...")
    
    summaries = []
    start_date = datetime.now() - timedelta(days=365)
    
    for month_offset in range(12):
        month_date = start_date + timedelta(days=month_offset * 30)
        
        is_after = month_offset >= 9
        
        if is_after:
            downtime_hours = generate_sensor_value(25, 35)
            scrap_count = int(generate_sensor_value(35, 45))
            corrective_pct = 0.20
            oee = generate_sensor_value(74, 80)
        else:
            downtime_hours = generate_sensor_value(45, 55)
            scrap_count = int(generate_sensor_value(55, 70))
            corrective_pct = 0.80
            oee = generate_sensor_value(62, 68)
        
        downtime_cost = downtime_hours * 25000
        scrap_cost = scrap_count * 8000
        total_maint_hrs = generate_sensor_value(150, 200)
        corrective_hrs = total_maint_hrs * corrective_pct
        preventive_hrs = total_maint_hrs * (1 - corrective_pct)
        labor_variance = corrective_hrs * 75
        
        summaries.append({
            'MONTH': month_date.strftime('%Y-%m-01'),
            'DOWNTIME_HOURS': round(downtime_hours, 1),
            'DOWNTIME_COST_USD': round(downtime_cost, 0),
            'SCRAP_COUNT': scrap_count,
            'SCRAP_COST_USD': round(scrap_cost, 0),
            'CORRECTIVE_MAINT_HRS': round(corrective_hrs, 1),
            'PREVENTIVE_MAINT_HRS': round(preventive_hrs, 1),
            'LABOR_VARIANCE_USD': round(labor_variance, 0),
            'INVENTORY_VALUE_USD': 2000000 if not is_after else 1700000,
            'STOCKOUT_EVENTS': random.randint(8, 15) if not is_after else random.randint(2, 5),
            'OEE_PCT': round(oee, 1),
            'SCENARIO': 'AFTER' if is_after else 'BEFORE'
        })
    
    with open(OUTPUT_DIR / 'financial_summary.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=summaries[0].keys())
        writer.writeheader()
        writer.writerows(summaries)
    
    print(f"  Generated {len(summaries)} financial summary records")
    return summaries

def generate_asset_status():
    """Generate current asset status for dashboard"""
    print("Generating asset status...")
    
    positions = {
        'LAYUP_ROOM': (0, 1),
        'LAYUP_BOT_01': (1, 0),
        'LAYUP_BOT_02': (1, 2),
        'AUTOCLAVE_01': (2, 0),
        'AUTOCLAVE_02': (2, 2),
        'CNC_MILL_01': (3, 0),
        'CNC_MILL_02': (3, 2),
        'QC_STATION_01': (4, 0),
        'QC_STATION_02': (4, 2),
    }
    
    statuses = []
    for asset_id, config in ASSETS.items():
        health = generate_sensor_value(70, 100)
        if health < 80:
            status = 'WARNING'
        elif health < 70:
            status = 'CRITICAL'
        else:
            status = 'HEALTHY'
        
        pos = positions.get(asset_id, (0, 0))
        
        statuses.append({
            'ASSET_ID': asset_id,
            'ASSET_NAME': asset_id.replace('_', ' ').title(),
            'ASSET_TYPE': config['asset_type'],
            'LINE_ID': 'LINE_01',
            'STATUS': status,
            'HEALTH_SCORE': round(health, 1),
            'LAST_ANOMALY_TIME': (datetime.now() - timedelta(hours=random.randint(1, 72))).isoformat(),
            'LAST_MAINTENANCE_TIME': (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat(),
            'POSITION_X': pos[0],
            'POSITION_Y': pos[1]
        })
    
    with open(OUTPUT_DIR / 'asset_status.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=statuses[0].keys())
        writer.writeheader()
        writer.writerows(statuses)
    
    print(f"  Generated {len(statuses)} asset status records")
    return statuses

def generate_knowledge_base():
    """Generate knowledge base entries for Cortex Search"""
    print("Generating knowledge base entries...")
    
    kb_entries = [
        {
            'DOC_TYPE': 'MANUAL',
            'ASSET_MODEL': 'AUTOCLAVE_2000',
            'COMPONENT_SECTION': 'Vacuum System',
            'ERROR_CODE': 'VAC-001',
            'TITLE': 'Vacuum Seal Replacement Procedure',
            'CONTENT': '''Vacuum Seal B Replacement Procedure for Autoclave 2000 Series:
            
1. Safety: Ensure autoclave is at ambient temperature and pressure. Lock out power.
2. Access: Remove the 8 hex bolts on the door seal housing using 13mm socket.
3. Inspection: Check seal groove for debris or damage. Clean with isopropyl alcohol.
4. Installation: Install new Vacuum Seal B (Part #VS-2847) starting at 12 o'clock position.
5. Verification: Apply vacuum to -0.95 bar and hold for 15 minutes. Accept if leak rate < 0.01 mbar/min.
6. Documentation: Record seal replacement in CMMS with batch traceability.

Common failure modes: Seal degradation from thermal cycling, contamination from resin outgassing.
Expected life: 500-800 cure cycles depending on operating conditions.''',
            'SOURCE_FILE': 'AUTOCLAVE_2000_MAINTENANCE_MANUAL.pdf'
        },
        {
            'DOC_TYPE': 'MANUAL',
            'ASSET_MODEL': 'CNC_MILL_5000',
            'COMPONENT_SECTION': 'Spindle Assembly',
            'ERROR_CODE': 'VIB-001',
            'TITLE': 'Spindle Vibration Calibration',
            'CONTENT': '''Spindle Vibration Sensor Calibration for CNC Mill 5000:
            
1. Prerequisites: Machine at operating temperature (min 30 min warmup). No tooling installed.
2. Access calibration mode: Control Panel > Service > Calibration > Spindle
3. Run baseline: Execute spindle ramp 0-12000 RPM over 60 seconds
4. Capture readings: Record vibration at 3000, 6000, 9000, 12000 RPM
5. Thresholds: 
   - Normal: < 0.3 G peak
   - Warning: 0.3-0.5 G peak
   - Critical: > 0.5 G peak
6. If above threshold, check spindle bearing preload and balance.

Typical causes of elevated vibration: Bearing wear, coolant contamination, imbalanced toolholder.''',
            'SOURCE_FILE': 'CNC_MILL_5000_CALIBRATION_GUIDE.pdf'
        },
        {
            'DOC_TYPE': 'CMMS_LOG',
            'ASSET_MODEL': 'AUTOCLAVE_2000',
            'COMPONENT_SECTION': 'Vacuum System',
            'ERROR_CODE': 'VAC-001',
            'TITLE': 'WO-20230915-047 Vacuum Leak Resolution',
            'CONTENT': '''Work Order: WO-20230915-047
Date: September 15, 2023
Asset: AUTOCLAVE_02
Technician: Mike Rodriguez

Problem: Vacuum decay rate exceeded 0.05 mbar/min during cure cycle. Batch BATCH-20230915-03 aborted.

Investigation: 
- Visual inspection found scoring on door seal groove
- Seal B showed hardening and cracking (1247 cycles since last replacement)
- No contamination detected in vacuum lines

Resolution:
- Replaced Vacuum Seal B with Part #VS-2847 (Lot: 2023-Q3-042)
- Cleaned and polished seal groove
- Verified vacuum hold: 0.008 mbar/min (within spec)

Root Cause: Extended seal life beyond recommended interval due to supply chain delay.

Recommendation: Increase safety stock of vacuum seals to prevent future delays.

Downtime: 2 hours 15 minutes
Parts Cost: $847
Labor Cost: $225''',
            'SOURCE_FILE': 'CMMS_EXPORT_2023Q3.json'
        },
        {
            'DOC_TYPE': 'CMMS_LOG',
            'ASSET_MODEL': 'LAYUP_ROOM',
            'COMPONENT_SECTION': 'HVAC',
            'ERROR_CODE': 'HUM-001',
            'TITLE': 'WO-20231022-089 Humidity Excursion Investigation',
            'CONTENT': '''Work Order: WO-20231022-089
Date: October 22, 2023
Asset: LAYUP_ROOM
Technician: Sarah Chen

Problem: Multiple batches from October 21-22 showing elevated delamination scores. 
QC flagged 6 batches for rework.

Investigation:
- Reviewed sensor data: Humidity peaked at 72% during 8am-12pm shift
- HVAC system running at capacity but unable to maintain setpoint
- Weather data showed unusual humidity spike (external 85% RH)
- Correlated affected batches to high-humidity layup window

Resolution:
- Adjusted HVAC dehumidification setpoint from 55% to 50%
- Added supplemental portable dehumidifier to layup area
- Implemented humidity trending alert at 60% threshold

Root Cause: HVAC sizing inadequate for extreme weather events. 
Correlation confirmed between layup humidity >65% and cure defects.

Cost Impact: 6 batches reworked @ $12,000 each = $72,000
Recommended CapEx: HVAC capacity upgrade ($150,000)
Payback: <3 months at current defect rate''',
            'SOURCE_FILE': 'CMMS_EXPORT_2023Q4.json'
        },
        {
            'DOC_TYPE': 'SOP',
            'ASSET_MODEL': 'AUTOCLAVE_2000',
            'COMPONENT_SECTION': 'Cure Cycle',
            'ERROR_CODE': None,
            'TITLE': 'Golden Batch Cure Profile for Avalanche X1',
            'CONTENT': '''Standard Operating Procedure: Avalanche X1 Cure Cycle
Document: SOP-CURE-001 Rev 3.2

Golden Batch Parameters:
- Ramp Rate: 2°C/min to 180°C
- Dwell: 120 minutes at 180°C ± 3°C
- Pressure: 100 psi ± 5 psi
- Vacuum: -0.95 bar minimum
- Cool Down: 3°C/min to 60°C before door open

Critical Control Points:
1. Pre-cure vacuum test: Must hold -0.95 bar for 5 min with <0.02 mbar/min leak rate
2. Temperature uniformity: All zones within ±3°C during dwell
3. Exotherm monitoring: If part temp exceeds bag temp by >10°C, extend dwell

Quality Gates:
- Delamination Score threshold: <25 (pass), 25-50 (review), >50 (reject)
- Void Content: <2% by volume
- Glass Transition Temp: >195°C (DMA verification)

Batch Release Criteria: All parameters within spec AND traceability complete.''',
            'SOURCE_FILE': 'SOP_CURE_AVALANCHE_X1.pdf'
        }
    ]
    
    with open(OUTPUT_DIR / 'knowledge_base.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'DOC_TYPE', 'ASSET_MODEL', 'COMPONENT_SECTION', 'ERROR_CODE',
            'TITLE', 'CONTENT', 'SOURCE_FILE', 'CHUNK_INDEX'
        ])
        writer.writeheader()
        for i, entry in enumerate(kb_entries):
            entry['CHUNK_INDEX'] = i
            writer.writerow(entry)
    
    print(f"  Generated {len(kb_entries)} knowledge base entries")
    return kb_entries

def main():
    print("=" * 60)
    print("Snowcore Anomaly Detection - Synthetic Data Generator")
    print(f"Seed: {SEED}")
    print("=" * 60)
    
    batches = generate_production_batches()
    generate_cure_results(batches)
    generate_maintenance_logs()
    generate_anomaly_events()
    generate_financial_summary()
    generate_asset_status()
    generate_knowledge_base()
    
    print("=" * 60)
    print(f"All data written to: {OUTPUT_DIR}")
    print("=" * 60)

if __name__ == '__main__':
    main()
