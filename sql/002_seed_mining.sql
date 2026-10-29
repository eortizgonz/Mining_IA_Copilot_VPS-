INSERT INTO machines (code, name, machine_type, area, max_usage_hours, max_vibration, max_temperature, rated_current, nominal_rpm, max_pressure)
VALUES
 ('EX-07','Excavadora hidráulica','excavator','Extracción',7500,8.0,105,80,1800,340),
 ('DR-02','Dragalina eléctrica','dragline','Descapote',12000,7.5,100,95,980,250),
 ('CT-33','Camión minero','haul_truck','Acarreo',9000,9.0,110,90,1900,300),
 ('BD-11','Bulldozer','dozer','Preparación de frentes',8000,8.5,108,85,1750,320),
 ('PF-04','Perforadora rotativa','drill','Perforación',8500,8.0,105,88,1200,280),
 ('TR-01','Trituradora primaria','crusher','Trituración',10000,7.0,95,110,740,220),
 ('BC-12','Banda transportadora','conveyor','Transporte de carbón',11000,6.0,90,70,1450,190),
 ('AP-02','Apilador recuperador','stacker_reclaimer','Patio de carbón',9500,7.0,95,75,1100,220),
 ('CF-06','Cargador frontal','wheel_loader','Manejo de patios',8000,8.5,108,85,1850,315),
 ('BA-03','Bomba de desagüe','dewatering_pump','Drenaje de mina',10000,6.5,92,72,1750,245)
ON CONFLICT (code) DO UPDATE SET
 name=EXCLUDED.name, machine_type=EXCLUDED.machine_type, area=EXCLUDED.area,
 max_usage_hours=EXCLUDED.max_usage_hours, max_vibration=EXCLUDED.max_vibration,
 max_temperature=EXCLUDED.max_temperature, rated_current=EXCLUDED.rated_current,
 nominal_rpm=EXCLUDED.nominal_rpm, max_pressure=EXCLUDED.max_pressure, active=true;

INSERT INTO work_shifts (code, name, start_time, end_time, planned_minutes)
VALUES ('A','Turno A','06:00','14:00',480),('B','Turno B','14:00','22:00',480),('C','Turno C','22:00','06:00',480)
ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name, start_time=EXCLUDED.start_time, end_time=EXCLUDED.end_time, planned_minutes=EXCLUDED.planned_minutes;

INSERT INTO products (code, name, product_type, presentation, unit_of_measure, standard_batch_size)
VALUES
 ('COAL-ROM','Carbón ROM','raw_coal','Patio ROM','ton',5000),
 ('COAL-THERMAL','Carbón térmico mezclado','saleable_coal','Lote de despacho','ton',10000)
ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name, product_type=EXCLUDED.product_type, presentation=EXCLUDED.presentation;

WITH seed(code,usage_hours,vibration,temperature,current_amps,rpm,pressure,failure_probability,health_status,explanation) AS (
 VALUES
 ('EX-07',6840,7.10,96.2,76.5,1640,329,72.8,'critical','Vibración y temperatura dominan el índice; revisar sistema hidráulico y rodamientos.'),
 ('DR-02',8150,5.20,82.4,72.1,925,231,43.5,'warning','Corriente y horas acumuladas requieren seguimiento de accionamientos.'),
 ('CT-33',5940,6.80,93.8,79.4,1745,286,61.2,'critical','Temperatura y desviación de RPM sugieren inspección de tren de potencia.'),
 ('BD-11',4720,4.90,84.1,68.2,1680,296,37.4,'healthy','Variables dentro de tendencia; mantener monitoreo del sistema hidráulico.'),
 ('PF-04',7210,6.40,91.5,81.3,1090,267,57.8,'warning','Horas, presión y vibración elevan el riesgo del cabezal de perforación.'),
 ('TR-01',8430,6.60,88.9,101.4,701,205,64.9,'critical','Vibración y corriente indican carga mecánica elevada en trituración.'),
 ('BC-12',6320,4.20,73.4,58.6,1408,171,31.6,'healthy','Condición estable; vigilar alineación y temperatura de rodillos.'),
 ('AP-02',5180,4.80,79.2,63.5,1052,207,39.8,'warning','Desviación de velocidad y presión requieren seguimiento.'),
 ('CF-06',3890,3.90,76.8,61.7,1798,292,26.4,'healthy','Telemetría estable dentro de límites demostrativos.'),
 ('BA-03',7560,5.90,86.7,69.8,1662,234,52.3,'warning','Horas acumuladas, vibración y presión sugieren revisar impulsor y sello.')
)
INSERT INTO machine_readings (machine_id, recorded_at, usage_hours, vibration, temperature, current_amps, rpm, pressure, failure_probability, health_status, explanation)
SELECT m.id, CURRENT_TIMESTAMP, s.usage_hours, s.vibration, s.temperature, s.current_amps, s.rpm, s.pressure, s.failure_probability, s.health_status, s.explanation
FROM seed s JOIN machines m ON m.code=s.code
WHERE NOT EXISTS (SELECT 1 FROM machine_readings r WHERE r.machine_id=m.id);
