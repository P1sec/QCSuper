import serial
import time
import sys

class ATSock:
    def __init__(self, port='/dev/ttyUSB2', baudrate=115200, timeout=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None

        try:
            # Configure and open the serial port
            self.ser = serial.Serial(
                self.port,
                self.baudrate,
                timeout=self.timeout
            )
            if self.ser.is_open:
                print(f"Successfully connected to {self.port}")
            else:
                # This case is unlikely with pyserial but good practice
                print(f"Error: Could not open {self.port}", file=sys.stderr)
                self.ser = None

        except serial.SerialException as e:
            print(f"Error connecting to {self.port}: {e}\nCheck port and permissions", file=sys.stderr)
            self.ser = None
        except Exception as e:
            print(f"An unexpected error occurred: {e}", file=sys.stderr)
            self.ser = None

    def send_command(self, command, read_delay=0.1):
        if not self.ser or not self.ser.is_open:
            return "Error: Serial port is not connected."

        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

        full_command = command + '\r\n'
        self.ser.write(full_command.encode('utf-8'))

        # Processing delay
        time.sleep(read_delay)

        response_lines = []
        while self.ser.in_waiting > 0:
            try:
                line = self.ser.readline().decode('utf-8').strip()
                if line: 
                    # Avoid adding empty lines
                    response_lines.append(line)
            except UnicodeDecodeError:
                # Handle cases where non-UTF-8 characters are received
                response_lines.append("[Undecodable data]")
        
        # Join the lines into a single string
        response = '\n'.join(response_lines)

        return response
    
    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print(f"Disconnected from {self.port}")

    def __enter__(self):
        """Allows the class to be used with a 'with' statement."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Closes the connection automatically when exiting a 'with' block."""
        self.close()