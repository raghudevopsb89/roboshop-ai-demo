USE catalogue;

INSERT IGNORE INTO products (sku, name, description, price, image_url, category, stock) VALUES
('ROB001', 'Robo-Arm Deluxe', 'Industrial robotic arm with 6-axis movement. Precision-engineered for manufacturing, assembly, and pick-and-place operations. Payload capacity: 10kg. Reach: 1.2m.', 1299.99, '/images/robo-arm.svg', 'Robots', 25),
('ROB002', 'AI Brain Module', 'Neural processing unit for autonomous decision-making. Features 128 TOPS AI inference, real-time sensor fusion, and adaptive learning algorithms.', 899.99, '/images/ai-brain.svg', 'AI Modules', 50),
('ROB003', 'Servo Motor Pack (x10)', 'High-torque digital servo motors with metal gears. Torque: 25kg/cm at 6V. Speed: 0.08s/60deg. Includes mounting hardware and cables.', 149.99, '/images/servo-motors.svg', 'Components', 200),
('ROB004', 'Vision Sensor Array', 'Multi-spectrum camera array for object recognition. Includes RGB, depth, and thermal sensors. 4K resolution, 60fps, with onboard AI preprocessing.', 449.99, '/images/vision-sensor.svg', 'Components', 75),
('ROB005', 'RoboOS Pro License', 'Advanced robotics operating system. Real-time task scheduling, ROS2 compatible, built-in SLAM navigation, fleet management, and OTA updates.', 599.99, '/images/roboos.svg', 'Software', 999),
('ROB006', 'Titanium Chassis Frame', 'Lightweight aerospace-grade titanium frame. CNC-machined with integrated cable routing. Supports robots up to 50kg. Dimensions: 60x40x30cm.', 349.99, '/images/chassis.svg', 'Components', 40),
('ROB007', 'LiPo Battery Pack 48V', 'High-capacity lithium polymer battery. 48V 20Ah (960Wh). Built-in BMS with cell balancing. Fast charging support. Runtime: 4-8 hours typical.', 199.99, '/images/battery.svg', 'Components', 150),
('ROB008', 'Wireless Control Module', 'Long-range RF controller with telemetry. 2.4GHz/900MHz dual-band, 2km range, 50ms latency. Includes joystick controller and receiver module.', 129.99, '/images/wireless-ctrl.svg', 'Accessories', 120),
('ROB009', 'AI Training Dataset', 'Curated dataset for robot vision training. 500K labeled images across 200 object categories. Includes augmentation scripts and baseline models.', 79.99, '/images/dataset.svg', 'Software', 999),
('ROB010', 'Gripper Attachment Kit', 'Universal gripper with force sensors. Adaptive 3-finger design, 0.5-150mm grip range, 50N max force. Includes pneumatic and electric versions.', 249.99, '/images/gripper.svg', 'Accessories', 85),
('ROB011', 'MicroBot Starter Kit', 'Complete beginner robot building kit. Includes Arduino-compatible controller, motors, sensors, chassis, and step-by-step tutorial. Ages 12+.', 199.99, '/images/microbot.svg', 'Robots', 300),
('ROB012', 'Neural Network Accelerator', 'GPU-based ML inference card. 256 TOPS INT8, 64GB HBM3 memory, PCIe 5.0 x16. Optimized for transformer models and real-time inference.', 1499.99, '/images/nn-accel.svg', 'AI Modules', 30);
