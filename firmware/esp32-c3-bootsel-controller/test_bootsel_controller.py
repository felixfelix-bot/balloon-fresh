#!/usr/bin/env python3
"""
Test script for ESP32 RP2040 BOOTSEL Controller
Validates basic functionality and hardware integration
"""

import serial
import time
import sys

class TestBOOTSELController:
    def __init__(self, port='/dev/ttyACM0', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
    
    def connect(self):
        """Connect to ESP32 controller"""
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            print(f"✅ Connected to ESP32 on {self.port}")
            return True
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from ESP32 controller"""
        if self.serial:
            self.serial.close()
            print("🔌 Disconnected from ESP32")
    
    def send_command(self, command):
        """Send command to ESP32 and wait for response"""
        if not self.serial:
            print("❌ Not connected to ESP32")
            return False
        
        print(f"📤 Sending: {command}")
        self.serial.write(f"{command}\\n".encode())
        
        # Wait for response
        response = self.serial.readline().decode().strip()
        print(f"📥 Response: {response}")
        
        return response == "OK"
    
    def test_heartbeat_monitoring(self, duration=10):
        """Test heartbeat monitoring for specified duration"""
        print(f"🔄 Testing heartbeat monitoring for {duration} seconds...")
        
        start_time = time.time()
        heartbeats = 0
        
        while time.time() - start_time < duration:
            if self.serial.in_waiting:
                line = self.serial.readline().decode().strip()
                if line.startswith("HB rx="):
                    heartbeats += 1
                    print(f"💓 Heartbeat #{heartbeats}: {line}")
        
        print(f"📊 Received {heartbeats} heartbeats in {duration} seconds")
        return heartbeats > 0
    
    def run_all_tests(self):
        """Run complete test suite"""
        print("🧪 Starting ESP32 BOOTSEL Controller Tests")
        print("=" * 50)
        
        if not self.connect():
            print("❌ Cannot run tests - connection failed")
            return False
        
        try:
            # Test 1: Basic BOOTSEL control
            print("\\n🔧 Test 1: BOOTSEL Control")
            if self.send_command("BOOTSEL"):
                print("✅ BOOTSEL command successful")
            else:
                print("❌ BOOTSEL command failed")
            
            time.sleep(1)
            
            # Test 2: Reset functionality
            print("\\n🔄 Test 2: Reset Functionality")
            if self.send_command("RESET"):
                print("✅ RESET command successful")
            else:
                print("❌ RESET command failed")
            
            time.sleep(1)
            
            # Test 3: Status check
            print("\\n📊 Test 3: Status Check")
            if self.send_command("STATUS"):
                print("✅ STATUS command successful")
            else:
                print("❌ STATUS command failed")
            
            time.sleep(1)
            
            # Test 4: Heartbeat monitoring
            print("\\n💓 Test 4: Heartbeat Monitoring")
            if self.test_heartbeat_monitoring():
                print("✅ Heartbeat monitoring working")
            else:
                print("❌ No heartbeats detected")
            
            print("\\n🎉 All tests completed!")
            return True
            
        except Exception as e:
            print(f"❌ Test suite failed with error: {e}")
            return False
        
        finally:
            self.disconnect()

def main():
    """Main test function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test ESP32 RP2040 BOOTSEL Controller")
    parser.add_argument("--port", default="/dev/ttyACM0", 
                       help="Serial port (default: /dev/ttyACM0)")
    parser.add_argument("--baudrate", type=int, default=115200,
                       help="Baud rate (default: 115200)")
    
    args = parser.parse_args()
    
    tester = TestBOOTSELController(args.port, args.baudrate)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()